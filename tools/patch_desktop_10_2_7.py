from pathlib import Path
import re

ROOT=Path('_desktop_src')
apps=[p for p in ROOT.iterdir() if p.is_dir() and (p/'app').is_dir()]
if not apps: raise SystemExit('desktop source root not found')
APP=apps[0]

# version + force extension mode on desktop
launcher=APP/'desktop_launcher.py'
s=launcher.read_text(encoding='utf-8')
s=s.replace('VERSION = "10.2.6"','VERSION = "10.2.7"')
needle='    os.environ["TOPOLOGLU_DESKTOP_VERSION"] = VERSION\n'
add='    os.environ["TOPOLOGLU_DESKTOP_VERSION"] = VERSION\n    # Hepsiburada desktop mode: read-only seller-panel bridge; never impersonate another integrator.\n    os.environ["HEPSIBURADA_MODE"] = "extension"\n'
if add not in s:
    if needle not in s: raise SystemExit('launcher version env marker missing')
    s=s.replace(needle,add,1)
launcher.write_text(s,encoding='utf-8')

iss=APP/'desktop_installer.iss'
s=iss.read_text(encoding='utf-8')
s=s.replace('#define MyAppVersion "10.2.6"','#define MyAppVersion "10.2.7"')
s=s.replace('Topaloglu-Pazaryeri-Merkezi-Setup-10.2.6','Topaloglu-Pazaryeri-Merkezi-Setup-10.2.7')
iss.write_text(s,encoding='utf-8')
(APP/'DESKTOP_VERSION.txt').write_text('10.2.7\n',encoding='utf-8')

# backend bridge status/open-folder and stale API cleanup
main=APP/'app/main.py'
s=main.read_text(encoding='utf-8')
if 'import sys\n' not in s[:800]:
    s=s.replace('import os\n','import os\nimport sys\nimport subprocess\n',1)

# extend startup with one-time HB cleanup
startup_marker='    if purged:\n        db.log("INFO",f"ET kuralı: {purged} eski ET dışı ürün tamamen temizlendi.","Sistem")\n'
startup_add=startup_marker+'    # v10.2.7: direct API credentials may belong to an external integrator; switch to local seller-panel bridge.\n    if db.runtime_all().get("hb_extension_migration_1027") != "1":\n        db.clear_market("Hepsiburada")\n        db.runtime_set("hb_extension_migration_1027","1")\n        db.log("INFO","Hepsiburada satıcı paneli bağlantı moduna geçirildi; eski API kayıtları temizlendi.","Hepsiburada")\n'
if 'hb_extension_migration_1027' not in s:
    if startup_marker not in s: raise SystemExit('startup HB migration marker missing')
    s=s.replace(startup_marker,startup_add,1)

# Replace old static extension status endpoint with richer status/open folder.
old='''@app.get("/api/hepsiburada/extension/status")\nasync def hepsiburada_extension_status():\n    return {"ok":True,"version":"10.0.2","message":"Chrome eklentisi bağlantısı hazır."}\n'''
new='''@app.get("/api/hepsiburada/extension/status")\nasync def hepsiburada_extension_status():\n    rt=db.runtime_all()\n    return {\n      "ok":True,"version":"10.2.7","mode":"extension",\n      "message":"Hepsiburada satıcı paneli bağlantısı hazır.",\n      "last_import_at":rt.get("Hepsiburada_extension_last_import_at"),\n      "last_import_count":int(rt.get("Hepsiburada_extension_last_import_count") or 0),\n      "last_saved":int(rt.get("Hepsiburada_extension_last_saved") or 0)\n    }\n\ndef _hb_extension_dir_1027():\n    if getattr(sys,"frozen",False):\n        return Path(sys.executable).resolve().parent / "chrome-extension"\n    return Path(__file__).resolve().parent.parent / "chrome-extension"\n\n@app.post("/api/hepsiburada/extension/open-folder")\ndef hepsiburada_extension_open_folder_1027():\n    p=_hb_extension_dir_1027()\n    if not p.exists(): raise HTTPException(404,"Chrome eklenti klasörü bulunamadı.")\n    if os.name=="nt":\n        subprocess.Popen(["explorer",str(p)])\n    return {"ok":True,"path":str(p)}\n'''
if old in s:
    s=s.replace(old,new,1)
elif 'def _hb_extension_dir_1027' not in s:
    pos=s.find('@app.post("/api/hepsiburada/extension/import")')
    if pos<0: raise SystemExit('extension import endpoint missing')
    s=s[:pos]+new+'\n'+s[pos:]

# add import timestamp
needle='    db.runtime_set("Hepsiburada_extension_last_import_count",len(rows)); db.runtime_set("Hepsiburada_extension_last_saved",saved)\n'
repl='    db.runtime_set("Hepsiburada_extension_last_import_count",len(rows)); db.runtime_set("Hepsiburada_extension_last_saved",saved); db.runtime_set("Hepsiburada_extension_last_import_at",service.now())\n'
if needle in s: s=s.replace(needle,repl,1)
main.write_text(s,encoding='utf-8')

# service: extension mode must never fall through to direct API
service=APP/'app/service.py'
sv=service.read_text(encoding='utf-8')
# run_marketplace_only
old='''    if name=="Hepsiburada" and (getattr(settings,"hepsiburada_mode","web") or "web").lower()=="web":\n        return await check_hepsiburada_web()\n    return await check_marketplace(name,fetcher)\n'''
new='''    if name=="Hepsiburada":\n        mode=(getattr(settings,"hepsiburada_mode","extension") or "extension").lower()\n        if mode=="extension":\n            rt=db.runtime_all()\n            return {"mode":"extension","message":"Chrome satıcı paneli bağlantısı bekleniyor/aktif.","last_import_at":rt.get("Hepsiburada_extension_last_import_at"),"last_saved":int(rt.get("Hepsiburada_extension_last_saved") or 0)}\n        if mode=="web":\n            return await check_hepsiburada_web()\n    return await check_marketplace(name,fetcher)\n'''
if old not in sv: raise SystemExit('run_marketplace_only pattern missing')
sv=sv.replace(old,new,1)

# run_cycle block
old='''            if name=="Hepsiburada" and (getattr(settings,"hepsiburada_mode","web") or "web").lower()=="web":\n                result["markets"][name]=await check_hepsiburada_web()\n            else:\n                result["markets"][name]=await check_marketplace(name,fetcher)\n'''
new='''            if name=="Hepsiburada":\n                mode=(getattr(settings,"hepsiburada_mode","extension") or "extension").lower()\n                if mode=="extension":\n                    rt=db.runtime_all()\n                    result["markets"][name]={"mode":"extension","last_import_at":rt.get("Hepsiburada_extension_last_import_at"),"last_saved":int(rt.get("Hepsiburada_extension_last_saved") or 0)}\n                    continue\n                if mode=="web":\n                    result["markets"][name]=await check_hepsiburada_web()\n                    continue\n            result["markets"][name]=await check_marketplace(name,fetcher)\n'''
if old not in sv: raise SystemExit('run_cycle pattern missing')
sv=sv.replace(old,new,1)

# single product: don't call direct API in extension mode
old='''        try:\n            if name=="Hepsiburada" and (getattr(settings,"hepsiburada_mode","web") or "web").lower()=="web":\n                row=await check_hepsiburada_web_single(target)\n            else:\n                rows=await fetcher()\n'''
new='''        try:\n            if name=="Hepsiburada":\n                mode=(getattr(settings,"hepsiburada_mode","extension") or "extension").lower()\n                if mode=="extension":\n                    existing=[x for x in db.list_checks() if x.get("marketplace")=="Hepsiburada" and x.get("product_code")==target.get("product_code")]\n                    if existing:\n                        row=existing[0]\n                        result["markets"][name]={"status":row.get("status"),"marketplace":name,"current_price":row.get("current_price"),"current_stock":row.get("current_stock"),"match_method":row.get("match_method"),"marketplace_sku":row.get("marketplace_sku"),"marketplace_title":row.get("marketplace_title"),"net_margin":row.get("net_margin"),"difference":row.get("difference"),"error":row.get("error")}\n                    else:\n                        result["markets"][name]={"status":"REVIEW","marketplace":name,"error":"Hepsiburada satıcı panelinde ürün listesini açın; Chrome eklentisi fiyatı yerel uygulamaya aktaracaktır."}\n                    continue\n                if mode=="web":\n                    row=await check_hepsiburada_web_single(target)\n                else:\n                    rows=await fetcher()\n                    db.replace_catalog(name,rows)\n                    idx=make_indexes(rows)\n                    market_row,method=match_product(target,idx,name,rows)\n                    row=base_row(target,None,None,name,"UNRESOLVED","Güvenli eşleşme bulunamadı.") if not market_row else evaluate(target,market_row,method,name)\n            else:\n                rows=await fetcher()\n'''
if old not in sv: raise SystemExit('single product pattern missing')
sv=sv.replace(old,new,1)
service.write_text(sv,encoding='utf-8')

# Chrome extension files
EXT=APP/'chrome-extension'; EXT.mkdir(exist_ok=True)
manifest=r'''{
  "manifest_version": 3,
  "name": "Topaloğlu Hepsiburada Köprüsü",
  "version": "1.0.0",
  "description": "Hepsiburada satıcı panelindeki ürün fiyat/stok verisini yalnız yerel Topaloğlu uygulamasına aktarır.",
  "permissions": ["storage"],
  "host_permissions": [
    "https://merchant.hepsiburada.com/*",
    "https://*.hepsiburada.com/*",
    "http://127.0.0.1:8765/*","http://127.0.0.1:8766/*","http://127.0.0.1:8767/*","http://127.0.0.1:8768/*","http://127.0.0.1:8877/*"
  ],
  "background": {"service_worker": "background.js"},
  "content_scripts": [
    {"matches":["https://merchant.hepsiburada.com/*"],"js":["main_hook.js"],"run_at":"document_start","world":"MAIN"},
    {"matches":["https://merchant.hepsiburada.com/*"],"js":["content.js"],"run_at":"document_start"}
  ],
  "action": {"default_popup":"popup.html","default_title":"Topaloğlu Hepsiburada Köprüsü"}
}'''
(EXT/'manifest.json').write_text(manifest,encoding='utf-8')

main_hook=r'''(()=>{
  if(window.__TOPOLOGLU_HB_HOOK__)return; window.__TOPOLOGLU_HB_HOOK__=true;
  const num=v=>{if(v==null)return null;if(typeof v==='object'){for(const k of ['amount','value','price'])if(v[k]!=null)return num(v[k]);return null;}const n=Number(String(v).replace(/\./g,'').replace(',','.').replace(/[^0-9.-]/g,''));return Number.isFinite(n)?n:null};
  const val=(o,keys)=>{for(const k of keys)if(o&&o[k]!=null&&o[k]!=='' )return o[k];return null};
  const clean=o=>{
    if(!o||typeof o!=='object'||Array.isArray(o))return null;
    const sku=val(o,['merchantSku','merchantSKU','merchant_sku','merchantSkuId','stockCode','merchantStockCode','sku']);
    const barcode=val(o,['barcode','barCode','merchantBarcode','gtin','ean']);
    const title=val(o,['productName','productTitle','listingName','title','name']);
    const price=num(val(o,['price','salePrice','listingPrice','currentPrice','finalPrice','offerPrice']));
    const stock=num(val(o,['availableStock','stock','quantity','merchantStock','inventory','availableQuantity']));
    const ident=String(sku||barcode||title||'');
    if(price==null||price<=0||!ident)return null;
    if(!/ET/i.test(String(sku||''))&&!/ET/i.test(String(barcode||''))&&!/ET/i.test(String(title||'')))return null;
    return {stock_code:String(sku||''),barcode:String(barcode||''),title:String(title||''),price,stock:stock==null?1:stock};
  };
  const extract=root=>{const out=[],seenObj=new WeakSet(),seenRow=new Set();let count=0;function walk(x,d){if(!x||d>9||count>25000)return;if(typeof x!=='object')return;if(seenObj.has(x))return;seenObj.add(x);count++;const r=clean(x);if(r){const k=[r.stock_code,r.barcode,r.title,r.price,r.stock].join('|');if(!seenRow.has(k)){seenRow.add(k);out.push(r)}}if(Array.isArray(x)){for(const v of x)walk(v,d+1)}else{for(const [k,v] of Object.entries(x)){if(/token|cookie|password|authorization|secret/i.test(k))continue;walk(v,d+1)}}}walk(root,0);return out.slice(0,500)};
  const emit=(data,url)=>{try{const rows=extract(data);if(rows.length)window.postMessage({source:'TOPOLOGLU_HB_BRIDGE',type:'ROWS',rows,url:String(url||'')},'*')}catch(_){}};
  const full=u=>{try{return new URL(String(u||''),location.href).href}catch(_){return String(u||'')}};
  const interesting=u=>{const x=full(u).toLowerCase();return x.includes('hepsiburada')||x.startsWith(location.origin.toLowerCase())||x.startsWith('/')};
  const ofetch=window.fetch;window.fetch=async function(...args){const res=await ofetch.apply(this,args);try{const url=full(args[0]?.url||args[0]);if(interesting(url)){const c=res.clone();const ct=c.headers.get('content-type')||'';if(ct.includes('json'))c.json().then(j=>emit(j,url)).catch(()=>{});else c.text().then(t=>{if(t&&t[0]&&'[{'.includes(t.trim()[0]))try{emit(JSON.parse(t),url)}catch(_){}}).catch(()=>{})}}catch(_){}return res};
  const XO=XMLHttpRequest.prototype.open, XS=XMLHttpRequest.prototype.send;XMLHttpRequest.prototype.open=function(m,u,...rest){this.__topaloglu_url=full(u);return XO.call(this,m,u,...rest)};XMLHttpRequest.prototype.send=function(...args){this.addEventListener('load',()=>{try{if(!interesting(this.__topaloglu_url))return;let d=this.response;if(this.responseType===''||this.responseType==='text'){const t=String(this.responseText||'').trim();if(t&&'[{'.includes(t[0]))d=JSON.parse(t)}if(this.responseType==='json'||typeof d==='object')emit(d,this.__topaloglu_url)}catch(_){}});return XS.apply(this,args)};
})();'''
(EXT/'main_hook.js').write_text(main_hook,encoding='utf-8')

content=r'''(()=>{if(window.__TOPOLOGLU_HB_CONTENT__)return;window.__TOPOLOGLU_HB_CONTENT__=true;window.addEventListener('message',e=>{if(e.source!==window||!e.data||e.data.source!=='TOPOLOGLU_HB_BRIDGE'||e.data.type!=='ROWS')return;const rows=Array.isArray(e.data.rows)?e.data.rows.slice(0,500):[];if(rows.length)chrome.runtime.sendMessage({type:'HB_ROWS',rows}).catch(()=>{})});})();'''
(EXT/'content.js').write_text(content,encoding='utf-8')

background=r'''const PORTS=[8765,8766,8767,8768,8877];let buffer=[],timer=null;
async function findApp(){for(const p of PORTS){try{const r=await fetch(`http://127.0.0.1:${p}/api/hepsiburada/extension/status`,{cache:'no-store'});if(r.ok)return p}catch(_){}}return null}
function dedupe(rows){const out=[],s=new Set();for(const r of rows){const k=[r.stock_code,r.barcode,r.title,r.price,r.stock].join('|');if(!s.has(k)){s.add(k);out.push(r)}}return out.slice(0,500)}
async function flush(){timer=null;const rows=dedupe(buffer);buffer=[];if(!rows.length)return;const port=await findApp();if(!port){await chrome.storage.local.set({hbStatus:{ok:false,message:'Topaloğlu uygulaması bulunamadı.',at:new Date().toISOString()}});chrome.action.setBadgeText({text:'!'});return}try{const r=await fetch(`http://127.0.0.1:${port}/api/hepsiburada/extension/import`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({rows})});const j=await r.json();if(!r.ok)throw new Error(j.detail||'Aktarım başarısız');await chrome.storage.local.set({hbStatus:{ok:true,message:`${j.saved||0} ürün aktarıldı`,saved:j.saved||0,matched:j.matched||0,at:new Date().toISOString(),port}});chrome.action.setBadgeBackgroundColor({color:'#2f9e68'});chrome.action.setBadgeText({text:String(Math.min(99,j.saved||0))})}catch(e){await chrome.storage.local.set({hbStatus:{ok:false,message:String(e.message||e),at:new Date().toISOString()}});chrome.action.setBadgeText({text:'!'})}}
chrome.runtime.onMessage.addListener(msg=>{if(msg?.type==='HB_ROWS'&&Array.isArray(msg.rows)){buffer.push(...msg.rows);if(!timer)timer=setTimeout(flush,900)}});
chrome.runtime.onInstalled.addListener(()=>chrome.storage.local.set({hbStatus:{ok:false,message:'Hepsiburada satıcı panelini açın.',at:new Date().toISOString()}}));'''
(EXT/'background.js').write_text(background,encoding='utf-8')

popup='''<!doctype html><html><head><meta charset="utf-8"><style>body{width:290px;background:#0b1017;color:#e8edf4;font:13px Segoe UI;margin:0;padding:16px}b{color:#f0c66b}#s{margin-top:10px;padding:10px;border:1px solid #27313d;border-radius:10px;color:#9eabb9}.ok{color:#64d49b!important}</style></head><body><b>Topaloğlu Hepsiburada Köprüsü</b><div id="s">Durum yükleniyor…</div><script src="popup.js"></script></body></html>'''
(EXT/'popup.html').write_text(popup,encoding='utf-8')
(EXT/'popup.js').write_text("chrome.storage.local.get('hbStatus',x=>{const s=document.getElementById('s'),d=x.hbStatus||{};s.textContent=d.message||'Hepsiburada satıcı panelini açın.';if(d.ok)s.className='ok';});",encoding='utf-8')

# UI: remove direct API script and add extension bridge setup card
idx=APP/'app/static/index.html'
h=idx.read_text(encoding='utf-8')
h=h.replace('v10.2.6','v10.2.7')
h=re.sub(r'<script src="/static/hepsiburada_settings\.js\?v=[^"]+"></script>\s*','',h)
h=re.sub(r'/static/style\.css(?:\?v=[^"\']*)?', '/static/style.css?v=10.2.7', h)
h=re.sub(r'/static/app\.js(?:\?v=[^"\']*)?', '/static/app.js?v=10.2.7', h)
h=re.sub(r'/static/desktop_settings\.js(?:\?v=[^"\']*)?', '/static/desktop_settings.js?v=10.2.7', h)
h=re.sub(r'/static/mete_boot\.js(?:\?v=[^"\']*)?', '/static/mete_boot.js?v=10.2.7', h)
if '/static/hepsiburada_bridge.js?v=10.2.7' not in h:h=h.replace('</body>','<script src="/static/hepsiburada_bridge.js?v=10.2.7"></script>\n</body>',1)
idx.write_text(h,encoding='utf-8')

bridge=r'''(function(){const q=s=>document.querySelector(s);async function api(u,o){const r=await fetch(u,o);let j={};try{j=await r.json()}catch(_){}if(!r.ok)throw new Error(j.detail||'İşlem başarısız');return j}function hideRaw(){document.querySelectorAll('.desktop-setting-row').forEach(r=>{if((r.dataset.key||'').startsWith('HEPSIBURADA_'))r.style.display='none'})}async function load(){const host=q('#desktopSettingsFields');if(!host)return;hideRaw();let card=q('#hbBridge1027');if(!card){card=document.createElement('section');card.id='hbBridge1027';card.className='hb1027-card';host.parentElement.insertBefore(card,host)}let d={};try{d=await api('/api/hepsiburada/extension/status')}catch(e){d={ok:false,message:e.message}}const last=d.last_import_at?`Son aktarım: ${d.last_import_at} · ${d.last_saved||0} kayıt`:'Henüz veri alınmadı';card.innerHTML=`<div class="hb1027-head"><div><span>HEPSİBURADA</span><h3>Satıcı Paneli Bağlantısı</h3><p>API anahtarı gerekmez. Normal Chrome oturumunuzdan yalnız ürün fiyatı ve stok verisi yerel uygulamaya aktarılır.</p></div><div class="hb1027-state ${d.last_import_at?'ok':''}">${d.last_import_at?'Bağlı':'Eklenti bekleniyor'}</div></div><div class="hb1027-steps"><div><b>1</b><span>Chrome'da <strong>chrome://extensions</strong> sayfasını açın ve Geliştirici Modu'nu etkinleştirin.</span></div><div><b>2</b><span><strong>Paketlenmemiş öğe yükle</strong> deyip aşağıdaki butonla açılan <strong>chrome-extension</strong> klasörünü seçin.</span></div><div><b>3</b><span>Hepsiburada satıcı panelinde ürün/listing sayfasını açın. ET ürünler otomatik aktarılır.</span></div></div><div class="hb1027-actions"><button id="hbOpen1027" class="btn primary">Eklenti Klasörünü Aç</button><button id="hbRefresh1027" class="btn ghost">Bağlantı Durumunu Yenile</button><span id="hbState1027">${last}</span></div><div class="hb1027-safe">🔒 Şifre, cookie, oturum tokenı ve servis anahtarı okunmaz. Yalnız ET içeren ürün kimliği, ürün adı, fiyat ve stok gönderilir; hedef sadece bilgisayarınızdaki 127.0.0.1 uygulamasıdır.</div>`;q('#hbOpen1027').onclick=async()=>{try{await api('/api/hepsiburada/extension/open-folder',{method:'POST'})}catch(e){alert(e.message)}};q('#hbRefresh1027').onclick=load}function boot(){const nav=document.querySelector('[data-view="desktop-settings"]');if(nav)nav.addEventListener('click',()=>setTimeout(load,120));const host=q('#desktopSettingsFields');if(host)new MutationObserver(hideRaw).observe(host,{childList:true,subtree:true})}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot()})();'''
(APP/'app/static/hepsiburada_bridge.js').write_text(bridge,encoding='utf-8')

css=APP/'app/static/style.css';cs=css.read_text(encoding='utf-8');cs+=r'''
/* v10.2.7 Hepsiburada seller panel bridge */
.hb1027-card{margin:0 0 16px;padding:21px;border:1px solid rgba(255,126,27,.2);border-radius:17px;background:linear-gradient(145deg,rgba(45,25,11,.48),rgba(11,15,21,.95));box-shadow:0 16px 44px rgba(0,0,0,.15)}.hb1027-head{display:flex;justify-content:space-between;gap:20px}.hb1027-head>div>span{font-size:9px;letter-spacing:.16em;color:#ff9c48;font-weight:800}.hb1027-head h3{margin:4px 0 5px;font-size:21px}.hb1027-head p{margin:0;color:#8e99a9;font-size:12px}.hb1027-state{height:max-content;padding:7px 10px;border-radius:999px;background:rgba(255,255,255,.055);color:#9ba6b7;font-size:11px}.hb1027-state.ok{background:rgba(78,205,142,.11);color:#6fdda7}.hb1027-steps{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:17px 0}.hb1027-steps>div{display:flex;gap:10px;padding:13px;border:1px solid rgba(255,255,255,.06);border-radius:12px;background:rgba(255,255,255,.022)}.hb1027-steps b{display:grid;place-items:center;min-width:25px;height:25px;border-radius:8px;background:rgba(255,156,72,.11);color:#ffad67}.hb1027-steps span{font-size:11.5px;line-height:1.5;color:#9aa5b5}.hb1027-steps strong{color:#dce2eb}.hb1027-actions{display:flex;gap:9px;align-items:center}.hb1027-actions>span{font-size:11px;color:#8f9baa}.hb1027-safe{margin-top:13px;padding:11px 12px;border-radius:10px;background:rgba(76,211,147,.045);border:1px solid rgba(76,211,147,.09);color:#829b8e;font-size:10.8px;line-height:1.5}@media(max-width:980px){.hb1027-steps{grid-template-columns:1fr}.hb1027-actions{flex-wrap:wrap}}
''';css.write_text(cs,encoding='utf-8')

assert (EXT/'manifest.json').exists() and (EXT/'main_hook.js').exists()
assert 'HEPSIBURADA_MODE"] = "extension"' in launcher.read_text(encoding='utf-8')
assert 'hb_extension_migration_1027' in main.read_text(encoding='utf-8')
assert 'mode=="extension"' in service.read_text(encoding='utf-8')
print(APP)
