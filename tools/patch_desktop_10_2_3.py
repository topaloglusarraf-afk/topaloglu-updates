from pathlib import Path

ROOT=Path('_desktop_src')
apps=[p for p in ROOT.iterdir() if p.is_dir() and (p/'app').is_dir()]
if not apps: raise SystemExit('desktop source root not found')
APP=apps[0]

# version
launcher=APP/'desktop_launcher.py'
s=launcher.read_text(encoding='utf-8')
s=s.replace('VERSION = "10.2.1"','VERSION = "10.2.3"').replace('VERSION = "10.2.0"','VERSION = "10.2.3"')
launcher.write_text(s,encoding='utf-8')
iss=APP/'desktop_installer.iss'
s=iss.read_text(encoding='utf-8')
s=s.replace('#define MyAppVersion "10.2.0"','#define MyAppVersion "10.2.3"').replace('#define MyAppVersion "10.2.1"','#define MyAppVersion "10.2.3"')
s=s.replace('Topaloglu-Pazaryeri-Merkezi-Setup-10.2.0','Topaloglu-Pazaryeri-Merkezi-Setup-10.2.3').replace('Topaloglu-Pazaryeri-Merkezi-Setup-10.2.1','Topaloglu-Pazaryeri-Merkezi-Setup-10.2.3')
iss.write_text(s,encoding='utf-8')
(APP/'DESKTOP_VERSION.txt').write_text('10.2.3\n',encoding='utf-8')

# backend fixed ENV settings API with explicit known fields + existing keys
main=APP/'app/main.py'
s=main.read_text(encoding='utf-8')
if 'import os\n' not in s[:250]: s=s.replace('from pathlib import Path\n','from pathlib import Path\nimport os\n',1)
if 'import re\n' not in s[:300]: s=s.replace('import os\n','import os\nimport re\n',1)
block=r'''

# v10.2.3 desktop settings
_DESKTOP_SECRET=re.compile(r'(TOKEN|SECRET|PASSWORD|PASS|KEY|AUTH|BEARER)',re.I)
_DESKTOP_DEFAULT_KEYS=[
 'TSOFT_BASE_URL','TSOFT_TOKEN','TSOFT_USERNAME',
 'HEPSIBURADA_MERCHANT_ID','HEPSIBURADA_USERNAME','HEPSIBURADA_PASSWORD','HEPSIBURADA_SERVICE_KEY','HEPSIBURADA_MODE',
 'PAZARAMA_API_URL','PAZARAMA_TOKEN','PAZARAMA_REFRESH_TOKEN',
 'CONNECTPROF_ENABLED','CONNECTPROF_BASE_URL','CONNECTPROF_API_KEY','CONNECTPROF_BEARER_TOKEN','CONNECTPROF_PRODUCTS_PATH','CONNECTPROF_EXPORTS_PATH','CONNECTPROF_ORDERS_PATH',
 'ALERT_TOLERANCE_TL'
]
def _desktop_env_path_1023(): return Path.cwd()/'.env'
def _desktop_env_map_1023():
    p=_desktop_env_path_1023(); out={}
    if p.exists():
        for raw in p.read_text(encoding='utf-8-sig',errors='ignore').splitlines():
            st=raw.strip()
            if not st or st.startswith('#') or '=' not in st: continue
            k,v=st.split('=',1); k=k.strip(); v=v.strip().strip('"').strip("'")
            if k: out[k]=v
    return out
@app.get('/api/desktop/settings')
def desktop_settings_1023_get():
    vals=_desktop_env_map_1023(); keys=[]
    for k in _DESKTOP_DEFAULT_KEYS+list(vals.keys()):
        if k not in keys: keys.append(k)
    fields=[]
    for k in keys:
        secret=bool(_DESKTOP_SECRET.search(k)); v=vals.get(k,'')
        fields.append({'key':k,'configured':bool(v),'secret':secret,'value':'' if secret else v})
    return {'ok':True,'version':os.getenv('TOPOLOGLU_DESKTOP_VERSION','10.2.3'),'env_path':str(_desktop_env_path_1023()),'fields':fields}
@app.post('/api/desktop/settings')
def desktop_settings_1023_save(payload:dict=Body(...)):
    vals=_desktop_env_map_1023(); changes=payload.get('changes') or {}
    if not isinstance(changes,dict): raise HTTPException(400,'Ayar verisi geçersiz.')
    allowed=re.compile(r'^[A-Z0-9_]{2,80}$'); changed=[]
    for k,v in changes.items():
        k=str(k or '').strip().upper()
        if not allowed.match(k): continue
        v=str(v if v is not None else '').replace('\r','').replace('\n','').strip()
        if v=='': continue
        vals[k]=v; os.environ[k]=v; changed.append(k)
    p=_desktop_env_path_1023(); p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text('\n'.join(f'{k}={v}' for k,v in vals.items())+'\n',encoding='utf-8')
    return {'ok':True,'changed':changed,'restart_required':True,'env_path':str(p)}
'''
if '# v10.2.3 desktop settings' not in s:
    marker='@app.get("/api/update/check")'
    pos=s.find(marker)
    if pos<0: raise SystemExit('update endpoint marker missing')
    s=s[:pos]+block+'\n'+s[pos:]
main.write_text(s,encoding='utf-8')

# Direct HTML changes. No dynamic nav injection.
idx=APP/'app/static/index.html'
h=idx.read_text(encoding='utf-8')
h=h.replace('Pazaryeri Merkezi v10.1.2','Pazaryeri Merkezi <b id="desktopFixedVersion">v10.2.3</b>')
h=h.replace('<div class="update-pill" id="updatePill">','<div class="update-pill desktop-hidden" id="updatePill">',1)
nav_anchor='      <button class="nav" data-view="events"><i>◷</i> Olay Geçmişi</button>'
settings_nav='      <button class="nav" data-view="desktop-settings"><i>⚙</i> Ayarlar & Bağlantılar</button>'
if settings_nav not in h:
    if nav_anchor not in h: raise SystemExit('nav anchor missing')
    h=h.replace(nav_anchor,nav_anchor+'\n'+settings_nav,1)
settings_section=r'''
    <section id="view-desktop-settings" class="view">
      <section class="settings-desktop-shell">
        <article class="panel glass settings-desktop-head">
          <div><div class="section-kicker">MASAÜSTÜ AYARLARI</div><h2>Ayarlar & Bağlantılar</h2><p>.env bağlantı bilgilerini buradan yönetin. Gizli değerler ekranda gösterilmez.</p></div>
          <div class="desktop-version-card"><span>SÜRÜM</span><strong>v10.2.3</strong></div>
        </article>
        <article class="panel glass">
          <div class="panel-head"><div><h2>Bağlantı Anahtarları</h2><p>Boş görünen gizli alan kayıtlı olabilir. Değiştirmek için yeni değeri yazın.</p></div><button id="desktopSettingsReload" class="btn ghost">Yenile</button></div>
          <div id="desktopEnvPath" class="desktop-env-path">ENV konumu yükleniyor…</div>
          <div id="desktopSettingsFields" class="desktop-settings-fields"></div>
          <div class="desktop-settings-actions"><button id="desktopSettingsSave" class="btn primary">Ayarları Kaydet</button></div>
          <div class="desktop-settings-note">Kaydetme sonrası uygulamayı kapatıp tekrar açın.</div>
        </article>
      </section>
    </section>
'''
if 'id="view-desktop-settings"' not in h:
    marker='    <section id="view-events" class="view">'
    pos=h.find(marker)
    if pos<0: raise SystemExit('events view anchor missing')
    h=h[:pos]+settings_section+'\n'+h[pos:]
if '/static/desktop_settings.js?v=10.2.3' not in h:
    h=h.replace('</body>','<script src="/static/desktop_settings.js?v=10.2.3"></script>\n</body>',1)
idx.write_text(h,encoding='utf-8')

js=r'''(function(){
const $=s=>document.querySelector(s);
const esc=v=>String(v??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]));
async function api(url,opt){const r=await fetch(url,opt);let j={};try{j=await r.json()}catch(e){}if(!r.ok)throw new Error(j.detail||'İşlem başarısız');return j}
async function loadSettings(){
 const d=await api('/api/desktop/settings');
 const p=$('#desktopEnvPath');if(p)p.textContent='ENV konumu: '+d.env_path;
 const box=$('#desktopSettingsFields');if(!box)return;
 box.innerHTML=(d.fields||[]).map(f=>`<div class="desktop-setting-row" data-key="${esc(f.key)}"><div><b>${esc(f.key)}</b><small>${f.secret?'Gizli değer':f.configured?'Kayıtlı':'Henüz girilmedi'}</small></div><input class="desktop-setting-input" type="${f.secret?'password':'text'}" value="${esc(f.value||'')}" placeholder="${f.secret&&f.configured?'Kayıtlı — değiştirmek için yeni değer yaz':'Değer girin'}"><span class="desktop-setting-state ${f.configured?'ok':''}">${f.configured?'Kayıtlı':'Boş'}</span></div>`).join('');
}
async function saveSettings(){
 const changes={};document.querySelectorAll('.desktop-setting-row').forEach(r=>{const v=r.querySelector('input').value;if(v!=='')changes[r.dataset.key]=v});
 const b=$('#desktopSettingsSave');b.disabled=true;b.textContent='Kaydediliyor…';
 try{const d=await api('/api/desktop/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({changes})});alert((d.changed||[]).length+' ayar kaydedildi. Uygulamayı kapatıp tekrar açın.');await loadSettings()}catch(e){alert('Kaydetme başarısız: '+e.message)}finally{b.disabled=false;b.textContent='Ayarları Kaydet'}
}
function bind(){
 const nav=document.querySelector('[data-view="desktop-settings"]');
 if(nav)nav.addEventListener('click',()=>setTimeout(loadSettings,50));
 $('#desktopSettingsReload')?.addEventListener('click',loadSettings);
 $('#desktopSettingsSave')?.addEventListener('click',saveSettings);
 const fixed=$('#desktopFixedVersion');if(fixed)fixed.textContent='v10.2.3';
 const pill=$('#updatePill');if(pill)pill.style.display='none';
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',bind);else bind();
})();'''
(APP/'app/static/desktop_settings.js').write_text(js,encoding='utf-8')

css=APP/'app/static/style.css'
cs=css.read_text(encoding='utf-8')
cs += r'''
.desktop-hidden{display:none!important}.settings-desktop-shell{display:grid;gap:18px}.settings-desktop-head{display:flex;justify-content:space-between;align-items:center;padding:24px}.desktop-version-card{text-align:right}.desktop-version-card span{display:block;font-size:11px;color:#8e98a8;letter-spacing:.12em}.desktop-version-card strong{font-size:24px}.desktop-env-path{padding:11px 13px;border-radius:10px;background:rgba(255,255,255,.03);color:#8f98a8;font-size:12px;margin-bottom:14px}.desktop-settings-fields{display:grid;gap:9px}.desktop-setting-row{display:grid;grid-template-columns:minmax(240px,1fr) minmax(300px,1.5fr) 90px;gap:12px;align-items:center;padding:12px 14px;border:1px solid rgba(255,255,255,.07);border-radius:12px;background:rgba(255,255,255,.025)}.desktop-setting-row b{display:block;font-size:13px}.desktop-setting-row small{display:block;margin-top:3px;color:#7f8999}.desktop-setting-input{width:100%;box-sizing:border-box;border:1px solid rgba(255,255,255,.1);background:#0b0f17;color:#eef2f7;border-radius:9px;padding:10px 11px}.desktop-setting-state{text-align:center;font-size:11px;color:#8993a3}.desktop-setting-state.ok{color:#69d9a2}.desktop-settings-actions{display:flex;justify-content:flex-end;margin-top:16px}.desktop-settings-note{margin-top:12px;padding:12px 14px;border-radius:10px;background:rgba(201,168,76,.06);color:#c9b97c;font-size:12px}@media(max-width:900px){.desktop-setting-row{grid-template-columns:1fr}.desktop-setting-state{text-align:left}}
'''
css.write_text(cs,encoding='utf-8')

# assertions
assert 'v10.2.3' in idx.read_text(encoding='utf-8')
assert 'Ayarlar & Bağlantılar' in idx.read_text(encoding='utf-8')
assert '/api/desktop/settings' in main.read_text(encoding='utf-8')
assert (APP/'app/static/desktop_settings.js').exists()
print(APP)
