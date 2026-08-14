from pathlib import Path
import hashlib,json,shutil,zipfile,subprocess,sys

ROOT=Path.cwd()
# 1) Build the already-designed 10.0.7 UI safely from 10.0.6.
src=(ROOT/'tools'/'publish_10_0_7.py').read_text(encoding='utf-8')
src=src.replace('WORK = ROOT / "_build-10.0.7"','WORK = ROOT / "_build-10.1.0-stage"')
src=src.replace('OUT = ROOT / "update-10.0.7.zip"','OUT = ROOT / "_stage-10.0.7.zip"')
src=src.replace('if start<0 or end<0: raise SystemExit("renderWallAlerts block missing")','if start<0 or end<0:\n    start=-1; end=-1')
src=src.replace('s=s[:start]+new_renderer+s[end:]','s=(s[:start]+new_renderer+s[end:]) if start>=0 and end>=0 else s')
patched=ROOT/'_publish_stage.py';patched.write_text(src,encoding='utf-8')
subprocess.run([sys.executable,str(patched)],check=True)

stagezip=ROOT/'_stage-10.0.7.zip'
work=ROOT/'_bootstrap-10.1.0'
if work.exists():shutil.rmtree(work)
work.mkdir()
with zipfile.ZipFile(stagezip,'r') as z:z.extractall(work)
app=work/'Topaloglu-Pazaryeri-Merkezi'
if not app.exists():raise SystemExit('package root missing')

# 2) Replace updater with direct changed-file channel implementation.
updater=r'''from __future__ import annotations
import hashlib,json,os,shutil,subprocess,sys,tempfile,zipfile
from pathlib import Path
import httpx
APP_DIR=Path(__file__).resolve().parents[1]
VERSION_FILE=APP_DIR/'VERSION'
CHANNEL='https://raw.githubusercontent.com/topaloglusarraf-afk/topaloglu-updates/main/channel.json'
LEGACY='https://raw.githubusercontent.com/topaloglusarraf-afk/topaloglu-updates/main/latest.json'
PROTECTED={'.env','data','topaloglu.db','app.db','.venv'}
def current_version():
    try:return VERSION_FILE.read_text(encoding='utf-8').strip()
    except:return '0.0.0'
def _v(v):
    a=[]
    for x in str(v).split('.'):
        try:a.append(int(''.join(c for c in x if c.isdigit()) or 0))
        except:a.append(0)
    return tuple((a+[0,0,0])[:3])
def _safe(rel):
    p=Path(str(rel).replace('\\','/'))
    if p.is_absolute() or '..' in p.parts or not p.parts:raise ValueError('Güvensiz dosya yolu')
    if p.parts[0] in PROTECTED:raise ValueError('Kalıcı kullanıcı verisi güncellenemez')
    return p
async def _json(url):
    async with httpx.AsyncClient(timeout=15,follow_redirects=True) as c:r=await c.get(url,headers={'Cache-Control':'no-cache','Pragma':'no-cache'})
    r.raise_for_status();return r.json()
async def check():
    try:
        m=await _json(CHANNEL);latest=str(m.get('version') or '0.0.0')
        if latest!='0.0.0':return {'ok':True,'configured':True,'channel':'direct','current':current_version(),'latest':latest,'available':_v(latest)>_v(current_version()),'notes':m.get('notes') or '','published_at':m.get('published_at') or '','files':m.get('files') or [],'package_url':m.get('package_url'),'sha256':m.get('sha256') or ''}
    except Exception:pass
    try:
        m=await _json(LEGACY);latest=str(m.get('version') or '0.0.0')
        return {'ok':True,'configured':True,'channel':'legacy','current':current_version(),'latest':latest,'available':_v(latest)>_v(current_version()),'notes':m.get('notes') or '','published_at':m.get('published_at') or '','package_url':m.get('package_url'),'sha256':m.get('sha256') or ''}
    except Exception as e:return {'ok':False,'configured':True,'current':current_version(),'message':f'Güncelleme kontrolü başarısız: {e}'}
async def _download(url,dst,sha=''):
    dst.parent.mkdir(parents=True,exist_ok=True);h=hashlib.sha256()
    async with httpx.AsyncClient(timeout=120,follow_redirects=True) as c:
        async with c.stream('GET',url,headers={'Cache-Control':'no-cache'}) as r:
            r.raise_for_status()
            with open(dst,'wb') as f:
                async for b in r.aiter_bytes():h.update(b);f.write(b)
    got=h.hexdigest()
    if sha and got.lower()!=str(sha).lower().strip():raise ValueError('SHA256 doğrulaması başarısız')
async def _direct(st):
    files=st.get('files') or []
    if not files:return {**st,'ok':False,'message':'Güncelleme dosya listesi boş.'}
    root=Path(tempfile.gettempdir())/'topaloglu_direct_update';shutil.rmtree(root,ignore_errors=True);stage=root/'stage';stage.mkdir(parents=True)
    rels=[]
    for i in files:
        rel=_safe(i.get('path') or '');url=str(i.get('url') or '')
        if not url.startswith('https://'):raise ValueError('Geçersiz güncelleme adresi')
        await _download(url,stage/rel,i.get('sha256') or '');rels.append(str(rel).replace('\\','/'))
    (root/'manifest.json').write_text(json.dumps({'version':st['latest'],'files':rels},ensure_ascii=False),encoding='utf-8')
    helper=root/'apply.py';helper.write_text("""import json,shutil,subprocess,sys,time\nfrom datetime import datetime\nfrom pathlib import Path\napp=Path(sys.argv[1]);root=Path(sys.argv[2]);stage=root/'stage';time.sleep(3)\nm=json.loads((root/'manifest.json').read_text(encoding='utf-8'));bak=app/'data'/'update-backups'/(datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+m['version']);bak.mkdir(parents=True,exist_ok=True);done=[]\ntry:\n for s in m['files']:\n  r=Path(s);src=stage/r;dst=app/r\n  if dst.exists() and dst.is_file():b=bak/r;b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dst,b)\n  dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);done.append(s)\n (app/'VERSION').write_text(m['version'],encoding='utf-8')\nexcept Exception:\n for s in done:\n  r=Path(s);b=bak/r;dst=app/r\n  if b.exists():dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(b,dst)\n raise\nbat=app/'BASLAT.bat'\nif bat.exists():subprocess.Popen(['cmd','/c',str(bat)],cwd=str(app),creationflags=0x00000008)\n""",encoding='utf-8')
    subprocess.Popen([sys.executable,str(helper),str(APP_DIR),str(root)],cwd=str(APP_DIR),creationflags=(0x00000008 if os.name=='nt' else 0));return {**st,'prepared':True,'message':f'{len(files)} dosya güncellenecek. Uygulama yeniden başlatılacak.'}
async def _legacy(st):
    root=Path(tempfile.gettempdir())/'topaloglu_update';shutil.rmtree(root,ignore_errors=True);root.mkdir();zp=root/'u.zip';await _download(st['package_url'],zp,st.get('sha256') or '')
    ext=root/'x';ext.mkdir()
    with zipfile.ZipFile(zp) as z:
        base=ext.resolve()
        for i in z.infolist():
            d=(ext/Path(i.filename)).resolve()
            if base not in d.parents and d!=base:raise ValueError('Güvensiz ZIP')
        z.extractall(ext)
    ch=[p for p in ext.iterdir()];payload=ch[0] if len(ch)==1 and ch[0].is_dir() else ext
    helper=root/'apply.py';helper.write_text("""import shutil,subprocess,sys,time\nfrom pathlib import Path\napp=Path(sys.argv[1]);src=Path(sys.argv[2]);time.sleep(3);keep={'.env','data','topaloglu.db','app.db','.venv'}\ndef cp(a,b):\n if a.is_dir():b.mkdir(parents=True,exist_ok=True);[cp(x,b/x.name) for x in a.iterdir() if x.name not in {'__pycache__','.git'}]\n else:b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a,b)\nfor x in src.iterdir():\n if x.name not in keep:cp(x,app/x.name)\nbat=app/'BASLAT.bat'\nif bat.exists():subprocess.Popen(['cmd','/c',str(bat)],cwd=str(app),creationflags=0x00000008)\n""",encoding='utf-8')
    subprocess.Popen([sys.executable,str(helper),str(APP_DIR),str(payload)],cwd=str(APP_DIR),creationflags=(0x00000008 if os.name=='nt' else 0));return {**st,'prepared':True,'message':'Geçiş güncellemesi indirildi. Uygulama yeniden başlatılacak.'}
async def prepare_update():
    st=await check()
    if not st.get('ok'):return st
    if not st.get('available'):return {**st,'message':'Uygulama zaten güncel.'}
    try:return await _direct(st) if st.get('channel')=='direct' and st.get('files') else await _legacy(st)
    except Exception as e:return {**st,'ok':False,'message':f'Güncelleme hazırlanamadı: {e}'}
'''
(app/'app'/'updater.py').write_text(updater,encoding='utf-8')
(app/'VERSION').write_text('10.1.0',encoding='utf-8')
for rel in ['app/static/index.html','README.md']:
    p=app/rel;t=p.read_text(encoding='utf-8').replace('10.0.7','10.1.0');p.write_text(t,encoding='utf-8')
for py in app.rglob('*.py'):subprocess.run([sys.executable,'-m','py_compile',str(py)],check=True)
try:subprocess.run(['node','--check',str(app/'app/static/app.js')],check=True)
except FileNotFoundError:pass
out=ROOT/'update-10.1.0.zip'
if out.exists():out.unlink()
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
    for f in app.rglob('*'):
        if f.is_file() and '__pycache__' not in f.parts:z.write(f,Path('Topaloglu-Pazaryeri-Merkezi')/f.relative_to(app))
sha=hashlib.sha256(out.read_bytes()).hexdigest()
latest={'version':'10.1.0','published_at':'2026-08-14','notes':'Pazaryeri kapsam seçimi, yeni kritik ekran ve doğrudan dosya güncelleme altyapısı.','package_url':'https://raw.githubusercontent.com/topaloglusarraf-afk/topaloglu-updates/main/update-10.1.0.zip','sha256':sha}
channel={'version':'10.1.0','published_at':'2026-08-14','notes':'Doğrudan dosya güncelleme kanalı aktif.','files':[],'package_url':latest['package_url'],'sha256':sha}
(ROOT/'latest.json').write_text(json.dumps(latest,ensure_ascii=False,indent=2),encoding='utf-8');(ROOT/'channel.json').write_text(json.dumps(channel,ensure_ascii=False,indent=2),encoding='utf-8')
print('built',sha)
