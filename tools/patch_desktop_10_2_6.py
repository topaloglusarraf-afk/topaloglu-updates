from pathlib import Path
import re

ROOT=Path('_desktop_src')
apps=[p for p in ROOT.iterdir() if p.is_dir() and (p/'app').is_dir()]
if not apps: raise SystemExit('desktop source root not found')
APP=apps[0]

# version
launcher=APP/'desktop_launcher.py'
s=launcher.read_text(encoding='utf-8')
s=s.replace('VERSION = "10.2.5"','VERSION = "10.2.6"')
# Backward compatibility: current HB connector expects PASSWORD; current panel may only expose service key.
needle='    load_env_file(d / ".env")\n'
compat='    load_env_file(d / ".env")\n    if os.environ.get("HEPSIBURADA_SERVICE_KEY") and not os.environ.get("HEPSIBURADA_PASSWORD"):\n        os.environ["HEPSIBURADA_PASSWORD"] = os.environ["HEPSIBURADA_SERVICE_KEY"]\n'
if compat not in s:
    if needle not in s: raise SystemExit('launcher env marker missing')
    s=s.replace(needle,compat,1)
launcher.write_text(s,encoding='utf-8')

iss=APP/'desktop_installer.iss'
s=iss.read_text(encoding='utf-8')
s=s.replace('#define MyAppVersion "10.2.5"','#define MyAppVersion "10.2.6"')
s=s.replace('Topaloglu-Pazaryeri-Merkezi-Setup-10.2.5','Topaloglu-Pazaryeri-Merkezi-Setup-10.2.6')
iss.write_text(s,encoding='utf-8')
(APP/'DESKTOP_VERSION.txt').write_text('10.2.6\n',encoding='utf-8')

# backend: simplified HB credentials + direct connectivity test
main=APP/'app/main.py'
s=main.read_text(encoding='utf-8')
if 'import httpx\n' not in s[:600]:
    insert='from pathlib import Path\n'
    if insert in s: s=s.replace(insert,insert+'import httpx\n',1)
    else: s='import httpx\n'+s

block=r'''

# v10.2.6 Hepsiburada simplified connection settings

def _write_desktop_env_1026(changes):
    vals=_desktop_env_map_1023()
    for k,v in changes.items():
        if v is None: continue
        vals[k]=str(v).strip()
        os.environ[k]=str(v).strip()
    p=_desktop_env_path_1023(); p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text('\n'.join(f'{k}={v}' for k,v in vals.items())+'\n',encoding='utf-8')
    return p

@app.get('/api/hepsiburada/settings')
def hepsiburada_settings_1026_get():
    vals=_desktop_env_map_1023()
    secret=vals.get('HEPSIBURADA_SERVICE_KEY') or vals.get('HEPSIBURADA_PASSWORD') or ''
    return {
      'ok':True,
      'merchant_id':vals.get('HEPSIBURADA_MERCHANT_ID',''),
      'username':vals.get('HEPSIBURADA_USERNAME',''),
      'secret_configured':bool(secret),
      'mode':vals.get('HEPSIBURADA_MODE','api') or 'api',
      'enabled':str(vals.get('HEPSIBURADA_ENABLED','true')).lower() not in ('0','false','no','off')
    }

@app.post('/api/hepsiburada/settings')
def hepsiburada_settings_1026_save(payload:dict=Body(...)):
    merchant=str(payload.get('merchant_id') or '').strip()
    username=str(payload.get('username') or '').strip()
    secret=str(payload.get('secret') or '').strip()
    vals=_desktop_env_map_1023()
    if not merchant: merchant=vals.get('HEPSIBURADA_MERCHANT_ID','')
    if not username: username=vals.get('HEPSIBURADA_USERNAME','')
    existing_secret=vals.get('HEPSIBURADA_SERVICE_KEY') or vals.get('HEPSIBURADA_PASSWORD') or ''
    if not secret: secret=existing_secret
    changes={
      'HEPSIBURADA_MERCHANT_ID':merchant,
      'HEPSIBURADA_USERNAME':username,
      'HEPSIBURADA_MODE':'api',
      'HEPSIBURADA_ENABLED':'true'
    }
    if secret:
      # new auth UI uses one secret; keep legacy PASSWORD in sync for current connector compatibility
      changes['HEPSIBURADA_SERVICE_KEY']=secret
      changes['HEPSIBURADA_PASSWORD']=secret
    p=_write_desktop_env_1026(changes)
    return {'ok':True,'restart_required':True,'env_path':str(p),'secret_configured':bool(secret)}

@app.post('/api/hepsiburada/test-connection')
async def hepsiburada_test_connection_1026():
    vals=_desktop_env_map_1023()
    merchant=vals.get('HEPSIBURADA_MERCHANT_ID','').strip()
    username=vals.get('HEPSIBURADA_USERNAME','').strip()
    secret=(vals.get('HEPSIBURADA_SERVICE_KEY') or vals.get('HEPSIBURADA_PASSWORD') or '').strip()
    missing=[]
    if not merchant: missing.append('Mağaza ID')
    if not username: missing.append('API/Entegratör Kullanıcı Adı')
    if not secret: missing.append('Servis Anahtarı / API Şifresi')
    if missing:
        raise HTTPException(400,'Eksik bilgi: '+', '.join(missing))
    url=f'https://listing-external.hepsiburada.com/listings/merchantid/{merchant}'
    headers={'Accept':'application/json','Content-Type':'application/json','User-Agent':f'TopalogluFiyatKoruma/10.2.6 ({merchant})'}
    try:
        async with httpx.AsyncClient(timeout=15.0,auth=(username,secret),headers=headers) as client:
            r=await client.get(url,params={'offset':0,'limit':1})
        if r.status_code==200:
            return {'ok':True,'status':200,'message':'Hepsiburada bağlantısı başarılı.'}
        if r.status_code==401:
            raise HTTPException(401,'Hepsiburada kimlik doğrulamayı reddetti. Kullanıcı adı / servis anahtarını kontrol edin.')
        if r.status_code==403:
            raise HTTPException(403,'Kimlik bilgisi kabul edildi ancak Listing servisi için yetki verilmemiş olabilir.')
        raise HTTPException(r.status_code,f'Hepsiburada HTTP {r.status_code} döndürdü.')
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502,'Hepsiburada bağlantı testi başarısız: '+str(e))
'''
if '# v10.2.6 Hepsiburada simplified connection settings' not in s:
    marker='@app.get("/api/update/check")'
    pos=s.find(marker)
    if pos<0: raise SystemExit('main update endpoint marker missing')
    s=s[:pos]+block+'\n'+s[pos:]
main.write_text(s,encoding='utf-8')

# dedicated HB settings UI, hide obsolete raw HB env rows
idx=APP/'app/static/index.html'
h=idx.read_text(encoding='utf-8')
h=h.replace('v10.2.5','v10.2.6')
h=re.sub(r'/static/style\.css(?:\?v=[^"\']*)?', '/static/style.css?v=10.2.6', h)
h=re.sub(r'/static/app\.js(?:\?v=[^"\']*)?', '/static/app.js?v=10.2.6', h)
h=re.sub(r'/static/desktop_settings\.js(?:\?v=[^"\']*)?', '/static/desktop_settings.js?v=10.2.6', h)
h=re.sub(r'/static/mete_boot\.js(?:\?v=[^"\']*)?', '/static/mete_boot.js?v=10.2.6', h)
if '/static/hepsiburada_settings.js?v=10.2.6' not in h:
    h=h.replace('</body>','<script src="/static/hepsiburada_settings.js?v=10.2.6"></script>\n</body>',1)
idx.write_text(h,encoding='utf-8')

hbjs=r'''(function(){
const q=s=>document.querySelector(s);
async function api(u,o){const r=await fetch(u,o);let j={};try{j=await r.json()}catch(_){}if(!r.ok)throw new Error(j.detail||'İşlem başarısız');return j}
function hideRaw(){document.querySelectorAll('.desktop-setting-row').forEach(r=>{const k=r.dataset.key||'';if(k.startsWith('HEPSIBURADA_'))r.style.display='none'})}
async function loadHB(){
 const host=q('#desktopSettingsFields');if(!host)return;
 hideRaw();
 let card=q('#hbSettings1026');
 if(!card){card=document.createElement('section');card.id='hbSettings1026';card.className='hb1026-card';host.parentElement.insertBefore(card,host);}
 try{
  const d=await api('/api/hepsiburada/settings');
  card.innerHTML=`<div class="hb1026-head"><div><span>HEPSİBURADA</span><h3>Doğrudan API Bağlantısı</h3><p>Hepsiburada için aynı bilgiyi iki farklı alana girmeniz gerekmez.</p></div><div class="hb1026-state ${d.secret_configured?'ok':''}">${d.secret_configured?'Bilgiler kayıtlı':'Kurulum gerekli'}</div></div>
  <div class="hb1026-grid"><label><span>Mağaza ID / Merchant ID</span><input id="hbMerchant1026" value="${esc(d.merchant_id||'')}" placeholder="Hepsiburada mağaza kimliği"></label><label><span>API / Entegratör Kullanıcı Adı</span><input id="hbUser1026" value="${esc(d.username||'')}" placeholder="API kullanıcı adı"></label><label><span>Servis Anahtarı / API Şifresi</span><input id="hbSecret1026" type="password" value="" placeholder="${d.secret_configured?'Kayıtlı — değiştirmek için yeni değer yaz':'Servis anahtarını gir'}"></label></div>
  <div class="hb1026-help">Satıcı panelinde yeni entegratör yapısını kullanıyorsanız <b>Bilgilerim → Entegrasyon → Entegratör Bilgileri → Servis Anahtarı</b> bölümündeki değeri kullanın. Normal satıcı giriş şifrenizi girmeyin.</div>
  <div class="hb1026-actions"><button id="hbSave1026" class="btn primary">Hepsiburada Ayarlarını Kaydet</button><button id="hbTest1026" class="btn ghost">Bağlantıyı Test Et</button><span id="hbResult1026"></span></div>`;
  q('#hbSave1026').onclick=saveHB;q('#hbTest1026').onclick=testHB;
 }catch(e){card.innerHTML='<div class="hb1026-help">Hepsiburada ayarları yüklenemedi: '+esc(e.message)+'</div>'}
}
function esc(v){return String(v??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]))}
async function saveHB(){
 const b=q('#hbSave1026');b.disabled=true;b.textContent='Kaydediliyor…';
 try{await api('/api/hepsiburada/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({merchant_id:q('#hbMerchant1026').value,username:q('#hbUser1026').value,secret:q('#hbSecret1026').value})});q('#hbResult1026').textContent='Kaydedildi. Uygulamayı yeniden başlatın.';await loadHB()}catch(e){q('#hbResult1026').textContent='Kaydetme başarısız: '+e.message}finally{b.disabled=false;b.textContent='Hepsiburada Ayarlarını Kaydet'}
}
async function testHB(){const b=q('#hbTest1026');const out=q('#hbResult1026');b.disabled=true;b.textContent='Test ediliyor…';out.textContent='';try{const d=await api('/api/hepsiburada/test-connection',{method:'POST'});out.textContent='✓ '+d.message;out.className='hb1026-result ok'}catch(e){out.textContent='✕ '+e.message;out.className='hb1026-result error'}finally{b.disabled=false;b.textContent='Bağlantıyı Test Et'}}
function boot(){const nav=document.querySelector('[data-view="desktop-settings"]');if(nav)nav.addEventListener('click',()=>setTimeout(loadHB,120));const mo=new MutationObserver(()=>hideRaw());const host=q('#desktopSettingsFields');if(host)mo.observe(host,{childList:true,subtree:true});}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();'''
(APP/'app/static/hepsiburada_settings.js').write_text(hbjs,encoding='utf-8')

css=APP/'app/static/style.css'
cs=css.read_text(encoding='utf-8')
cs += r'''

/* v10.2.6 Hepsiburada connection card */
.hb1026-card{margin:0 0 16px;padding:20px;border:1px solid rgba(255,126,27,.18);border-radius:16px;background:linear-gradient(145deg,rgba(43,24,10,.44),rgba(13,16,22,.92));box-shadow:0 14px 40px rgba(0,0,0,.13)}.hb1026-head{display:flex;justify-content:space-between;gap:18px;align-items:flex-start}.hb1026-head span{font-size:9px;letter-spacing:.16em;color:#ff9a47;font-weight:800}.hb1026-head h3{margin:4px 0 5px;font-size:20px}.hb1026-head p{margin:0;color:#8d97a8;font-size:12px}.hb1026-state{font-size:11px;padding:7px 10px;border-radius:999px;background:rgba(255,255,255,.06);color:#9ba5b5}.hb1026-state.ok{background:rgba(87,217,155,.1);color:#72dda9}.hb1026-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:17px}.hb1026-grid label span{display:block;margin:0 0 6px;color:#9aa5b5;font-size:11px}.hb1026-grid input{width:100%;box-sizing:border-box}.hb1026-help{margin-top:13px;padding:11px 12px;border-radius:10px;background:rgba(255,255,255,.025);color:#8d98a8;font-size:11.5px;line-height:1.55}.hb1026-help b{color:#d6dde8}.hb1026-actions{display:flex;align-items:center;gap:9px;margin-top:14px}.hb1026-result{font-size:11px;color:#a0a9b8}.hb1026-result.ok{color:#6fdca7}.hb1026-result.error{color:#ff7b82}@media(max-width:980px){.hb1026-grid{grid-template-columns:1fr}.hb1026-actions{flex-wrap:wrap}}
'''
css.write_text(cs,encoding='utf-8')

# validate
assert '/api/hepsiburada/settings' in main.read_text(encoding='utf-8')
assert '/api/hepsiburada/test-connection' in main.read_text(encoding='utf-8')
assert (APP/'app/static/hepsiburada_settings.js').exists()
print(APP)
