from pathlib import Path

ROOT=Path('_desktop_src')
apps=[p for p in ROOT.iterdir() if p.is_dir() and (p/'app').is_dir()]
if not apps: raise SystemExit('desktop source root not found')
APP=apps[0]

# Fix installer AppId to a stable valid GUID.
iss=APP/'desktop_installer.iss'
s=iss.read_text(encoding='utf-8')
s=s.replace('AppId={{7C25CB53-EB46-4ED4-AF2B-TOPOLOG10200}', 'AppId={{7C25CB53-EB46-4ED4-AF2B-102000000001}')
iss.write_text(s,encoding='utf-8')

# Desktop mode marker in health endpoint so browser-only updater controls can be hidden.
main=APP/'app/main.py'
s=main.read_text(encoding='utf-8')
if 'import os\n' not in s[:200]:
    s=s.replace('from pathlib import Path\n','from pathlib import Path\nimport os\n',1)
needle='return {"ok":True,"interval":settings.interval_minutes,"alert_tolerance_tl":settings.alert_tolerance_tl,'
if needle in s:
    s=s.replace(needle,'return {"ok":True,"desktop":os.getenv("TOPOLOGLU_DESKTOP")=="1","desktop_version":os.getenv("TOPOLOGLU_DESKTOP_VERSION",""),"interval":settings.interval_minutes,"alert_tolerance_tl":settings.alert_tolerance_tl,',1)
main.write_text(s,encoding='utf-8')

js=APP/'app/static/app.js'
s=js.read_text(encoding='utf-8')
needle="  $('#tolChip').textContent=money(H.alert_tolerance_tl||1000);"
patch="  $('#tolChip').textContent=money(H.alert_tolerance_tl||1000);\n  if(H.desktop){const p=$('#updatePill');if(p){const v=$('#updateVersion');if(v)v.textContent='Masaüstü v'+(H.desktop_version||'10.2.0');$('#updateCheckBtn')?.classList.add('hidden');$('#updateInstallBtn')?.classList.add('hidden');}}"
if needle in s and 'H.desktop' not in s:
    s=s.replace(needle,patch,1)
js.write_text(s,encoding='utf-8')

print(APP)
