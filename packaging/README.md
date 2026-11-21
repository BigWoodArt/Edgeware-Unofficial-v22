# One-click Edgeware.exe

Build (needs Python 3.12+ with `edgeware/requirements.txt` and `pyinstaller` installed):

    powershell -ExecutionPolicy Bypass -File packaging\build_exe.ps1 -Zip

Result: `dist\Edgeware\Edgeware.exe` (and `dist\Edgeware.zip`). Users unzip and double-click `Edgeware.exe`; no Python needed.

- `Edgeware.exe` acts as a tiny Python interpreter for the scripts in the `app` folder (see `launcher.py`), so the app's own
  `subprocess.Popen([sys.executable, script])` calls keep working.
- `app\` holds Edgeware's plain source, packs, config and logs, so the built-in updater and user data keep working.
- Rebuilding in place keeps `app\data`.
