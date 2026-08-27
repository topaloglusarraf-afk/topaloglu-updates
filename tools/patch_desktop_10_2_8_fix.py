from pathlib import Path

ROOT=Path('_desktop_src')
apps=[p for p in ROOT.iterdir() if p.is_dir() and (p/'app').is_dir()]
if not apps: raise SystemExit('desktop source root not found')
APP=apps[0]
idx=APP/'app/static/index.html'
h=idx.read_text(encoding='utf-8')
for name in ('style.css','app.js','desktop_settings.js','mete_boot.js','hepsiburada_bridge.js'):
    for old in ('10.2.7','10.2.6','10.2.5','10.2.4','10.2.3','10.1.5','10.1.2'):
        h=h.replace(f'/static/{name}?v={old}',f'/static/{name}?v=10.2.8')
idx.write_text(h,encoding='utf-8')
if '/static/hepsiburada_bridge.js?v=10.2.8' not in h:
    raise SystemExit('Hepsiburada bridge asset version not fixed')
print(APP)
