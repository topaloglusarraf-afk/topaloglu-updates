from pathlib import Path

ROOT=Path('_desktop_src')
apps=[p for p in ROOT.iterdir() if p.is_dir() and (p/'app').is_dir()]
if not apps: raise SystemExit('desktop source root not found')
APP=apps[0]

# ---- version ----
launcher=APP/'desktop_launcher.py'
s=launcher.read_text(encoding='utf-8')
s=s.replace('VERSION = "10.2.1"','VERSION = "10.2.2"')
launcher.write_text(s,encoding='utf-8')

iss=APP/'desktop_installer.iss'
s=iss.read_text(encoding='utf-8')
s=s.replace('#define MyAppVersion "10.2.1"','#define MyAppVersion "10.2.2"')
s=s.replace('Topaloglu-Pazaryeri-Merkezi-Setup-10.2.1','Topaloglu-Pazaryeri-Merkezi-Setup-10.2.2')
iss.write_text(s,encoding='utf-8')
(APP/'DESKTOP_VERSION.txt').write_text('10.2.2\n',encoding='utf-8')

# ---- backend .env editor ----
main=APP/'app/main.py'
s=main.read_text(encoding='utf-8')
if 'import re\n' not in s[:300]:
    s=s.replace('import os\n','import os\nimport re\n',1)

block=r'''

# v10.2.2 desktop settings / safe .env editor
_ENV_SECRET_RE=re.compile(r"(TOKEN|SECRET|PASSWORD|PASS|KEY|AUTH|BEARER)",re.I)
_ENV_SAFE_VALUE_RE=re.compile(r"(URL|BASE|ENABLED|MODE|PATH|INTERVAL|MINUTES|PORT|HOST|LIMIT|SIZE|TIMEOUT|ID)$",re.I)

def _desktop_env_path():
    return Path.cwd()/'.env'

def _read_env_lines():
    p=_desktop_env_path()
    if not p.exists(): return []
    return p.read_text(encoding='utf-8-sig',errors='ignore').splitlines()

def _parse_env():
    out=[]
    seen=set()
    for raw in _read_env_lines():
        line=raw.strip()
        if not line or line.startswith('#') or '=' not in line: continue
        key,val=line.split('=',1); key=key.strip(); val=val.strip().strip('"').strip("'")
        if not key or key in seen: continue
        seen.add(key)
        secret=bool(_ENV_SECRET_RE.search(key))
        safe=(not secret) and bool(_ENV_SAFE_VALUE_RE.search(key))
        out.append({'key':key,'configured':bool(val),'secret':secret,'value':val if safe else ''})
    return out

@app.get('/api/desktop/settings')
def desktop_settings_get():
    return {
        'ok':True,
        'desktop':os.getenv('TOPOLOGLU_DESKTOP')=='1',
        'version':os.getenv('TOPOLOGLU_DESKTOP_VERSION','10.2.2'),
        'env_path':str(_desktop_env_path()),
        'fields':_parse_env(),
    }

@app.post('/api/desktop/settings')
def desktop_settings_save(payload:dict=Body(...)):
    changes=payload.get('changes') or {}
    additions=payload.get('additions') or []
    if not isinstance(changes,dict) or not isinstance(additions,list):
        raise HTTPException(400,'Ayar verisi geçersiz.')
    lines=_read_env_lines()
    index={}
    for i,raw in enumerate(lines):
        st=raw.strip()
        if st and not st.startswith('#') and '=' in st:
            k=st.split('=',1)[0].strip()
            if k and k not in index:index[k]=i
    allowed=re.compile(r'^[A-Z0-9_]{2,80}$')
    changed=[]
    for key,value in changes.items():
        key=str(key or '').strip().upper()
        if not allowed.match(key): continue
        value=str(value if value is not None else '').replace('\r','').replace('\n','').strip()
        # Blank means keep existing value; explicit clear must use __CLEAR__.
        if value=='': continue
        if value=='__CLEAR__': value=''
        row=f'{key}={value}'
        if key in index: lines[index[key]]=row
        else: index[key]=len(lines); lines.append(row)
        os.environ[key]=value
        changed.append(key)
    for item in additions:
        if not isinstance(item,dict): continue
        key=str(item.get('key') or '').strip().upper()
        value=str(item.get('value') or '').replace('\r','').replace('\n','').strip()
        if not allowed.match(key) or not value: continue
        row=f'{key}={value}'
        if key in index: lines[index[key]]=row
        else: index[key]=len(lines); lines.append(row)
        os.environ[key]=value
        changed.append(key)
    p=_desktop_env_path(); p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text('\n'.join(lines).rstrip()+'\n',encoding='utf-8')
    return {'ok':True,'changed':sorted(set(changed)),'restart_required':True,'env_path':str(p)}
'''
if '# v10.2.2 desktop settings / safe .env editor' not in s:
    marker='@app.get("/api/update/check")'
    pos=s.find(marker)
    if pos<0: raise SystemExit('main.py update marker not found')
    s=s[:pos]+block+'\n'+s[pos:]
main.write_text(s,encoding='utf-8')

# ---- frontend settings view + force real desktop version ----
js=APP/'app/static/app.js'
s=js.read_text(encoding='utf-8')
s=s.replace("H.desktop_version||'10.2.1'","H.desktop_version||'10.2.2'")
append=r'''

/* v10.2.2 — desktop version + safe ENV settings */
(function(){
  const q=s=>document.querySelector(s);
  const esc=v=>String(v??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]));
  async function api22(url,opt){const r=await fetch(url,opt);let j={};try{j=await r.json()}catch(_){ }if(!r.ok)throw new Error(j.detail||j.message||'İşlem başarısız');return j}
  function forceVersion22(v){
    const ver=v||'10.2.2';
    const up=q('#updateVersion');if(up)up.textContent='Masaüstü v'+ver;
    document.querySelectorAll('.brand span').forEach(x=>{if(/v\d|Pazaryeri Merkezi/i.test(x.textContent||''))x.textContent='Pazaryeri Merkezi v'+ver});
  }
  function installSettingsView22(){
    if(q('#desktopSettingsNav22'))return;
    const nav=document.querySelector('.sidebar nav'); if(!nav)return;
    const b=document.createElement('button');b.id='desktopSettingsNav22';b.className='nav';b.innerHTML='<i>⚙</i> Ayarlar & Bağlantılar';nav.appendChild(b);
    const main=document.querySelector('main.main');if(!main)return;
    const sec=document.createElement('section');sec.id='view-desktop-settings22';sec.className='view';
    sec.innerHTML=`<section class="settings22-shell">
      <article class="settings22-hero glass"><div><span class="section-kicker">MASAÜSTÜ AYARLARI</span><h2>Ayarlar & Bağlantılar</h2><p>.env bilgilerini CMD veya klasör açmadan güvenli biçimde yönetin.</p></div><div class="settings22-version"><span>Uygulama</span><b id="settingsVersion22">v10.2.2</b></div></article>
      <article class="panel glass settings22-panel"><div class="panel-head"><div><h2>Bağlantı Ayarları</h2><p>Gizli anahtarlar ekranda gösterilmez. Değiştirmek istediğiniz değeri yazıp kaydedin.</p></div><button id="reloadSettings22" class="btn ghost">Yenile</button></div><div id="settingsPath22" class="settings22-path"></div><div id="settingsFields22" class="settings22-fields"><div class="settings22-loading">Ayarlar yükleniyor…</div></div></article>
      <article class="panel glass settings22-add"><div><h3>Yeni ENV Anahtarı</h3><p>Gerekirse yeni bir bağlantı anahtarı ekleyebilirsiniz.</p></div><input id="newEnvKey22" placeholder="Örn: CONNECTPROF_ENABLED"><input id="newEnvValue22" placeholder="Değer"><button id="addEnv22" class="btn ghost">Listeye Ekle</button></article>
      <div class="settings22-footer"><span>Değişiklikler .env dosyasına kaydedilir.</span><button id="saveSettings22" class="btn primary">Ayarları Kaydet</button></div>
      <div class="settings22-note">Kaydettikten sonra yeni bağlantı bilgilerinin tamamının aktif olması için uygulamayı kapatıp tekrar açın.</div>
    </section>`;
    main.appendChild(sec);
    b.onclick=async()=>{document.querySelectorAll('.nav').forEach(x=>x.classList.remove('active'));b.classList.add('active');document.querySelectorAll('.view').forEach(x=>x.classList.remove('active'));sec.classList.add('active');await loadSettings22()};
    q('#reloadSettings22').onclick=loadSettings22;
    q('#addEnv22').onclick=()=>{const k=q('#newEnvKey22').value.trim().toUpperCase(),v=q('#newEnvValue22').value;if(!k||!v)return typeof toast==='function'&&toast('Anahtar ve değer girin.');const box=q('#settingsFields22');const row=document.createElement('div');row.className='settings22-row settings22-new';row.dataset.key=k;row.innerHTML=`<div class="settings22-meta"><b>${esc(k)}</b><span>Yeni anahtar</span></div><input class="settings22-input" value="${esc(v)}"><span class="settings22-state">Yeni</span>`;box.appendChild(row);q('#newEnvKey22').value='';q('#newEnvValue22').value=''};
    q('#saveSettings22').onclick=saveSettings22;
  }
  async function loadSettings22(){
    try{const d=await api22('/api/desktop/settings');forceVersion22(d.version);if(q('#settingsVersion22'))q('#settingsVersion22').textContent='v'+d.version;if(q('#settingsPath22'))q('#settingsPath22').textContent='ENV konumu: '+d.env_path;const box=q('#settingsFields22');box.innerHTML=(d.fields||[]).map(f=>`<div class="settings22-row" data-key="${esc(f.key)}"><div class="settings22-meta"><b>${esc(f.key)}</b><span>${f.secret?'Gizli değer':f.configured?'Yapılandırılmış':'Boş'}</span></div><input class="settings22-input" type="${f.secret?'password':'text'}" value="${esc(f.value||'')}" placeholder="${f.secret&&f.configured?'Kayıtlı — değiştirmek için yeni değer yaz':'Değer'}"><span class="settings22-state ${f.configured?'ok':''}">${f.configured?'Kayıtlı':'Boş'}</span></div>`).join('')||'<div class="settings22-loading">Henüz .env anahtarı bulunamadı.</div>'}catch(e){if(typeof toast==='function')toast('Ayarlar yüklenemedi: '+e.message)}
  }
  async function saveSettings22(){
    const changes={},additions=[];document.querySelectorAll('#settingsFields22 .settings22-row').forEach(r=>{const key=r.dataset.key,val=r.querySelector('.settings22-input')?.value??'';if(r.classList.contains('settings22-new'))additions.push({key,value:val});else if(val!=='')changes[key]=val});const b=q('#saveSettings22');b.disabled=true;b.textContent='Kaydediliyor…';try{const r=await api22('/api/desktop/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({changes,additions})});if(typeof toast==='function')toast((r.changed||[]).length+' ayar kaydedildi. Uygulamayı yeniden başlatın.');await loadSettings22()}catch(e){if(typeof toast==='function')toast('Kaydetme başarısız: '+e.message)}finally{b.disabled=false;b.textContent='Ayarları Kaydet'}}
  async function boot22(){installSettingsView22();try{const d=await api22('/api/desktop/settings');forceVersion22(d.version)}catch(_){forceVersion22('10.2.2')}setInterval(()=>forceVersion22('10.2.2'),1500)}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot22);else boot22();
})();
'''
if 'v10.2.2 — desktop version + safe ENV settings' not in s:
    s += append
js.write_text(s,encoding='utf-8')

css=APP/'app/static/style.css'
s=css.read_text(encoding='utf-8')
css += r'''

/* v10.2.2 desktop settings */
.settings22-shell{display:grid;gap:18px}.settings22-hero{display:flex;align-items:center;justify-content:space-between;padding:28px 30px}.settings22-hero h2{margin:6px 0 8px;font-size:30px}.settings22-hero p{margin:0;color:var(--muted,#8d97a8)}.settings22-version{min-width:150px;text-align:right}.settings22-version span{display:block;font-size:11px;letter-spacing:.12em;color:var(--muted,#8d97a8)}.settings22-version b{display:block;margin-top:6px;font-size:22px}.settings22-panel{padding:22px}.settings22-path{margin:4px 0 18px;padding:10px 12px;border:1px solid rgba(201,168,76,.16);border-radius:12px;color:#aab2c2;font-size:12px;background:rgba(255,255,255,.02);word-break:break-all}.settings22-fields{display:grid;gap:10px}.settings22-row{display:grid;grid-template-columns:minmax(220px,.9fr) minmax(280px,1.6fr) 90px;gap:14px;align-items:center;padding:14px 16px;border:1px solid rgba(255,255,255,.07);border-radius:14px;background:rgba(255,255,255,.025)}.settings22-meta b{display:block;font-size:13px;letter-spacing:.02em}.settings22-meta span{display:block;margin-top:4px;font-size:11px;color:#7f899a}.settings22-input{width:100%;border:1px solid rgba(255,255,255,.09);border-radius:10px;background:rgba(7,10,16,.72);color:#eef1f7;padding:11px 12px;outline:none}.settings22-input:focus{border-color:rgba(201,168,76,.6);box-shadow:0 0 0 3px rgba(201,168,76,.08)}.settings22-state{font-size:11px;text-align:center;padding:7px 9px;border-radius:999px;background:rgba(255,255,255,.06);color:#8f98a8}.settings22-state.ok{background:rgba(64,195,132,.12);color:#6fdda9}.settings22-add{display:grid;grid-template-columns:1fr minmax(220px,.7fr) minmax(260px,1fr) auto;gap:12px;align-items:center;padding:20px 22px}.settings22-add h3{margin:0 0 4px}.settings22-add p{margin:0;color:#8490a2;font-size:12px}.settings22-add input{border:1px solid rgba(255,255,255,.09);border-radius:10px;background:rgba(7,10,16,.72);color:#eef1f7;padding:11px 12px}.settings22-footer{display:flex;justify-content:flex-end;align-items:center;gap:18px;padding:4px 2px}.settings22-footer span{font-size:12px;color:#818b9b}.settings22-note{padding:14px 16px;border:1px solid rgba(201,168,76,.18);border-radius:12px;background:rgba(201,168,76,.055);color:#c9b97c;font-size:12px}.settings22-loading{padding:20px;color:#8993a3;text-align:center}@media(max-width:1000px){.settings22-row{grid-template-columns:1fr}.settings22-state{text-align:left;width:max-content}.settings22-add{grid-template-columns:1fr}.settings22-hero{align-items:flex-start;gap:20px}.settings22-version{text-align:left}}
'''
css.write_text(s,encoding='utf-8')

print(APP)
