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

import logging
import traceback
from tkinter import messagebox

from config.window import ConfigWindow

if __name__ == "__main__":
    try:
        ConfigWindow()
    except Exception as e:
        logging.fatal(f"Config encountered fatal error: {e}\n\n{traceback.format_exc()}")
        messagebox.showerror("Could not start", f"Could not start config.\n[{e}]")
