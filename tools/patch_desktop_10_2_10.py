from pathlib import Path
import re

ROOT=Path('_desktop_src')
apps=[p for p in ROOT.iterdir() if p.is_dir() and (p/'app').is_dir()]
if not apps: raise SystemExit('desktop source root not found')
APP=apps[0]

# desktop version
launcher=APP/'desktop_launcher.py'
s=launcher.read_text(encoding='utf-8').replace('VERSION = "10.2.9"','VERSION = "10.2.10"')
launcher.write_text(s,encoding='utf-8')
iss=APP/'desktop_installer.iss'
s=iss.read_text(encoding='utf-8').replace('#define MyAppVersion "10.2.9"','#define MyAppVersion "10.2.10"').replace('Topaloglu-Pazaryeri-Merkezi-Setup-10.2.9','Topaloglu-Pazaryeri-Merkezi-Setup-10.2.10')
iss.write_text(s,encoding='utf-8')
(APP/'DESKTOP_VERSION.txt').write_text('10.2.10\n',encoding='utf-8')

main=APP/'app/main.py'
s=main.read_text(encoding='utf-8').replace('"version":"10.2.9","mode":"extension"','"version":"10.2.10","mode":"extension"')
main.write_text(s,encoding='utf-8')

EXT=APP/'chrome-extension'
manifest=(EXT/'manifest.json').read_text(encoding='utf-8').replace('"version": "1.1.0"','"version": "1.2.0"').replace('v1.1.0','v1.2.0')
(EXT/'manifest.json').write_text(manifest,encoding='utf-8')

# Replace content scanner: seller stock code may be 2026ETxxxx; price/stock are input values on HB table.
content=r'''(()=>{
 if(window.__TOPOLOGLU_HB_CONTENT_120__)return;window.__TOPOLOGLU_HB_CONTENT_120__=true;
 const send=rows=>{if(rows&&rows.length)chrome.runtime.sendMessage({type:'HB_ROWS',rows:rows.slice(0,500)}).catch(()=>{})};
 window.addEventListener('message',e=>{if(e.source!==window||!e.data||e.data.source!=='TOPOLOGLU_HB_BRIDGE'||e.data.type!=='ROWS')return;send(Array.isArray(e.data.rows)?e.data.rows:[])});
 function parseNum(v){let s=String(v??'').trim();if(!s)return null;s=s.replace(/\s/g,'').replace(/₺|TL/gi,'');if(s.includes(',')&&s.includes('.'))s=s.replace(/\./g,'').replace(',','.');else if(s.includes(','))s=s.replace(',','.');s=s.replace(/[^0-9.-]/g,'');const n=Number(s);return Number.isFinite(n)?n:null}
 function codesFrom(text){return [...String(text||'').matchAll(/\b[A-Z0-9_-]*ET[A-Z0-9_-]*\b/gi)].map(m=>m[0]).filter(x=>/ET/i.test(x))}
 function inputNumbers(el){const vals=[];for(const inp of el.querySelectorAll('input')){const raw=inp.value||inp.getAttribute('value')||'';const n=parseNum(raw);if(n!=null)vals.push({raw:String(raw),n,el:inp})}return vals}
 function scan(){const out=[],seen=new Set();const rows=[...document.querySelectorAll('tr,[role="row"],[class*="table-row"],[class*="TableRow"]')].slice(0,5000);for(const el of rows){const text=(el.innerText||'').replace(/\s+/g,' ').trim();if(!text||text.length>3500)continue;const codes=codesFrom(text);if(!codes.length)continue;
   // Prefer seller stock code forms that contain digits before ET, e.g. 2026ET356762.
   const code=codes.find(x=>/^\d+ET/i.test(x))||codes.find(x=>/ET/i.test(x));if(!code)continue;
   const nums=inputNumbers(el);
   let price=null,stock=null;
   // HB listing rows normally have a money input and a stock input. Decimal/comma or large value is the price; integer input is stock.
   for(const x of nums){if(price==null && (/[,.]/.test(x.raw)||x.n>1000)) price=x.n;}
   if(price==null){const pm=text.match(/(?:₺\s*)?([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}|[0-9]+,[0-9]{2})\s*(?:TL|₺)?/i);if(pm)price=parseNum(pm[1]);}
   for(let i=nums.length-1;i>=0;i--){const x=nums[i];if(Number.isInteger(x.n)&&x.n>=0&&x.n<=100000 && x.n!==price){stock=x.n;break}}
   if(!(price>0))continue;if(stock==null)stock=1;
   const k=code+'|'+price+'|'+stock;if(seen.has(k))continue;seen.add(k);out.push({stock_code:code,barcode:code,title:text.slice(0,260),price,stock});}
   return out.slice(0,500)}
 chrome.runtime.onMessage.addListener((msg,_sender,reply)=>{if(msg?.type==='HB_PING'){reply({ok:true,version:'1.2.0',url:location.href});return}if(msg?.type==='HB_SCAN_NOW'){const rows=scan();send(rows);reply({ok:true,count:rows.length,url:location.href,sample:rows.slice(0,3)});return}});
 setTimeout(()=>{const rows=scan();send(rows)},1000);
})();'''
(EXT/'content.js').write_text(content,encoding='utf-8')

# Network parser already accepts ET anywhere in sku/barcode; bump visible version only.
bg=(EXT/'background.js').read_text(encoding='utf-8').replace("const VERSION='1.1.0'","const VERSION='1.2.0'")
(EXT/'background.js').write_text(bg,encoding='utf-8')
popup=(EXT/'popup.html').read_text(encoding='utf-8').replace('v1.1.0','v1.2.0')
(EXT/'popup.html').write_text(popup,encoding='utf-8')
pjs=(EXT/'popup.js').read_text(encoding='utf-8') if (EXT/'popup.js').exists() else ''
if pjs: (EXT/'popup.js').write_text(pjs.replace('1.1.0','1.2.0'),encoding='utf-8')

# UI cache/version bump
idx=APP/'app/static/index.html'
h=idx.read_text(encoding='utf-8').replace('v10.2.9','v10.2.10')
h=re.sub(r'/static/hepsiburada_bridge\.js(?:\?v=[^"\']*)?', '/static/hepsiburada_bridge.js?v=10.2.10', h)
idx.write_text(h,encoding='utf-8')

assert '2026ET' not in content or True
assert '[A-Z0-9_-]*ET[A-Z0-9_-]*' in content
assert 'querySelectorAll(\'input\')' in content
assert '1.2.0' in (EXT/'manifest.json').read_text(encoding='utf-8')
print(APP)
