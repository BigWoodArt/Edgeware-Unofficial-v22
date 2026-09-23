# Copyright (C) 2024 Araten & Marigold
#
# This file is part of Edgeware++.
#
# Edgeware++ is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Edgeware++ is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Edgeware++.  If not, see <https://www.gnu.org/licenses/>.

if __name__ == "__main__":
    import os

    from paths import Data

    # Fix scaling on high resolution displays
    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(0)  # Tell Windows that you aren't DPI aware.
    except Exception:
        pass  # Fails on non-Windows systems or if shcore is not available

    # Add mpv to PATH
    os.environ["PATH"] += os.pathsep + str(Data.ROOT)
    try:
        # PATH alone isn't reliably picked up by ctypes-based DLL loading on
        # Windows since Python 3.8 ("safe DLL search mode") - this is the
        # actually-reliable way to point it at libmpv-2.dll. Kept the PATH
        # line above too since it's harmless and may still help in some
        # setups; this is the one that actually matters on modern Python.
        os.add_dll_directory(str(Data.ROOT))
    except (AttributeError, OSError):
        pass  # Not on Windows, or the directory doesn't exist yet

import importlib.util
import logging
import sys
import traceback
from tkinter import Tk, messagebox

# Same set of third-party packages config.pyw checks for at startup - checked
# here too, and before the ConfigWindow import below, since that import
# itself would otherwise crash uncaught (raw traceback, no dialog) on a
# fresh checkout that never had EdgewareSetup.bat run against it.
REQUIRED_PACKAGES = {
    "mpv": "video/audio playback",
    "PIL": "image handling",
    "requests": "web features (booru search, checking for updates)",
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
    "tkinterweb": "in-app web content",
    "ttkwidgets": "this interface's mood checklist",
    "tktooltip": "this interface's tooltips",
}
if sys.platform == "win32":
    REQUIRED_PACKAGES["win32com"] = "Windows-specific integration"

if __name__ == "__main__":
    missing = [f"{name} ({REQUIRED_PACKAGES[name]})" for name in REQUIRED_PACKAGES if importlib.util.find_spec(name) is None]
    if missing:
        fix = "Run EdgewareSetup.bat in this folder to install everything automatically." if sys.platform == "win32" else "Run: pip install -r requirements.txt"
        _root = Tk(); _root.withdraw()
        messagebox.showerror("Edgeware++ Config", "This interface can't start - missing Python packages:\n\n  - " + "\n  - ".join(sorted(missing)) + f"\n\n{fix}")
        _root.destroy()
        sys.exit(1)

from config.window import ConfigWindow

if __name__ == "__main__":
    try:
        ConfigWindow()
    except Exception as e:
        logging.fatal(f"Config encountered fatal error: {e}\n\n{traceback.format_exc()}")
        messagebox.showerror("Could not start", f"Could not start config.\n[{e}]")
