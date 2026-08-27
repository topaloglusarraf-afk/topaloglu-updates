from pathlib import Path
import re

ROOT=Path('_desktop_src')
apps=[p for p in ROOT.iterdir() if p.is_dir() and (p/'app').is_dir()]
if not apps: raise SystemExit('desktop source root not found')
APP=apps[0]

# ----- version -----
launcher=APP/'desktop_launcher.py'
s=launcher.read_text(encoding='utf-8')
s=s.replace('VERSION = "10.2.4"','VERSION = "10.2.5"').replace('VERSION = "10.2.3"','VERSION = "10.2.5"')
launcher.write_text(s,encoding='utf-8')

iss=APP/'desktop_installer.iss'
s=iss.read_text(encoding='utf-8')
s=s.replace('#define MyAppVersion "10.2.4"','#define MyAppVersion "10.2.5"').replace('#define MyAppVersion "10.2.3"','#define MyAppVersion "10.2.5"')
s=s.replace('Topaloglu-Pazaryeri-Merkezi-Setup-10.2.4','Topaloglu-Pazaryeri-Merkezi-Setup-10.2.5').replace('Topaloglu-Pazaryeri-Merkezi-Setup-10.2.3','Topaloglu-Pazaryeri-Merkezi-Setup-10.2.5')
iss.write_text(s,encoding='utf-8')
(APP/'DESKTOP_VERSION.txt').write_text('10.2.5\n',encoding='utf-8')

# ----- permanent no-cache for desktop static assets -----
main=APP/'app/main.py'
s=main.read_text(encoding='utf-8')
cache_block=r'''

# v10.2.5 desktop: never serve stale UI assets from WebView cache
@app.middleware("http")
async def desktop_no_cache_1025(request, call_next):
    response = await call_next(request)
    if os.getenv("TOPOLOGLU_DESKTOP") == "1" and (request.url.path == "/" or request.url.path.startswith("/static/")):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response
'''
if '# v10.2.5 desktop: never serve stale UI assets' not in s:
    marker='@app.on_event("startup")'
    pos=s.find(marker)
    if pos<0: raise SystemExit('startup marker missing')
    s=s[:pos]+cache_block+'\n'+s[pos:]
main.write_text(s,encoding='utf-8')

# ----- HTML: force cache-busting and stronger visual mode -----
idx=APP/'app/static/index.html'
h=idx.read_text(encoding='utf-8')
h=h.replace('v10.2.4','v10.2.5').replace('v10.2.3','v10.2.5')
h=h.replace('class="premium-v2 premium-v3"','class="premium-v2 premium-v3 premium-v4"',1)
if 'premium-v4' not in h:
    h=h.replace('class="premium-v2"','class="premium-v2 premium-v3 premium-v4"',1)
# force unique URLs, including old 10.1.x links that caused WebView to keep old CSS
h=re.sub(r'/static/style\.css(?:\?v=[^"\']*)?', '/static/style.css?v=10.2.5', h)
h=re.sub(r'/static/app\.js(?:\?v=[^"\']*)?', '/static/app.js?v=10.2.5', h)
h=re.sub(r'/static/wallboard\.js(?:\?v=[^"\']*)?', '/static/wallboard.js?v=10.2.5', h)
h=re.sub(r'/static/desktop_settings\.js(?:\?v=[^"\']*)?', '/static/desktop_settings.js?v=10.2.5', h)
h=re.sub(r'/static/mete_boot\.js(?:\?v=[^"\']*)?', '/static/mete_boot.js?v=10.2.5', h)
idx.write_text(h,encoding='utf-8')

# ----- authentic full-screen CMD-style METE boot -----
boot_js=r'''(function(){
const boot=document.getElementById('meteBoot');
if(!boot)return;
if(sessionStorage.getItem('mete_boot_1025')==='1'){boot.remove();document.body.classList.add('mete-app-ready');return;}
sessionStorage.setItem('mete_boot_1025','1');
boot.classList.add('mete-cmd-mode');
const box=document.getElementById('meteBootLines');
const prog=document.getElementById('meteProgress');
const ready=document.getElementById('meteReady');
const word=document.querySelector('.mete-word');
if(word){word.innerHTML='<span class="mete-cmd-prompt">C:\\TOPOLOGLU&gt; whoami</span><strong>METE</strong><span class="mete-cursor">_</span>';}
const lines=[
 'Microsoft Windows [Version 10.0.26100]',
 '(c) Topaloglu Systems. All rights reserved.',
 '',
 'C:\\TOPOLOGLU&gt; guard.exe --start --mode=secure',
 '[OK] ET product gate ................. ACTIVE',
 '[OK] Price protection engine ......... ACTIVE',
 '[OK] Critical alarm tolerance ........ 1300 TL',
 '[OK] Marketplace control center ...... READY'
];
let i=0;
function add(){
 if(i>=lines.length)return;
 const row=document.createElement('div'); row.className='mete-line';
 const raw=lines[i++];
 row.textContent=raw;
 if(raw.startsWith('[OK]'))row.classList.add('ok');
 if(raw.startsWith('C:\\'))row.classList.add('cmd');
 box.appendChild(row); requestAnimationFrame(()=>row.classList.add('show'));
 box.scrollTop=box.scrollHeight;
 setTimeout(add, i<4?145:120);
}
setTimeout(add,90);
requestAnimationFrame(()=>{if(prog)prog.style.width='100%'});
setTimeout(()=>ready&&ready.classList.add('show'),1250);
setTimeout(()=>boot.classList.add('mete-boot-out'),2650);
setTimeout(()=>{boot.remove();document.body.classList.add('mete-app-ready');},3150);
})();'''
(APP/'app/static/mete_boot.js').write_text(boot_js,encoding='utf-8')

# ----- visibly different command-center design -----
css=APP/'app/static/style.css'
cs=css.read_text(encoding='utf-8')
cs += r'''

/* v10.2.5 — command center redesign (intentionally high specificity) */
body.premium-v4{font-family:"Segoe UI Variable","Segoe UI",Arial,sans-serif!important;background:#05070a!important;color:#eef1f6!important}
body.premium-v4 .shell{grid-template-columns:272px minmax(0,1fr)!important;min-height:100vh!important;background:radial-gradient(circle at 88% -10%,rgba(209,174,91,.09),transparent 31%),radial-gradient(circle at 22% 110%,rgba(53,94,148,.07),transparent 32%),#070a0f!important}
body.premium-v4 .sidebar{padding:24px 17px 20px!important;background:linear-gradient(180deg,#0b0f16 0%,#070a0f 100%)!important;border-right:1px solid rgba(255,255,255,.075)!important;box-shadow:18px 0 55px rgba(0,0,0,.28)!important}
body.premium-v4 .brand{padding:0 5px 22px!important;margin-bottom:13px!important;gap:12px!important}
body.premium-v4 .brand-icon{width:43px!important;height:43px!important;border-radius:13px!important;font-size:20px!important}
body.premium-v4 .brand strong{font-size:14px!important}body.premium-v4 .brand span{font-size:10px!important;margin-top:3px!important}
body.premium-v4 .sidebar nav{display:grid!important;gap:4px!important}
body.premium-v4 .nav{min-height:43px!important;padding:0 13px!important;font-size:12.5px!important;border-radius:12px!important}
body.premium-v4 .nav i{width:23px!important;color:#728095!important;font-style:normal!important}
body.premium-v4 .nav.active{background:linear-gradient(90deg,rgba(216,184,102,.17),rgba(216,184,102,.035))!important;border:1px solid rgba(216,184,102,.2)!important;color:#f0d98d!important;box-shadow:inset 3px 0 #d8b866,0 10px 24px rgba(0,0,0,.12)!important}
body.premium-v4 .notification-state,body.premium-v4 .sidebar-card{background:#0c1118!important;border:1px solid rgba(255,255,255,.07)!important;border-radius:14px!important;box-shadow:none!important}
body.premium-v4 .main{padding:22px 28px 46px!important;min-width:0!important}
body.premium-v4 .header{background:linear-gradient(145deg,rgba(17,22,31,.96),rgba(10,14,20,.96))!important;border:1px solid rgba(255,255,255,.075)!important;border-radius:20px!important;padding:22px 24px!important;margin:0 0 18px!important;box-shadow:0 18px 50px rgba(0,0,0,.2)!important;align-items:center!important}
body.premium-v4 .header h1{font-size:31px!important;margin:4px 0 5px!important}body.premium-v4 .header p{font-size:12px!important;max-width:600px!important}
body.premium-v4 .eyebrow{font-size:9px!important;letter-spacing:.16em!important}
body.premium-v4 .toolbar{gap:7px!important;align-items:center!important}body.premium-v4 .toolbar .btn{white-space:nowrap!important}
body.premium-v4 .btn{height:39px!important;padding:0 14px!important;border-radius:10px!important;font-size:11.5px!important}
body.premium-v4 .btn.primary{background:linear-gradient(135deg,#e4c570,#b78d34)!important;color:#171109!important;box-shadow:0 8px 24px rgba(216,184,102,.14)!important}
body.premium-v4 .view{animation:premium1025In .24s ease both} @keyframes premium1025In{from{opacity:.35;transform:translateY(5px)}to{opacity:1;transform:none}}
body.premium-v4 .glass,body.premium-v4 .panel{background:linear-gradient(145deg,rgba(17,22,31,.94),rgba(10,14,20,.94))!important;border:1px solid rgba(255,255,255,.072)!important;border-radius:18px!important;box-shadow:0 16px 44px rgba(0,0,0,.16)!important}
body.premium-v4 .wall-status{min-height:178px!important;padding:30px 32px!important;border-radius:22px!important;background:linear-gradient(135deg,#101821,#0b1118)!important;border:1px solid rgba(255,255,255,.08)!important;box-shadow:0 20px 55px rgba(0,0,0,.22)!important}
body.premium-v4 .wall-status.wall-ok{background:linear-gradient(120deg,rgba(22,69,51,.82),rgba(11,19,20,.98) 58%,#0a0f15)!important;border-color:rgba(83,217,153,.2)!important}
body.premium-v4 .wall-status.wall-critical,body.premium-v4 .wall-status.wall-danger{background:linear-gradient(120deg,rgba(91,29,36,.88),rgba(20,13,17,.98) 58%,#0b0e13)!important;border-color:rgba(255,95,104,.28)!important}
body.premium-v4 .wall-copy h1{font-size:44px!important;line-height:1!important;letter-spacing:-.05em!important;margin:5px 0 9px!important}
body.premium-v4 .wall-copy>span{font-size:9px!important;letter-spacing:.17em!important}body.premium-v4 .wall-copy p{font-size:12px!important}
body.premium-v4 .wall-signal{width:70px!important;height:70px!important;border-radius:20px!important;background:rgba(255,255,255,.035)!important;border:1px solid rgba(255,255,255,.08)!important}
body.premium-v4 .wall-kpis{display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr))!important;gap:12px!important;margin:12px 0!important}
body.premium-v4 .wall-kpis article{padding:19px 21px!important;border-radius:16px!important;background:linear-gradient(145deg,#101620,#0b1017)!important;border:1px solid rgba(255,255,255,.07)!important}
body.premium-v4 .wall-kpis strong{font-size:36px!important;margin-top:4px!important}body.premium-v4 .wall-kpis small{color:#697588!important}
body.premium-v4 .wall-panel{border-radius:18px!important;border:1px solid rgba(255,255,255,.075)!important;background:#0b1017!important;box-shadow:0 18px 46px rgba(0,0,0,.16)!important}
body.premium-v4 .wall-head{padding:20px 22px!important;background:rgba(255,255,255,.012)!important}
body.premium-v4 .executive-grid{gap:12px!important}body.premium-v4 .hero-card,body.premium-v4 .metric-card{border-radius:17px!important;background:linear-gradient(145deg,#111720,#0b1017)!important}
body.premium-v4 .market-grid{gap:12px!important}body.premium-v4 .market-card{border-radius:17px!important;background:linear-gradient(145deg,#111720,#0b1017)!important;border:1px solid rgba(255,255,255,.07)!important}
body.premium-v4 .panel-head{padding-bottom:15px!important;border-bottom:1px solid rgba(255,255,255,.045)!important;margin-bottom:12px!important}
body.premium-v4 table{font-size:11.5px!important}body.premium-v4 thead th{background:#0a0f16!important;color:#718095!important;padding:12px 11px!important}body.premium-v4 tbody td{padding:12px 11px!important}body.premium-v4 tbody tr:hover{background:rgba(216,184,102,.028)!important}
body.premium-v4 input,body.premium-v4 select{min-height:38px!important;background:#080c12!important;border-color:rgba(255,255,255,.085)!important}
body.premium-v4 .desktop-setting-row{padding:14px 15px!important;border-radius:13px!important;background:#0b1017!important}
body.premium-v4 .desktop-version-card{background:linear-gradient(135deg,rgba(216,184,102,.11),rgba(216,184,102,.025))!important;border-color:rgba(216,184,102,.2)!important}

/* v10.2.5 full-screen Windows CMD boot */
.mete-boot.mete-cmd-mode{position:fixed!important;inset:0!important;width:100vw!important;height:100vh!important;z-index:2147483647!important;background:#020303!important;display:flex!important;align-items:center!important;justify-content:center!important;padding:0!important;margin:0!important;overflow:hidden!important;font-family:"Cascadia Mono","Consolas","Courier New",monospace!important;color:#d7fbe2!important}
.mete-cmd-mode .mete-scanlines{display:block!important;position:absolute!important;inset:0!important;background:repeating-linear-gradient(0deg,transparent 0,transparent 3px,rgba(71,255,129,.018) 4px)!important;pointer-events:none!important}
.mete-cmd-mode .mete-terminal{width:min(980px,88vw)!important;height:min(610px,78vh)!important;display:flex!important;flex-direction:column!important;background:#050806!important;border:1px solid #26382b!important;border-radius:8px!important;box-shadow:0 28px 120px rgba(0,0,0,.85),0 0 60px rgba(65,255,123,.035)!important;overflow:hidden!important;padding:0!important;position:relative!important}
.mete-cmd-mode .mete-terminal-top{height:38px!important;min-height:38px!important;background:#111411!important;border-bottom:1px solid #283028!important;color:#8f9c91!important;padding:0 13px!important;display:flex!important;align-items:center!important;gap:7px!important;font-size:10px!important;letter-spacing:.06em!important}
.mete-cmd-mode .mete-terminal-top span{width:9px!important;height:9px!important;border-radius:50%!important;background:#485148!important}.mete-cmd-mode .mete-terminal-top span:first-child{background:#8d4545!important}.mete-cmd-mode .mete-terminal-top span:nth-child(2){background:#8b763c!important}.mete-cmd-mode .mete-terminal-top span:nth-child(3){background:#3f7d55!important}
.mete-cmd-mode .mete-boot-lines{flex:1!important;height:auto!important;overflow:hidden!important;padding:26px 30px 8px!important;font-size:14px!important;line-height:1.72!important;color:#c9d2ca!important;text-align:left!important}
.mete-cmd-mode .mete-line{opacity:0!important;transform:translateY(3px)!important;transition:.12s ease!important;white-space:pre-wrap!important}.mete-cmd-mode .mete-line.show{opacity:1!important;transform:none!important}.mete-cmd-mode .mete-line.ok{color:#66ee94!important}.mete-cmd-mode .mete-line.cmd{color:#f1f5f2!important}
.mete-cmd-mode .mete-word-wrap{padding:5px 30px 24px!important;text-align:left!important}.mete-cmd-mode .mete-prefix{display:none!important}.mete-cmd-mode .mete-word{font-size:15px!important;line-height:1.45!important;letter-spacing:0!important;color:#eff5f0!important;text-shadow:none!important;animation:none!important;margin:0!important}.mete-cmd-mode .mete-word:before{display:none!important}.mete-cmd-mode .mete-cmd-prompt{display:block!important;color:#eef4ef!important;font-weight:400!important}.mete-cmd-mode .mete-word strong{display:inline-block!important;margin-top:6px!important;font-size:72px!important;line-height:1!important;letter-spacing:.12em!important;color:#70ff9d!important;text-shadow:0 0 28px rgba(83,255,136,.16)!important}.mete-cmd-mode .mete-cursor{font-size:62px!important;color:#afffc7!important;animation:meteCursor .66s steps(1,end) infinite!important}
.mete-cmd-mode .mete-progress{height:2px!important;background:#101b13!important}.mete-cmd-mode .mete-progress i{background:#58e784!important;box-shadow:0 0 14px rgba(88,231,132,.4)!important;transition:width 2.35s cubic-bezier(.22,.75,.25,1)!important}.mete-cmd-mode .mete-ready{height:30px!important;padding:0 30px!important;display:flex!important;align-items:center!important;background:#071008!important;color:#4c895f!important;font-size:9px!important;letter-spacing:.13em!important;border-top:1px solid #16251a!important;opacity:.45!important}.mete-cmd-mode .mete-ready.show{opacity:1!important;color:#70d991!important}
@media(max-width:1100px){body.premium-v4 .shell{grid-template-columns:230px minmax(0,1fr)!important}body.premium-v4 .main{padding:18px!important}body.premium-v4 .header{align-items:flex-start!important}body.premium-v4 .wall-copy h1{font-size:36px!important}}
'''
css.write_text(cs,encoding='utf-8')

# assertions
final_h=idx.read_text(encoding='utf-8')
assert 'style.css?v=10.2.5' in final_h
assert 'mete_boot.js?v=10.2.5' in final_h
assert 'premium-v4' in final_h
assert '# v10.2.5 desktop: never serve stale UI assets' in main.read_text(encoding='utf-8')
assert 'v10.2.5 — command center redesign' in css.read_text(encoding='utf-8')
print(APP)
