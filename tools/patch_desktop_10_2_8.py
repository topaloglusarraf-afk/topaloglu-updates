from pathlib import Path
import re

ROOT=Path('_desktop_src')
apps=[p for p in ROOT.iterdir() if p.is_dir() and (p/'app').is_dir()]
if not apps: raise SystemExit('desktop source root not found')
APP=apps[0]

# version
launcher=APP/'desktop_launcher.py'
s=launcher.read_text(encoding='utf-8')
s=s.replace('VERSION = "10.2.7"','VERSION = "10.2.8"')
launcher.write_text(s,encoding='utf-8')

iss=APP/'desktop_installer.iss'
s=iss.read_text(encoding='utf-8')
s=s.replace('#define MyAppVersion "10.2.7"','#define MyAppVersion "10.2.8"')
s=s.replace('Topaloglu-Pazaryeri-Merkezi-Setup-10.2.7','Topaloglu-Pazaryeri-Merkezi-Setup-10.2.8')
iss.write_text(s,encoding='utf-8')
(APP/'DESKTOP_VERSION.txt').write_text('10.2.8\n',encoding='utf-8')

# Backend: never ask Chrome to load from the PyInstaller program root.
main=APP/'app/main.py'
s=main.read_text(encoding='utf-8')
if 'import shutil\n' not in s[:900]:
    s=s.replace('import subprocess\n','import subprocess\nimport shutil\n',1)

old='''def _hb_extension_dir_1027():\n    if getattr(sys,"frozen",False):\n        return Path(sys.executable).resolve().parent / "chrome-extension"\n    return Path(__file__).resolve().parent.parent / "chrome-extension"\n\n@app.post("/api/hepsiburada/extension/open-folder")\ndef hepsiburada_extension_open_folder_1027():\n    p=_hb_extension_dir_1027()\n    if not p.exists(): raise HTTPException(404,"Chrome eklenti klasörü bulunamadı.")\n    if os.name=="nt":\n        subprocess.Popen(["explorer",str(p)])\n    return {"ok":True,"path":str(p)}\n'''
new='''def _hb_extension_source_1028():\n    if getattr(sys,"frozen",False):\n        return Path(sys.executable).resolve().parent / "chrome-extension"\n    return Path(__file__).resolve().parent.parent / "chrome-extension"\n\ndef _hb_extension_clean_dir_1028():\n    base=os.environ.get("LOCALAPPDATA") or str(Path.home()/"AppData"/"Local")\n    return Path(base)/"Topaloglu"/"PazaryeriMerkezi"/"Topaloglu-Hepsiburada-Uzantisi"\n\ndef _prepare_hb_extension_1028():\n    src=_hb_extension_source_1028()\n    if not (src/"manifest.json").exists():\n        raise HTTPException(404,"Paket içindeki Chrome eklentisi bulunamadı.")\n    dest=_hb_extension_clean_dir_1028()\n    dest.parent.mkdir(parents=True,exist_ok=True)\n    if dest.exists(): shutil.rmtree(dest,ignore_errors=True)\n    shutil.copytree(src,dest)\n    required=["manifest.json","background.js","content.js","main_hook.js","popup.html"]\n    missing=[x for x in required if not (dest/x).exists()]\n    if missing:\n        raise HTTPException(500,"Eklenti hazırlanamadı. Eksik dosya: "+", ".join(missing))\n    # Chrome unpacked extension root must be clean: no PyInstaller _internal or executable tree.\n    bad=[p.name for p in dest.iterdir() if p.name.startswith("_")]\n    if bad:\n        raise HTTPException(500,"Eklenti klasörü temiz değil: "+", ".join(bad))\n    return dest\n\n@app.post("/api/hepsiburada/extension/open-folder")\ndef hepsiburada_extension_open_folder_1028():\n    p=_prepare_hb_extension_1028()\n    if os.name=="nt": subprocess.Popen(["explorer",str(p)])\n    return {"ok":True,"path":str(p),"folder_name":p.name,"manifest":str(p/"manifest.json")}\n\n@app.post("/api/hepsiburada/extension/prepare")\ndef hepsiburada_extension_prepare_1028():\n    p=_prepare_hb_extension_1028()\n    return {"ok":True,"path":str(p),"folder_name":p.name,"manifest":str(p/"manifest.json")}\n'''
if old not in s:
    raise SystemExit('10.2.7 extension folder block missing')
s=s.replace(old,new,1)
# status version
s=s.replace('"version":"10.2.7","mode":"extension"','"version":"10.2.8","mode":"extension"',1)
main.write_text(s,encoding='utf-8')

# UI: show exact clean folder and copy-to-clipboard button.
idx=APP/'app/static/index.html'
h=idx.read_text(encoding='utf-8')
h=h.replace('v10.2.7','v10.2.8')
h=re.sub(r'/static/style\\.css(?:\\?v=[^"\\\']*)?', '/static/style.css?v=10.2.8', h)
h=re.sub(r'/static/app\\.js(?:\\?v=[^"\\\']*)?', '/static/app.js?v=10.2.8', h)
h=re.sub(r'/static/desktop_settings\\.js(?:\\?v=[^"\\\']*)?', '/static/desktop_settings.js?v=10.2.8', h)
h=re.sub(r'/static/mete_boot\\.js(?:\\?v=[^"\\\']*)?', '/static/mete_boot.js?v=10.2.8', h)
h=re.sub(r'/static/hepsiburada_bridge\\.js(?:\\?v=[^"\\\']*)?', '/static/hepsiburada_bridge.js?v=10.2.8', h)
idx.write_text(h,encoding='utf-8')

bridge=APP/'app/static/hepsiburada_bridge.js'
b=bridge.read_text(encoding='utf-8')
# Replace full file with robust clean-folder UX while keeping same card id.
b=r'''(function(){
const q=s=>document.querySelector(s);
async function api(u,o){const r=await fetch(u,o);let j={};try{j=await r.json()}catch(_){}if(!r.ok)throw new Error(j.detail||'İşlem başarısız');return j}
function hideRaw(){document.querySelectorAll('.desktop-setting-row').forEach(r=>{if((r.dataset.key||'').startsWith('HEPSIBURADA_'))r.style.display='none'})}
async function prepare(open){const out=q('#hbState1028');try{const d=await api(open?'/api/hepsiburada/extension/open-folder':'/api/hepsiburada/extension/prepare',{method:'POST'});if(out)out.innerHTML=`Hazır klasör: <strong>${esc(d.folder_name)}</strong>`;const path=q('#hbPath1028');if(path)path.value=d.path||'';return d}catch(e){if(out)out.textContent='✕ '+e.message;throw e}}
async function load(){const host=q('#desktopSettingsFields');if(!host)return;hideRaw();let card=q('#hbBridge1027');if(!card){card=document.createElement('section');card.id='hbBridge1027';card.className='hb1027-card';host.parentElement.insertBefore(card,host)}let d={};try{d=await api('/api/hepsiburada/extension/status')}catch(e){d={ok:false,message:e.message}}const last=d.last_import_at?`Son aktarım: ${d.last_import_at} · ${d.last_saved||0} kayıt`:'Henüz veri alınmadı';card.innerHTML=`<div class="hb1027-head"><div><span>HEPSİBURADA</span><h3>Satıcı Paneli Bağlantısı</h3><p>API anahtarı gerekmez. Chrome uzantısı yalnız ET ürün fiyatı ve stok bilgisini yerel uygulamaya aktarır.</p></div><div class="hb1027-state ${d.last_import_at?'ok':''}">${d.last_import_at?'Bağlı':'Eklenti bekleniyor'}</div></div><div class="hb1027-steps"><div><b>1</b><span><strong>Eklenti Klasörünü Hazırla ve Aç</strong> butonuna bas. Açılan klasörün adı <strong>Topaloglu-Hepsiburada-Uzantisi</strong> olacak.</span></div><div><b>2</b><span>Chrome'da <strong>chrome://extensions</strong> → Geliştirici Modu → <strong>Paketlenmemiş öğe yükle</strong>.</span></div><div><b>3</b><span>Chrome seçim penceresinde uygulama klasörünü DEĞİL, aşağıdaki tam yolu taşıyan <strong>Topaloglu-Hepsiburada-Uzantisi</strong> klasörünü seç.</span></div></div><div class="hb1028-path"><label>Chrome'a seçilecek TAM klasör</label><div><input id="hbPath1028" readonly placeholder="Hazırlamak için butona bas"><button id="hbCopy1028" class="btn ghost">Yolu Kopyala</button></div></div><div class="hb1027-actions"><button id="hbOpen1028" class="btn primary">Eklenti Klasörünü Hazırla ve Aç</button><button id="hbRefresh1027" class="btn ghost">Bağlantı Durumunu Yenile</button><span id="hbState1028">${last}</span></div><div class="hb1027-safe">🔒 Doğru klasörün içinde <strong>manifest.json</strong> görünür. <strong>_internal</strong> görüyorsan yanlış klasördesin. Şifre, cookie ve oturum tokenı okunmaz.</div>`;
q('#hbOpen1028').onclick=()=>prepare(true);q('#hbRefresh1027').onclick=load;q('#hbCopy1028').onclick=async()=>{try{let path=q('#hbPath1028').value;if(!path){const d=await prepare(false);path=d.path||''}await navigator.clipboard.writeText(path);q('#hbState1028').textContent='✓ Klasör yolu kopyalandı.'}catch(e){q('#hbState1028').textContent='✕ '+e.message}};try{const p=await prepare(false);q('#hbPath1028').value=p.path||''}catch(_){}}
function esc(v){return String(v??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]))}
function boot(){const nav=document.querySelector('[data-view="desktop-settings"]');if(nav)nav.addEventListener('click',()=>setTimeout(load,120));const host=q('#desktopSettingsFields');if(host)new MutationObserver(hideRaw).observe(host,{childList:true,subtree:true})}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();'''
bridge.write_text(b,encoding='utf-8')

css=APP/'app/static/style.css'
cs=css.read_text(encoding='utf-8')
cs+=r'''
/* v10.2.8 clean Chrome extension folder */
.hb1028-path{margin:0 0 13px;padding:12px;border-radius:11px;background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.06)}.hb1028-path label{display:block;margin-bottom:7px;color:#8e99aa;font-size:10px;text-transform:uppercase;letter-spacing:.08em}.hb1028-path>div{display:flex;gap:8px}.hb1028-path input{flex:1;font-family:"Cascadia Mono","Consolas",monospace;font-size:10.5px;color:#d8c27c!important}.hb1027-safe strong{color:#dfe6ef}
'''
css.write_text(cs,encoding='utf-8')

# Source validations
assert '_prepare_hb_extension_1028' in main.read_text(encoding='utf-8')
assert 'Topaloglu-Hepsiburada-Uzantisi' in bridge.read_text(encoding='utf-8')
print(APP)
