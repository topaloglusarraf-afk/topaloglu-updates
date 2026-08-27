from pathlib import Path
import shutil, urllib.request, zipfile

ROOT = Path.cwd()
BASE_URL = "https://raw.githubusercontent.com/topaloglusarraf-afk/topaloglu-updates/main/"
ZIP = ROOT / "_desktop_base_1010.zip"
WORK = ROOT / "_desktop_src"

urllib.request.urlretrieve(BASE_URL + "update-10.1.0.zip", ZIP)
shutil.rmtree(WORK, ignore_errors=True)
WORK.mkdir(parents=True)
with zipfile.ZipFile(ZIP, "r") as z:
    z.extractall(WORK)

candidates = [p for p in WORK.iterdir() if p.is_dir() and (p / "app").is_dir()]
if not candidates:
    raise SystemExit("Uygulama kökü bulunamadı")
APP = candidates[0]

# Cumulative latest source overlays.
overlays = {
    "app/db.py": "direct/10.1.4/app/db.py",
    "app/service.py": "direct/10.1.4/app/service.py",
    "app/main.py": "direct/10.1.4/app/main.py",
    "app/static/index.html": "direct/10.1.2/app/static/index.html",
    "app/static/app.js": "direct/10.1.5/app/static/app.js",
    "app/static/style.css": "direct/10.1.5/app/static/style.css",
}
for target, remote in overlays.items():
    dest = APP / target
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(BASE_URL + remote, dest)

launcher = r'''from pathlib import Path
import os, sys, threading, time, urllib.request, socket

APP_NAME = "Topaloğlu Pazaryeri Merkezi"
VERSION = "10.2.0"


def data_dir():
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    p = Path(base) / "Topaloglu" / "PazaryeriMerkezi"
    p.mkdir(parents=True, exist_ok=True)
    (p / "data").mkdir(parents=True, exist_ok=True)
    return p


def load_env_file(path: Path):
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def find_free_port(preferred=8765):
    for port in (preferred, 8766, 8767, 8768, 8877):
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", port))
            s.close()
            return port
        except OSError:
            s.close()
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close(); return port


def wait_ready(url, seconds=20):
    until = time.time() + seconds
    while time.time() < until:
        try:
            with urllib.request.urlopen(url + "/api/health", timeout=1.5) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.25)
    return False


def main():
    d = data_dir()
    os.chdir(d)
    os.environ["TOPOLOGLU_DESKTOP"] = "1"
    os.environ["TOPOLOGLU_DESKTOP_VERSION"] = VERSION
    load_env_file(d / ".env")

    port = find_free_port(int(os.environ.get("TOPOLOGLU_DESKTOP_PORT", "8765")))
    url = f"http://127.0.0.1:{port}"

    import uvicorn
    from app.main import app

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="TopalogluLocalServer", daemon=True)
    thread.start()
    if not wait_ready(url):
        raise RuntimeError("Yerel uygulama servisi başlatılamadı.")

    import webview
    window = webview.create_window(
        APP_NAME,
        url,
        width=1500,
        height=920,
        min_size=(1050, 680),
        text_select=True,
        confirm_close=False,
    )
    try:
        webview.start(debug=False, private_mode=False)
    finally:
        server.should_exit = True
        thread.join(timeout=3)


if __name__ == "__main__":
    main()
'''
(APP / "desktop_launcher.py").write_text(launcher, encoding="utf-8")

# Desktop build requirements are separate from the application's runtime requirements.
(APP / "desktop_requirements.txt").write_text(
    "pywebview>=5.4,<7\npyinstaller>=6.10,<7\n",
    encoding="utf-8",
)

# Build metadata for Inno Setup.
iss = r'''#define MyAppName "Topaloglu Pazaryeri Merkezi"
#define MyAppVersion "10.2.0"
#define MyAppExeName "Topaloglu Pazaryeri Merkezi.exe"

[Setup]
AppId={{7C25CB53-EB46-4ED4-AF2B-TOPOLOG10200}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\Topaloglu Pazaryeri Merkezi
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=installer
OutputBaseFilename=Topaloglu-Pazaryeri-Merkezi-Setup-10.2.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UninstallDisplayName={#MyAppName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "dist\Topaloglu Pazaryeri Merkezi\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName} uygulamasını aç"; Flags: nowait postinstall skipifsilent
'''
(APP / "desktop_installer.iss").write_text(iss, encoding="utf-8")

# A tiny marker used in support/diagnostics.
(APP / "DESKTOP_VERSION.txt").write_text("10.2.0\n", encoding="utf-8")

print(APP)
