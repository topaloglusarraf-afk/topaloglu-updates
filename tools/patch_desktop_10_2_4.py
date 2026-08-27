from pathlib import Path

ROOT=Path('_desktop_src')
apps=[p for p in ROOT.iterdir() if p.is_dir() and (p/'app').is_dir()]
if not apps: raise SystemExit('desktop source root not found')
APP=apps[0]

# ----- version -----
launcher=APP/'desktop_launcher.py'
s=launcher.read_text(encoding='utf-8')
s=s.replace('VERSION = "10.2.3"','VERSION = "10.2.4"')
launcher.write_text(s,encoding='utf-8')

iss=APP/'desktop_installer.iss'
s=iss.read_text(encoding='utf-8')
s=s.replace('#define MyAppVersion "10.2.3"','#define MyAppVersion "10.2.4"')
s=s.replace('Topaloglu-Pazaryeri-Merkezi-Setup-10.2.3','Topaloglu-Pazaryeri-Merkezi-Setup-10.2.4')
iss.write_text(s,encoding='utf-8')
(APP/'DESKTOP_VERSION.txt').write_text('10.2.4\n',encoding='utf-8')

# ----- HTML: fixed version + real boot overlay -----
idx=APP/'app/static/index.html'
h=idx.read_text(encoding='utf-8')
h=h.replace('v10.2.3','v10.2.4')
h=h.replace('<body class="premium-v2">','<body class="premium-v2 premium-v3">',1)

boot=r'''
<div id="meteBoot" class="mete-boot" aria-hidden="true">
  <div class="mete-scanlines"></div>
  <div class="mete-terminal">
    <div class="mete-terminal-top"><span></span><span></span><span></span><b>TOPOLOGLU // SECURE CONSOLE</b></div>
    <div id="meteBootLines" class="mete-boot-lines"></div>
    <div class="mete-word-wrap">
      <span class="mete-prefix">SYSTEM USER //</span>
      <div class="mete-word" data-text="METE">METE<span class="mete-cursor">_</span></div>
    </div>
    <div class="mete-progress"><i id="meteProgress"></i></div>
    <div class="mete-ready" id="meteReady">PAZARYERİ KONTROL MERKEZİ HAZIRLANIYOR</div>
  </div>
</div>
'''
if 'id="meteBoot"' not in h:
    h=h.replace('<body class="premium-v2 premium-v3">','<body class="premium-v2 premium-v3">\n'+boot,1)

if '/static/mete_boot.js?v=10.2.4' not in h:
    h=h.replace('</body>','<script src="/static/mete_boot.js?v=10.2.4"></script>\n</body>',1)
idx.write_text(h,encoding='utf-8')

# ----- standalone boot JS -----
boot_js=r'''(function(){
  const boot=document.getElementById('meteBoot');
  if(!boot)return;
  // Only once for the current desktop window session.
  if(sessionStorage.getItem('mete_boot_seen')==='1'){
    boot.remove();
    document.body.classList.add('mete-app-ready');
    return;
  }
  sessionStorage.setItem('mete_boot_seen','1');

  const lines=[
    '[00:00:01] initializing marketplace guard...',
    '[00:00:02] loading ET product filter ........ OK',
    '[00:00:03] binding price protection engine .. OK',
    '[00:00:04] alert tolerance .................. 1300 TL',
    '[00:00:05] critical-only wallboard .......... ACTIVE',
    '[00:00:06] secure local environment .......... READY'
  ];
  const box=document.getElementById('meteBootLines');
  const prog=document.getElementById('meteProgress');
  const ready=document.getElementById('meteReady');
  let i=0;
  function add(){
    if(i>=lines.length)return;
    const row=document.createElement('div');
    row.className='mete-line';
    row.innerHTML='<span>&gt;</span> '+lines[i].replace('OK','<b>OK</b>').replace('ACTIVE','<b>ACTIVE</b>').replace('READY','<b>READY</b>');
    box.appendChild(row);
    requestAnimationFrame(()=>row.classList.add('show'));
    i++;
    if(i<lines.length)setTimeout(add,185);
  }
  setTimeout(add,120);
  requestAnimationFrame(()=>{prog.style.width='100%'});
  setTimeout(()=>ready.classList.add('show'),1080);
  setTimeout(()=>boot.classList.add('mete-boot-out'),2050);
  setTimeout(()=>{
    boot.remove();
    document.body.classList.add('mete-app-ready');
  },2500);
})();'''
(APP/'app/static/mete_boot.js').write_text(boot_js,encoding='utf-8')

# ----- premium visual refresh: CSS-only, preserving all existing behavior -----
css=APP/'app/static/style.css'
cs=css.read_text(encoding='utf-8')
cs += r'''

/* v10.2.4 — premium desktop refresh */
:root{
  --p-bg:#07090d;--p-panel:#10141c;--p-panel2:#0c1017;--p-line:rgba(255,255,255,.075);
  --p-gold:#d8b866;--p-gold2:#f0d98d;--p-text:#f3f5f8;--p-muted:#8b96a8;
  --p-red:#ff5f68;--p-green:#57d99b;--p-amber:#f2bd5c;
}
html,body{background:var(--p-bg)!important}.premium-v3{color:var(--p-text);font-feature-settings:'tnum' 1,'ss01' 1}
.premium-v3 .shell{background:
  radial-gradient(circle at 82% 8%,rgba(216,184,102,.055),transparent 28%),
  radial-gradient(circle at 16% 88%,rgba(66,105,160,.045),transparent 30%),#080b10}
.premium-v3 .sidebar{background:linear-gradient(180deg,#0c1017 0%,#080b10 100%);border-right:1px solid var(--p-line);box-shadow:18px 0 55px rgba(0,0,0,.18)}
.premium-v3 .brand{padding-bottom:22px;margin-bottom:12px;border-bottom:1px solid rgba(255,255,255,.06)}
.premium-v3 .brand-icon{background:linear-gradient(145deg,#f0d98d,#a57c28);color:#17120a;box-shadow:0 8px 28px rgba(216,184,102,.18);border:1px solid rgba(255,255,255,.17)}
.premium-v3 .brand strong{letter-spacing:-.01em}.premium-v3 .brand span{color:#7e899c}
.premium-v3 .nav{border:1px solid transparent;border-radius:12px;margin:3px 0;transition:.18s ease;color:#9da7b7}
.premium-v3 .nav:hover{background:rgba(255,255,255,.035);color:#e7ebf1;transform:translateX(2px)}
.premium-v3 .nav.active{background:linear-gradient(90deg,rgba(216,184,102,.15),rgba(216,184,102,.045));border-color:rgba(216,184,102,.16);color:#f2dc98;box-shadow:inset 3px 0 0 #d8b866}
.premium-v3 .sidebar-card,.premium-v3 .notification-state{background:rgba(255,255,255,.025);border:1px solid var(--p-line);border-radius:14px}
.premium-v3 .main{padding:28px 32px 42px}
.premium-v3 .header{padding:4px 0 22px;margin-bottom:4px;border-bottom:1px solid rgba(255,255,255,.045)}
.premium-v3 .header h1{font-size:34px;letter-spacing:-.04em;background:linear-gradient(90deg,#fff,#b9c0cb);-webkit-background-clip:text;color:transparent}
.premium-v3 .header p{color:#7f8999}.premium-v3 .eyebrow{color:#c6ad6b;letter-spacing:.14em;font-weight:700}
.premium-v3 .btn{border-radius:11px;min-height:40px;transition:.18s ease;font-weight:650}
.premium-v3 .btn.primary{background:linear-gradient(135deg,#e0c06d,#b38b33);color:#141008;border:0;box-shadow:0 8px 24px rgba(216,184,102,.13)}
.premium-v3 .btn.primary:hover{transform:translateY(-1px);box-shadow:0 10px 30px rgba(216,184,102,.2)}
.premium-v3 .btn.ghost{background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.08);color:#c9d0dc}
.premium-v3 .glass,.premium-v3 .panel{background:linear-gradient(145deg,rgba(18,23,32,.93),rgba(12,16,23,.93));border:1px solid var(--p-line);box-shadow:0 16px 45px rgba(0,0,0,.16);backdrop-filter:blur(16px)}
.premium-v3 .wall-status{border-radius:22px;padding:28px 30px;overflow:hidden;position:relative}
.premium-v3 .wall-status:after{content:'';position:absolute;inset:auto -12% -80% 42%;height:180px;background:radial-gradient(circle,rgba(216,184,102,.08),transparent 68%);pointer-events:none}
.premium-v3 .wall-copy h1{font-size:42px;letter-spacing:-.045em;margin-top:3px}.premium-v3 .wall-copy p{color:#929cad}
.premium-v3 .wall-kpis{gap:14px;margin:14px 0}.premium-v3 .wall-kpis article{border-radius:17px;background:linear-gradient(145deg,#111620,#0c1017);border:1px solid var(--p-line);padding:20px 22px;box-shadow:0 12px 35px rgba(0,0,0,.13)}
.premium-v3 .wall-kpis strong{font-size:34px;letter-spacing:-.035em}.premium-v3 .wall-kpis span{font-size:11px;letter-spacing:.09em;color:#919cad;text-transform:uppercase}
.premium-v3 .wall-panel{border-radius:20px;background:linear-gradient(145deg,#10151e,#0b0f16);border:1px solid var(--p-line);overflow:hidden}
.premium-v3 .wall-head{padding:22px 24px;border-bottom:1px solid rgba(255,255,255,.055)}
.premium-v3 .market-card,.premium-v3 .metric-card,.premium-v3 .hero-card{border-radius:18px!important;overflow:hidden;position:relative}
.premium-v3 .market-card:before,.premium-v3 .metric-card:before{content:'';position:absolute;left:0;right:0;top:0;height:1px;background:linear-gradient(90deg,transparent,rgba(255,255,255,.13),transparent)}
.premium-v3 table{border-collapse:separate;border-spacing:0}.premium-v3 thead th{position:sticky;top:0;z-index:2;background:#0d1118;color:#7e899a;font-size:10px;letter-spacing:.075em;text-transform:uppercase;border-bottom:1px solid rgba(255,255,255,.07);padding-top:13px;padding-bottom:13px}
.premium-v3 tbody td{border-bottom:1px solid rgba(255,255,255,.045);padding-top:13px;padding-bottom:13px}.premium-v3 tbody tr{transition:.15s ease}.premium-v3 tbody tr:hover{background:rgba(255,255,255,.025)}
.premium-v3 input,.premium-v3 select{border-radius:10px!important;background:#0a0e14!important;border:1px solid rgba(255,255,255,.085)!important;color:#dfe4ec!important;outline:none}.premium-v3 input:focus,.premium-v3 select:focus{border-color:rgba(216,184,102,.45)!important;box-shadow:0 0 0 3px rgba(216,184,102,.07)!important}
.premium-v3 .badge{border-radius:999px;padding:5px 9px;font-size:10px;font-weight:750;letter-spacing:.04em}.premium-v3 code{font-family:'Cascadia Code','Consolas',monospace;color:#d7c17e}
.premium-v3 .settings-desktop-head{border-radius:20px!important}.premium-v3 .desktop-setting-row{background:linear-gradient(90deg,rgba(255,255,255,.022),rgba(255,255,255,.012));border-radius:13px}
.premium-v3 .desktop-version-card{padding:14px 18px;border:1px solid rgba(216,184,102,.14);background:rgba(216,184,102,.045);border-radius:13px}

/* METE terminal boot */
.mete-boot{position:fixed;inset:0;z-index:999999;background:#030504;color:#74f6a7;display:flex;align-items:center;justify-content:center;font-family:'Cascadia Code','Consolas','Courier New',monospace;transition:opacity .42s ease,transform .42s ease;overflow:hidden}
.mete-boot:before{content:'';position:absolute;inset:0;background:radial-gradient(circle at center,rgba(60,255,137,.055),transparent 48%),linear-gradient(90deg,rgba(0,255,103,.018) 1px,transparent 1px),linear-gradient(rgba(0,255,103,.014) 1px,transparent 1px);background-size:auto,42px 42px,42px 42px;opacity:.9}
.mete-scanlines{position:absolute;inset:0;pointer-events:none;background:repeating-linear-gradient(0deg,rgba(0,0,0,0) 0,rgba(0,0,0,0) 2px,rgba(52,255,123,.025) 3px);animation:meteScan 7s linear infinite}
.mete-terminal{width:min(760px,82vw);position:relative;padding:1px;border:1px solid rgba(89,255,151,.19);background:rgba(3,8,5,.84);box-shadow:0 0 0 1px rgba(0,0,0,.9),0 0 80px rgba(42,255,118,.055);border-radius:10px;overflow:hidden}
.mete-terminal-top{height:38px;display:flex;align-items:center;gap:7px;padding:0 13px;border-bottom:1px solid rgba(89,255,151,.13);background:rgba(60,255,128,.025);font-size:10px;letter-spacing:.11em;color:#4e9b69}.mete-terminal-top span{width:8px;height:8px;border-radius:50%;background:#163b23}.mete-terminal-top b{margin-left:7px;font-weight:500}
.mete-boot-lines{height:190px;padding:20px 24px 5px;font-size:12px;line-height:1.85;color:#4da36c}.mete-line{opacity:0;transform:translateY(5px);transition:.16s ease}.mete-line.show{opacity:1;transform:none}.mete-line span{color:#285e3b}.mete-line b{color:#8affb5;font-weight:600;text-shadow:0 0 12px rgba(89,255,151,.28)}
.mete-word-wrap{padding:8px 24px 20px}.mete-prefix{font-size:9px;letter-spacing:.18em;color:#326945}.mete-word{position:relative;margin-top:4px;font-size:70px;line-height:.95;font-weight:800;letter-spacing:.11em;color:#91ffb9;text-shadow:0 0 18px rgba(68,255,134,.24),0 0 60px rgba(68,255,134,.08);animation:meteFlicker 2.4s steps(1,end) infinite}.mete-word:before{content:attr(data-text);position:absolute;left:2px;top:0;color:#3fff86;opacity:.12;clip-path:inset(35% 0 45% 0);transform:translateX(-2px)}.mete-cursor{animation:meteCursor .68s steps(1,end) infinite;color:#c6ffd9}
.mete-progress{height:2px;background:#0b2113}.mete-progress i{display:block;width:0;height:100%;background:#66ff9d;box-shadow:0 0 16px #43ff88;transition:width 1.75s cubic-bezier(.15,.7,.15,1)}
.mete-ready{padding:11px 24px 13px;font-size:9px;letter-spacing:.19em;color:#2b6340;opacity:0;transition:.3s ease}.mete-ready.show{opacity:1;color:#5aaa76}
.mete-boot-out{opacity:0;transform:scale(1.015);pointer-events:none}.mete-app-ready .shell{animation:meteAppIn .36s ease both}
@keyframes meteCursor{0%,48%{opacity:1}49%,100%{opacity:0}}@keyframes meteFlicker{0%,94%,100%{opacity:1}95%{opacity:.82}96%{opacity:1}97%{opacity:.88}}@keyframes meteScan{from{transform:translateY(-12px)}to{transform:translateY(12px)}}@keyframes meteAppIn{from{opacity:0;transform:scale(.995)}to{opacity:1;transform:none}}
@media(max-width:900px){.premium-v3 .main{padding:20px 18px 32px}.premium-v3 .wall-copy h1{font-size:34px}.mete-terminal{width:90vw}.mete-word{font-size:50px}.mete-boot-lines{height:170px;font-size:10px}}
'''
css.write_text(cs,encoding='utf-8')

# Assertions
hi=idx.read_text(encoding='utf-8')
assert 'v10.2.4' in hi
assert 'id="meteBoot"' in hi
assert 'mete_boot.js?v=10.2.4' in hi
assert (APP/'app/static/mete_boot.js').exists()
assert 'METE' in (APP/'app/static/mete_boot.js').read_text(encoding='utf-8') or 'METE' in hi
assert 'premium desktop refresh' in css.read_text(encoding='utf-8')
print(APP)
