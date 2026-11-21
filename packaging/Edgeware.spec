# PyInstaller spec for the one-click Edgeware.exe. Run through build_exe.ps1.
# Freezes Python + third-party libraries only; Edgeware's own scripts stay plain files in `app`.
import ast
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).parent
APP = ROOT / "edgeware"

# Everything the scripts import must be frozen, but PyInstaller only sees the launcher.
# So: read every import from Edgeware's own files and hand them over as hidden imports.
local_names = {p.stem for p in APP.rglob("*.py*")} | {p.name for p in APP.rglob("*") if p.is_dir()}
imported = set()
for file in list(APP.rglob("*.py")) + list(APP.rglob("*.pyw")):
    try:
        tree = ast.parse(file.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
imported = {name for name in imported if name not in local_names and name != "__future__"}

# Packages that load submodules, data files or DLLs dynamically get everything.
FULL = [
    "pyglet", "pynput", "pystray", "tkinterweb", "tkinterweb_tkhtml", "desktop_notifier", "ttkwidgets",
    "tktooltip", "booru", "videoprops", "pypresence", "screeninfo", "filetype", "voluptuous", "PIL",
    "win32com", "pythoncom", "pywintypes", "mpv", "requests",
]
hiddenimports = sorted(imported | {"tkinter", "tkinter.ttk", "tkinter.messagebox", "tkinter.filedialog", "win32timezone"})
datas, binaries = [], []
for package in FULL:
    try:
        d, b, h = collect_all(package)
    except Exception as error:  # package missing in the build environment: say so loudly
        print(f"WARNING: could not collect {package}: {error}", file=sys.stderr)
        continue
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=sorted(set(hiddenimports)),
    excludes=["ruff", "pytest", "IPython"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Edgeware",
    console=False,  # windowed: no black console window, like .pyw
    icon=str(APP / "assets" / "default_icon.ico"),
)
coll = COLLECT(exe, a.binaries, a.datas, name="Edgeware")
