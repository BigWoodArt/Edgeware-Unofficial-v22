"""Startup checks that show a visible, plain-language warning instead of failing silently.

Uses only the standard library so it can run before any dependency is imported.
"""

import importlib.util
import logging
import os
import subprocess
import sys
from pathlib import Path
from tkinter import Tk

MIN_PYTHON = (3, 12)
ERROR_LIMIT = 5
ERROR_WINDOW_MS = 120_000
NO_POPUP_WAIT_MS = 90_000

REQUIRED_PACKAGES = {
    "mpv": "video/audio playback",
    "PIL": "image handling",
    "requests": "web features",
    "desktop_notifier": "desktop notifications",
    "pystray": "the system tray icon",
    "pynput": "the global panic hotkey",
    "pyglet": "audio playback",
    "pypresence": "Discord Rich Presence",
    "screeninfo": "multi-monitor support",
    "filetype": "media type detection",
    "videoprops": "video file inspection",
    "voluptuous": "config validation",
    "booru": "booru image downloading",
}
if sys.platform == "win32":
    REQUIRED_PACKAGES["win32com"] = "Windows-specific integration"

SETUP_FIX = (
    "Run EdgewareSetup.bat in the Edgeware folder. It installs everything needed." if sys.platform == "win32" else "Run: pip install -r requirements.txt"
)


def relaunch_with_python312(script: Path) -> None:
    """Windows only: if this Python lacks packages but Python 3.12 has them, run `script` under 3.12 and exit.

    EdgewareSetup.bat installs into 3.12 when the default Python is too new for some packages.
    Does nothing when already on 3.12, when 3.12 is missing packages, or after one relaunch.
    """
    if sys.platform != "win32" or sys.version_info[:2] == MIN_PYTHON or os.environ.get("EDGEWARE_RELAUNCHED"):
        return
    names = ",".join(f"'{name}'" for name in REQUIRED_PACKAGES)
    probe = f"import importlib.util as u,sys;print(sys.executable);sys.exit(0 if all(u.find_spec(n) for n in [{names}]) else 1)"
    try:
        result = subprocess.run(["py", "-3.12", "-c", probe], capture_output=True, text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode != 0:
            return
        python = Path(result.stdout.strip())
        pythonw = python.with_name("pythonw.exe")
        env = {**os.environ, "EDGEWARE_RELAUNCHED": "1"}
        subprocess.Popen(
            [str(pythonw if pythonw.exists() else python), str(script)],
            env=env,
            cwd=str(script.parent.parent if script.parent.name == "src" else script.parent),
        )
    except Exception:
        return
    sys.exit(0)


def show_error(title: str, message: str, warning: bool = False) -> None:
    """Shows a dialog. Falls back to stderr if Tk itself is unavailable."""
    try:
        from tkinter import Tk, messagebox

        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        (messagebox.showwarning if warning else messagebox.showerror)(title, message, parent=root)
        root.destroy()
    except Exception:
        print(f"{title}\n{message}", file=sys.stderr)


def preflight(root_dir: Path, script: Path) -> None:
    """Exits with a visible message if Python, packages or libmpv are unusable."""
    problems = []
    if sys.version_info < MIN_PYTHON:
        problems.append(
            f"Python {sys.version_info.major}.{sys.version_info.minor} is too old. Edgeware needs {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer.\n"
            "Fix: install the latest Python from python.org (tick 'Add to PATH'), then run EdgewareSetup.bat."
        )
    missing = sorted(f"{name} ({why})" for name, why in REQUIRED_PACKAGES.items() if importlib.util.find_spec(name) is None)
    if missing:
        relaunch_with_python312(script)
        problems.append("Missing Python packages:\n  - " + "\n  - ".join(missing) + f"\nFix: {SETUP_FIX}")
    if sys.platform == "win32" and not (root_dir / "libmpv-2.dll").exists():
        problems.append(
            "Video engine (libmpv-2.dll) is missing, so videos cannot play.\nFix: run EdgewareSetup.bat, or place libmpv-2.dll in the Edgeware 'data' folder."
        )
    if problems:
        show_error("Edgeware++ cannot start", "\n\n".join(problems))
        sys.exit(1)


def report_fatal(error: BaseException, log_dir: Path) -> None:
    show_error(
        "Edgeware++ crashed on startup",
        f"{type(error).__name__}: {error}\n\n"
        f"Details are in the newest file in:\n{log_dir}\n\n"
        "Try: run EdgewareSetup.bat again, pick a different pack, or reset settings in the config window.",
    )


class _ErrorCounter(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self.count = 0

    def emit(self, record: logging.LogRecord) -> None:  # noqa: ARG002
        self.count += 1


def start_watchdog(root: Tk, log_dir: Path, popups_expected: bool, attempts: list[int]) -> None:
    """Warns once if errors pile up early, or if nothing was ever attempted."""
    counter = _ErrorCounter()
    logging.getLogger().addHandler(counter)
    warned = []

    def warn(reason: str) -> None:
        if warned:
            return
        warned.append(1)
        show_error(
            "Edgeware++ is having trouble",
            f"{reason}\n\nLogs: {log_dir}\n\n"
            "Try: run EdgewareSetup.bat again, update Python (3.12+), "
            "disable hardware acceleration in config, or choose another pack. "
            "Send the newest log if you ask for help.",
            warning=True,
        )

    def check_errors() -> None:
        if counter.count >= ERROR_LIMIT:
            warn(f"{counter.count} errors occurred in the first two minutes. Popups may not be loading.")

    def check_alive() -> None:
        if popups_expected and not attempts[0]:
            warn("No popup has been attempted yet. Check your chances and pack settings.")

    root.after(ERROR_WINDOW_MS, check_errors)
    root.after(NO_POPUP_WAIT_MS, check_alive)
