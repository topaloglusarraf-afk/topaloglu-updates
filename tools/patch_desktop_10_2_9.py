from pathlib import Path
import re

ROOT=Path('_desktop_src')
apps=[p for p in ROOT.iterdir() if p.is_dir() and (p/'app').is_dir()]
if not apps: raise SystemExit('desktop source root not found')
APP=apps[0]

# Desktop version
launcher=APP/'desktop_launcher.py'
s=launcher.read_text(encoding='utf-8').replace('VERSION = "10.2.8"','VERSION = "10.2.9"')
launcher.write_text(s,encoding='utf-8')
iss=APP/'desktop_installer.iss'
s=iss.read_text(encoding='utf-8').replace('#define MyAppVersion "10.2.8"','#define MyAppVersion "10.2.9"').replace('Topaloglu-Pazaryeri-Merkezi-Setup-10.2.8','Topaloglu-Pazaryeri-Merkezi-Setup-10.2.9')
iss.write_text(s,encoding='utf-8')
(APP/'DESKTOP_VERSION.txt').write_text('10.2.9\n',encoding='utf-8')

# Backend status version
main=APP/'app/main.py'
s=main.read_text(encoding='utf-8').replace('"version":"10.2.8","mode":"extension"','"version":"10.2.9","mode":"extension"')
main.write_text(s,encoding='utf-8')

EXT=APP/'chrome-extension'; EXT.mkdir(exist_ok=True)
manifest=r'''{
  "manifest_version": 3,
  "name": "Topaloğlu Hepsiburada Köprüsü",
  "version": "1.1.0",
  "description": "Hepsiburada satıcı panelindeki ET ürün fiyat/stok verisini yalnız yerel Topaloğlu uygulamasına aktarır.",
  "permissions": ["storage", "scripting", "tabs", "activeTab"],
  "host_permissions": [
    "https://*.hepsiburada.com/*",
    "https://hepsiburada.com/*",
    "http://127.0.0.1:8765/*","http://127.0.0.1:8766/*","http://127.0.0.1:8767/*","http://127.0.0.1:8768/*","http://127.0.0.1:8877/*"
  ],
  "background": {"service_worker": "background.js"},
  "content_scripts": [
    {"matches":["https://*.hepsiburada.com/*","https://hepsiburada.com/*"],"js":["main_hook.js"],"run_at":"document_start","world":"MAIN"},
    {"matches":["https://*.hepsiburada.com/*","https://hepsiburada.com/*"],"js":["content.js"],"run_at":"document_start"}
  ],
  "action": {"default_popup":"popup.html","default_title":"Topaloğlu Hepsiburada Köprüsü v1.1.0"}
}'''
(EXT/'manifest.json').write_text(manifest,encoding='utf-8')

main_hook=r'''(()=>{
 if(window.__TOPOLOGLU_HB_HOOK_110__)return;window.__TOPOLOGLU_HB_HOOK_110__=true;
 const num=v=>{if(v==null)return null;if(typeof v==='object'){for(const k of ['amount','value','price'])if(v[k]!=null)return num(v[k]);return null;}let s=String(v).trim();if(!s)return null;s=s.replace(/\s/g,'');if(s.includes(',')&&s.includes('.'))s=s.replace(/\./g,'').replace(',','.');else if(s.includes(','))s=s.replace(',','.');s=s.replace(/[^0-9.-]/g,'');const n=Number(s);return Number.isFinite(n)?n:null};
 const val=(o,keys)=>{for(const k of keys)if(o&&o[k]!=null&&o[k]!=='' )return o[k];return null};
 const clean=o=>{if(!o||typeof o!=='object'||Array.isArray(o))return null;const sku=val(o,['merchantSku','merchantSKU','merchant_sku','merchantSkuId','stockCode','merchantStockCode','sku','merchantProductCode']);const barcode=val(o,['barcode','barCode','merchantBarcode','gtin','ean']);const title=val(o,['productName','productTitle','listingName','title','name']);const price=num(val(o,['price','salePrice','listingPrice','currentPrice','finalPrice','offerPrice']));const stock=num(val(o,['availableStock','stock','quantity','merchantStock','inventory','availableQuantity']));if(price==null||price<=0)return null;if(!/ET/i.test(String(sku||''))&&!/ET/i.test(String(barcode||'')))return null;return {stock_code:String(sku||''),barcode:String(barcode||''),title:String(title||''),price,stock:stock==null?1:stock};};
 const extract=root=>{const out=[],seenObj=new WeakSet(),seenRow=new Set();let count=0;function walk(x,d){if(!x||d>9||count>30000||typeof x!=='object')return;if(seenObj.has(x))return;seenObj.add(x);count++;const r=clean(x);if(r){const k=[r.stock_code,r.barcode,r.title,r.price,r.stock].join('|');if(!seenRow.has(k)){seenRow.add(k);out.push(r)}}if(Array.isArray(x)){for(const v of x)walk(v,d+1)}else{for(const [k,v] of Object.entries(x)){if(/token|cookie|password|authorization|secret|session/i.test(k))continue;walk(v,d+1)}}}walk(root,0);return out.slice(0,500)};
 const emit=(data,url)=>{try{const rows=extract(data);if(rows.length)window.postMessage({source:'TOPOLOGLU_HB_BRIDGE',type:'ROWS',rows,url:String(url||'')},'*')}catch(_){}};
 const full=u=>{try{return new URL(String(u||''),location.href).href}catch(_){return String(u||'')}};
 const interesting=u=>{const x=full(u).toLowerCase();return x.includes('hepsiburada.com')};
 const ofetch=window.fetch;window.fetch=async function(...args){const res=await ofetch.apply(this,args);try{const url=full(args[0]?.url||args[0]);if(interesting(url)){const c=res.clone();const ct=c.headers.get('content-type')||'';if(ct.includes('json'))c.json().then(j=>emit(j,url)).catch(()=>{});else c.text().then(t=>{const z=String(t||'').trim();if(z&&'[{'.includes(z[0]))try{emit(JSON.parse(z),url)}catch(_){}}).catch(()=>{})}}catch(_){}return res};
 const XO=XMLHttpRequest.prototype.open,XS=XMLHttpRequest.prototype.send;XMLHttpRequest.prototype.open=function(m,u,...rest){this.__topaloglu_url=full(u);return XO.call(this,m,u,...rest)};XMLHttpRequest.prototype.send=function(...args){this.addEventListener('load',()=>{try{if(!interesting(this.__topaloglu_url))return;let d=this.response;if(this.responseType===''||this.responseType==='text'){const t=String(this.responseText||'').trim();if(t&&'[{'.includes(t[0]))d=JSON.parse(t)}if(this.responseType==='json'||typeof d==='object')emit(d,this.__topaloglu_url)}catch(_){}});return XS.apply(this,args)};
})();'''
(EXT/'main_hook.js').write_text(main_hook,encoding='utf-8')

content=r'''(()=>{
 if(window.__TOPOLOGLU_HB_CONTENT_110__)return;window.__TOPOLOGLU_HB_CONTENT_110__=true;
 const send=rows=>{if(rows&&rows.length)chrome.runtime.sendMessage({type:'HB_ROWS',rows:rows.slice(0,500)}).catch(()=>{})};
 window.addEventListener('message',e=>{if(e.source!==window||!e.data||e.data.source!=='TOPOLOGLU_HB_BRIDGE'||e.data.type!=='ROWS')return;send(Array.isArray(e.data.rows)?e.data.rows:[])});
 function priceFrom(t){const ms=[...String(t||'').matchAll(/(?:₺\s*)?([0-9]{1,3}(?:\.[0-9]{3})*(?:,[0-9]{1,2})|[0-9]+(?:[.,][0-9]{1,2})?)\s*(?:TL|₺)/gi)];if(!ms.length)return null;const raw=ms[0][1];const n=Number(raw.includes(',')?raw.replace(/\./g,'').replace(',','.') : raw);return Number.isFinite(n)?n:null}
 function scan(){const out=[],seen=new Set();const nodes=[...document.querySelectorAll('tr,[role="row"],[class*="product"],[class*="listing"],[class*="offer"],[class*="table-row"],[class*="TableRow"]')].slice(0,3000);for(const el of nodes){const text=(el.innerText||'').replace(/\s+/g,' ').trim();if(!text||text.length>2500)continue;const codes=[...text.matchAll(/\bET[-_A-Z0-9]{2,}\b/gi)].map(m=>m[0]);if(!codes.length)continue;const price=priceFrom(text);if(!(price>0))continue;let stock=1;const sm=text.match(/(?:stok|stock|adet|miktar)\s*[:\-]?\s*(\d+)/i);if(sm)stock=Number(sm[1]);const code=codes[0];const k=code+'|'+price+'|'+stock;if(seen.has(k))continue;seen.add(k);out.push({stock_code:code,barcode:code,title:text.slice(0,240),price,stock})}return out.slice(0,500)}
 chrome.runtime.onMessage.addListener((msg,_sender,reply)=>{if(msg?.type==='HB_PING'){reply({ok:true,version:'1.1.0',url:location.href});return}if(msg?.type==='HB_SCAN_NOW'){const rows=scan();send(rows);reply({ok:true,count:rows.length,url:location.href});return}});
 setTimeout(()=>{const rows=scan();send(rows)},1200);
})();'''
(EXT/'content.js').write_text(content,encoding='utf-8')

background=r'''const VERSION='1.1.0';const PORTS=[8765,8766,8767,8768,8877];let buffer=[],timer=null;
async function findApp(){for(const p of PORTS){try{const r=await fetch(`http://127.0.0.1:${p}/api/hepsiburada/extension/status`,{cache:'no-store'});if(r.ok)return p}catch(_){}}return null}
function dedupe(rows){const out=[],s=new Set();for(const r of rows||[]){const k=[r.stock_code,r.barcode,r.title,r.price,r.stock].join('|');if(!s.has(k)){s.add(k);out.push(r)}}return out.slice(0,500)}
async function flush(){timer=null;const rows=dedupe(buffer);buffer=[];if(!rows.length)return;const port=await findApp();if(!port){await chrome.storage.local.set({hbStatus:{ok:false,message:'Topaloğlu uygulaması bulunamadı.',at:new Date().toISOString(),version:VERSION}});chrome.action.setBadgeText({text:'!'});return}try{const r=await fetch(`http://127.0.0.1:${port}/api/hepsiburada/extension/import`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({rows})});const j=await r.json();if(!r.ok)throw new Error(j.detail||'Aktarım başarısız');await chrome.storage.local.set({hbStatus:{ok:true,message:`${j.saved||0} ürün aktarıldı`,saved:j.saved||0,matched:j.matched||0,at:new Date().toISOString(),port,version:VERSION}});chrome.action.setBadgeBackgroundColor({color:'#2f9e68'});chrome.action.setBadgeText({text:String(Math.min(99,j.saved||0))})}catch(e){await chrome.storage.local.set({hbStatus:{ok:false,message:String(e.message||e),at:new Date().toISOString(),version:VERSION}});chrome.action.setBadgeText({text:'!'})}}
chrome.runtime.onMessage.addListener((msg,_sender,sendResponse)=>{if(msg?.type==='HB_ROWS'&&Array.isArray(msg.rows)){buffer.push(...msg.rows);if(!timer)timer=setTimeout(flush,700);sendResponse({ok:true});return}if(msg?.type==='HB_FIND_APP'){findApp().then(p=>sendResponse({ok:!!p,port:p,version:VERSION}));return true}});
chrome.runtime.onInstalled.addListener(()=>chrome.storage.local.set({hbStatus:{ok:false,message:'Hepsiburada satıcı panelini açın.',at:new Date().toISOString(),version:VERSION}}));'''
(EXT/'background.js').write_text(background,encoding='utf-8')

popup=r'''<!doctype html><html><head><meta charset="utf-8"><style>body{width:360px;background:#0b1017;color:#e8edf4;font:13px Segoe UI;margin:0;padding:18px}h2{font-size:17px;margin:0 0 4px}small{color:#7f8b99}.ver{color:#e2b751;font-weight:700}.btn{width:100%;border:0;border-radius:11px;padding:12px;margin-top:10px;font-weight:700;cursor:pointer}.primary{background:#e0b34f;color:#111}.ghost{background:#1b2634;color:#e8edf4;border:1px solid #344253}.s{margin-top:12px;padding:11px;border-radius:10px;background:#151c25;color:#9eabb9;line-height:1.45}.ok{color:#62d59b}.err{color:#ff777f}.page{margin-top:10px;color:#7e8997;font-size:11px;word-break:break-all}</style></head><body><h2>Topaloğlu Hepsiburada Köprüsü <span class="ver">v1.1.0</span></h2><small>Açık Hepsiburada sayfasını otomatik bağlar; yenileme gerekmez.</small><div id="page" class="page"></div><button id="scan" class="btn primary">Açık Sayfayı Tara ve Gönder</button><button id="app" class="btn ghost">Topaloğlu Uygulamasını Kontrol Et</button><div id="s" class="s">Bağlantı hazırlanıyor…</div><script src="popup.js"></script></body></html>'''
(EXT/'popup.html').write_text(popup,encoding='utf-8')

popup_js=r'''const $=id=>document.getElementById(id);function state(t,c=''){const s=$('s');s.textContent=t;s.className='s '+c}function isHB(u){try{return new URL(u).hostname.endsWith('hepsiburada.com')}catch(_){return false}}
async function active(){const [t]=await chrome.tabs.query({active:true,currentWindow:true});return t}
async function ping(tabId){return await chrome.tabs.sendMessage(tabId,{type:'HB_PING'})}
async function ensure(tab){if(!tab||!isHB(tab.url))throw new Error('Önce Hepsiburada satıcı paneli sekmesini açın.');$('page').textContent=tab.url;try{return await ping(tab.id)}catch(_){}try{await chrome.scripting.executeScript({target:{tabId:tab.id},files:['main_hook.js'],world:'MAIN'});await chrome.scripting.executeScript({target:{tabId:tab.id},files:['content.js']});await new Promise(r=>setTimeout(r,180));return await ping(tab.id)}catch(e){throw new Error('Hepsiburada sekmesine bağlanılamadı: '+(e.message||e))}}
async function boot(){try{const tab=await active();const p=await ensure(tab);state('✓ Hepsiburada sekmesi bağlı · Köprü '+p.version,'ok')}catch(e){state('✕ '+e.message,'err')}}
$('scan').onclick=async()=>{state('Sayfa taranıyor…');try{const tab=await active();await ensure(tab);const r=await chrome.tabs.sendMessage(tab.id,{type:'HB_SCAN_NOW'});if(r.count>0)state(`✓ ${r.count} ET satırı bulundu ve gönderildi.`,'ok');else state('ET kodu ve fiyat içeren satır bulunamadı. Ürün/listing tablosunu açın.','err')}catch(e){state('✕ '+e.message,'err')}};
$('app').onclick=async()=>{state('Uygulama aranıyor…');try{const r=await chrome.runtime.sendMessage({type:'HB_FIND_APP'});if(r?.ok)state(`✓ Topaloğlu uygulaması bağlı · port ${r.port}`,'ok');else state('Topaloğlu uygulaması bulunamadı. Uygulamayı açık tutun.','err')}catch(e){state('✕ '+e.message,'err')}};boot();'''
(EXT/'popup.js').write_text(popup_js,encoding='utf-8')

# UI cache bump and clearer bridge version
idx=APP/'app/static/index.html'
h=idx.read_text(encoding='utf-8').replace('v10.2.8','v10.2.9')
h=re.sub(r'/static/style\.css(?:\?v=[^"\']*)?', '/static/style.css?v=10.2.9', h)
h=re.sub(r'/static/app\.js(?:\?v=[^"\']*)?', '/static/app.js?v=10.2.9', h)
h=re.sub(r'/static/desktop_settings\.js(?:\?v=[^"\']*)?', '/static/desktop_settings.js?v=10.2.9', h)
h=re.sub(r'/static/mete_boot\.js(?:\?v=[^"\']*)?', '/static/mete_boot.js?v=10.2.9', h)
h=re.sub(r'/static/hepsiburada_bridge\.js(?:\?v=[^"\']*)?', '/static/hepsiburada_bridge.js?v=10.2.9', h)
idx.write_text(h,encoding='utf-8')
bridge=APP/'app/static/hepsiburada_bridge.js'
b=bridge.read_text(encoding='utf-8')
b=b.replace('Topaloglu-Hepsiburada-Uzantisi</strong> olacak.','Topaloglu-Hepsiburada-Uzantisi</strong> olacak. Chrome uzantısında <strong>v1.1.0</strong> yazdığını kontrol et.')
bridge.write_text(b,encoding='utf-8')

assert '"version": "1.1.0"' in (EXT/'manifest.json').read_text(encoding='utf-8')
assert 'chrome.scripting.executeScript' in (EXT/'popup.js').read_text(encoding='utf-8')
assert '*.hepsiburada.com' in (EXT/'manifest.json').read_text(encoding='utf-8')
print(APP)
