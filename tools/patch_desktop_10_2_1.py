from pathlib import Path

ROOT=Path('_desktop_src')
apps=[p for p in ROOT.iterdir() if p.is_dir() and (p/'app').is_dir()]
if not apps: raise SystemExit('desktop source root not found')
APP=apps[0]

launcher=APP/'desktop_launcher.py'
s=launcher.read_text(encoding='utf-8')
s=s.replace('VERSION = "10.2.0"','VERSION = "10.2.1"')
# PyInstaller --windowed may leave stdout/stderr as None. Uvicorn default logging calls isatty().
needle='    import uvicorn\n    from app.main import app\n\n    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False)'
replacement='    import uvicorn\n    from app.main import app\n\n    # Windowed EXE has no console streams; keep Uvicorn from configuring console formatters.\n    if sys.stdout is None:\n        sys.stdout = open(os.devnull, "w", encoding="utf-8")\n    if sys.stderr is None:\n        sys.stderr = open(os.devnull, "w", encoding="utf-8")\n    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False, log_config=None)'
if needle not in s:
    raise SystemExit('launcher uvicorn block not found')
s=s.replace(needle,replacement,1)
launcher.write_text(s,encoding='utf-8')

iss=APP/'desktop_installer.iss'
s=iss.read_text(encoding='utf-8')
s=s.replace('#define MyAppVersion "10.2.0"','#define MyAppVersion "10.2.1"')
s=s.replace('Topaloglu-Pazaryeri-Merkezi-Setup-10.2.0','Topaloglu-Pazaryeri-Merkezi-Setup-10.2.1')
iss.write_text(s,encoding='utf-8')

marker=APP/'DESKTOP_VERSION.txt'
marker.write_text('10.2.1\n',encoding='utf-8')

js=APP/'app/static/app.js'
s=js.read_text(encoding='utf-8')
s=s.replace("H.desktop_version||'10.2.0'","H.desktop_version||'10.2.1'")
js.write_text(s,encoding='utf-8')

print(APP)
