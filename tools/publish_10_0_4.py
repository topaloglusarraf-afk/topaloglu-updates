from pathlib import Path
import hashlib, json, shutil, urllib.request, zipfile

ROOT = Path.cwd()
SOURCE_URL = "https://raw.githubusercontent.com/topaloglusarraf-afk/topaloglu-updates/main/update-10.0.3.zip"
SOURCE = ROOT / "_source-10.0.3.zip"
WORK = ROOT / "_build-10.0.4"
OUT = ROOT / "update-10.0.4.zip"

urllib.request.urlretrieve(SOURCE_URL, SOURCE)
if WORK.exists():
    shutil.rmtree(WORK)
WORK.mkdir()
with zipfile.ZipFile(SOURCE, "r") as z:
    z.extractall(WORK)

app = WORK / "Topaloglu-Pazaryeri-Merkezi"
if not app.exists():
    raise SystemExit("Update package root not found")

# Alarm tolerance: migrate the legacy 500 TL default to 1,000 TL without
# overwriting other custom values in the user's persistent .env.
p = app / "app/config.py"
s = p.read_text(encoding="utf-8")
s = s.replace(
    'alert_tolerance_tl: float = float(os.getenv("ALERT_TOLERANCE_TL", "500"))',
    '_alert_tolerance_raw = os.getenv("ALERT_TOLERANCE_TL", "").strip()\n    # v10.0.4: migrate legacy 500 TL default to 1,000 TL.\n    alert_tolerance_tl: float = 1000.0 if _alert_tolerance_raw in ("", "500", "500.0") else float(_alert_tolerance_raw)'
)
p.write_text(s, encoding="utf-8")

p = app / "app/service.py"
s = p.read_text(encoding="utf-8").replace("settings.alert_tolerance_tl or 500", "settings.alert_tolerance_tl or 1000")
p.write_text(s, encoding="utf-8")

p = app / "app/static/index.html"
s = p.read_text(encoding="utf-8")
s = s.replace('<strong id="tolChip">500 TL</strong>', '<strong id="tolChip">1.000 TL</strong>')
s = s.replace("Pazaryeri Merkezi v10.0.3", "Pazaryeri Merkezi v10.0.4")
s = s.replace("/static/style.css?v=10.0.3", "/static/style.css?v=10.0.4")
s = s.replace("/static/app.js?v=10.0.3", "/static/app.js?v=10.0.4")
p.write_text(s, encoding="utf-8")

p = app / "app/static/app.js"
s = p.read_text(encoding="utf-8").replace("H.alert_tolerance_tl||500", "H.alert_tolerance_tl||1000")
p.write_text(s, encoding="utf-8")

p = app / ".env.example"
s = p.read_text(encoding="utf-8").replace("ALERT_TOLERANCE_TL=500", "ALERT_TOLERANCE_TL=1000")
p.write_text(s, encoding="utf-8")

(app / "VERSION").write_text("10.0.4", encoding="utf-8")

p = app / "README.md"
s = p.read_text(encoding="utf-8").replace("10.0.3", "10.0.4")
s += "\n\n## 10.0.4 — Alarm toleransı\n- Alarm toleransı 500 TL'den 1.000 TL'ye yükseltildi.\n- Eski sabit .env içindeki 500 TL değeri kullanıcı verisini silmeden 1.000 TL'ye taşınır.\n- 500 TL dışında özel bir tolerans tanımlıysa korunur.\n"
p.write_text(s, encoding="utf-8")

if OUT.exists():
    OUT.unlink()
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for f in app.rglob("*"):
        if f.is_file() and "__pycache__" not in f.parts:
            z.write(f, Path("Topaloglu-Pazaryeri-Merkezi") / f.relative_to(app))

sha = hashlib.sha256(OUT.read_bytes()).hexdigest()
manifest = {
    "version": "10.0.4",
    "published_at": "2026-08-14",
    "notes": "Alarm toleransı 500 TL'den 1.000 TL'ye yükseltildi.",
    "package_url": "https://raw.githubusercontent.com/topaloglusarraf-afk/topaloglu-updates/main/update-10.0.4.zip",
    "sha256": sha,
}
(ROOT / "latest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

shutil.rmtree(WORK, ignore_errors=True)
SOURCE.unlink(missing_ok=True)
print("Built", OUT, sha)
