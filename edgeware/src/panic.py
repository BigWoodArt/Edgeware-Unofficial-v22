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

import hashlib
import logging
import shutil
from multiprocessing.connection import Client, Listener
from pathlib import Path
from threading import Thread
from tkinter import Button, Entry, Label, TclError, Tk, Toplevel

import pyglet
from config.settings import Settings
from os_utils import get_wallpaper, set_wallpaper
from paths import CustomAssets, Data
from PIL import Image
from state import State

ADDRESS = ("localhost", 6000)
AUTHKEY = b"Edgeware++"
PANIC_MESSAGE = "panic"

RELIFT_INTERVAL_MS = 250


def ask_panic_password(root: Tk) -> str | None:
    """Same job as tkinter.simpledialog.askstring(), but explicitly kept
    topmost - the built-in dialog never sets -topmost at all, so it can (and,
    per a direct report, did) get buried under Edgeware's own topmost popups
    almost immediately. Worse, its keyboard/mouse grab still routes all
    input to the now-invisible dialog underneath everything else,
    effectively locking the person out with no visible way to even see what
    they're typing into. Unlike the passive overlays elsewhere in this
    codebase that deliberately avoid stealing focus, this one is meant to be
    typed into right now, so re-claiming focus on every tick is the correct
    behavior here, not a disruption."""
    dialog = Toplevel(root)
    dialog.title("Panic")
    dialog.attributes("-topmost", True)
    dialog.resizable(False, False)
    dialog.protocol("WM_DELETE_WINDOW", lambda: None)  # Only submitting (or Panic's own cleanup) should close this

    result: dict[str, str | None] = {"value": None}

    Label(dialog, text="Enter Panic Password").pack(padx=16, pady=(16, 4))
    entry = Entry(dialog, show="*", width=30)
    entry.pack(padx=16, pady=(0, 8))
    entry.focus_set()

    def submit(event: object = None) -> None:  # noqa: ARG001 - unused, but <Return> passes one and the Button doesn't, so it needs a default either way
        result["value"] = entry.get()
        dialog.destroy()

    entry.bind("<Return>", submit)
    Button(dialog, text="Submit", command=submit).pack(pady=(0, 16))

    def relift() -> None:
        try:
            dialog.attributes("-topmost", False)
            dialog.attributes("-topmost", True)
            dialog.lift()
            dialog.focus_force()
            entry.focus_set()
        except TclError:
            return  # Already destroyed (submitted)
        dialog.after(RELIFT_INTERVAL_MS, relift)

    relift()
    dialog.grab_set()
    dialog.wait_window()
    return result["value"]


def panic(root: Tk, settings: Settings, state: State, condition: bool = True, disable: bool = True) -> None:
    def do_panic() -> None:
        if (disable and settings.panic_disabled) or not condition:
            return

        if settings.panic_lockout and state.panic_lockout_active:
            password = ask_panic_password(root)
            if password != settings.panic_lockout_password:
                return

        restore_panic_wallpaper()
        state.keyboard_process.terminate()
        if state.tray:
            state.tray.stop()
        for popup in state.popups.copy():
            popup.close()
        # Neither of these lived in state.popups (the spiral overlay is a
        # persistent ambient window, not a one-shot popup; the binaural
        # player was deliberately kept out of state.audio_players so it
        # never competes with real pack audio for a playback slot) - so
        # panic's cleanup never reached either one. Reported directly:
        # after Skip to Hibernate, Panic stopped tracked popups (and the
        # tray icon correctly disappeared) but left images/audio/the spiral
        # still running. Both already have their own close() - they just
        # were never being called.
        for overlay in state.spiral_overlays:
            overlay.close()
        if state.binaural_overlay:
            state.binaural_overlay.close()
        pyglet.app.exit()
        root.destroy()

    # Make sure panic code is executed in the main thread, otherwise
    # simpledialog will not work from most panic sources
    root.after(0, do_panic)


def start_panic_listener(root: Tk, settings: Settings, state: State) -> None:
    def listen() -> None:
        try:
            with Listener(address=ADDRESS, authkey=AUTHKEY) as listener:
                while True:
                    with listener.accept() as connection:
                        message = connection.recv()
                        if message == PANIC_MESSAGE:
                            panic(root, settings, state, disable=False)
        except OSError as e:
            logging.warning(f"Failed to start panic listener, some panic sources may not be functional. Reason: {e}")

    Thread(target=listen, daemon=True).start()


def send_panic() -> None:
    with Client(address=ADDRESS, authkey=AUTHKEY) as connection:
        connection.send(PANIC_MESSAGE)


def restore_panic_wallpaper() -> None:
    saved = CustomAssets.panic_wallpaper()

    try:
        # We restore from the original wallpaper file rather than Edgeware's copy to avoid issues
        # when installed on a USB drive or after uninstalling.
        original = Path(Data.PANIC_WALLPAPER_LINK.read_text()).resolve()
        # The content at `original` can drift from our saved snapshot for reasons
        # having nothing to do with settings.replace_images (which this used to be
        # gated behind): Windows itself regenerates its wallpaper cache file every
        # time the desktop wallpaper changes, including every change Edgeware's own
        # wallpaper cycling makes during a session. By the time Panic fires, that
        # path can easily no longer contain the real original wallpaper at all - so
        # this check now always runs, not just when Replace Images is on.
        with original.open("rb") as of, saved.open("rb") as sf:
            was_overwritten = hashlib.file_digest(of, "sha256") != hashlib.file_digest(sf, "sha256")
        if was_overwritten:
            shutil.copy2(saved, original)
    except (OSError, AssertionError):
        set_wallpaper(saved)
    else:
        set_wallpaper(original)


def ensure_panic_wallpaper() -> None:
    """If the user has never set a custom panic wallpaper (via "Set Panic
    Wallpaper" or "Auto Import" in the config window), Panic falls back to a
    generic bundled image that looks nothing like their desktop - the exact
    problem Panic exists to avoid. Call this once at startup, before anything
    else changes the wallpaper: it costs nothing if a panic wallpaper is
    already set, and otherwise captures whatever wallpaper is currently on
    screen so Panic has something that actually looks normal, without the
    user needing to remember a setup step first."""
    if Data.PANIC_WALLPAPER.is_file():
        return
    try:
        path = get_wallpaper()
        assert path is not None, "Auto-import not supported for your desktop environment"
        assert path.is_file(), "Auto-import returned a nonexistent file"
        image = Image.open(path).convert("RGB")
        image.save(Data.PANIC_WALLPAPER)
        Data.PANIC_WALLPAPER_LINK.write_text(str(path))
    except Exception as e:
        # Not fatal - restore_panic_wallpaper() already has its own fallback
        # to the bundled default if this never manages to run successfully.
        logging.warning(f"Failed to auto-capture a panic wallpaper at startup\n{e}")


if __name__ == "__main__":
    send_panic()
