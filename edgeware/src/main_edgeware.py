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
    from threading import Thread

    from paths import Data

    # Fix scaling on high resolution displays
    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(0)  # Tell Windows that you aren't DPI aware.
    except Exception:
        pass  # Fails on non-Windows systems or if shcore is not available

    # Add mpv to PATH
    os.environ["PATH"] += os.pathsep + str(Data.ROOT)

    def pyglet_run() -> None:
        import pyglet

        pyglet.app.run()

    Thread(target=pyglet_run, daemon=True).start()  # Required for pyglet events

import json
import logging
import random
from threading import Thread
from tkinter import Tk

import utils
from config import first_launch_configure
from config.settings import Settings
from features.audio import play_audio
from features.corruption import corruption_danger_check, handle_corruption
from features.drive import fill_drive, replace_images
from features.hibernate import main_hibernate, start_main_hibernate
from features.image_popup import ImagePopup
from features.misc import (
    handle_discord,
    handle_keyboard,
    handle_mitosis_mode,
    handle_panic_lockout,
    handle_wallpaper,
    make_desktop_icons,
    make_tray_icon,
    open_web,
    send_notification,
)
from features.prompt import Prompt
from features.startup_splash import StartupSplash
from features.subliminal_popup import SubliminalPopup
from features.video_popup import VideoPopup
from os_utils import is_linux
from os_utils.linux_utils import get_desktop_environment
from pack import Pack
from panic import ensure_panic_wallpaper, start_panic_listener
from paths import Data
from roll import RollTarget, roll_targets
from scripting import run_script
from state import State


def read_do_not_press_armed() -> bool:
    """"Do Not Press" is a config.pyw-only feature, not a real Settings/Item,
    so its flag has to be read directly from the config file rather than
    through Settings - see config.pyw's own comments for the full explanation
    of what this does and why. Never crashes startup if this is missing or
    malformed; it just means the feature is treated as off."""
    try:
        return bool(json.loads(Data.CONFIG.read_text()).get("_doNotPressArmed", 0))
    except Exception:
        return False


def pick_random_pack_path():
    if not Data.PACKS.is_dir():
        return None
    packs = [p for p in Data.PACKS.iterdir() if p.is_dir()]
    return random.choice(packs) if packs else None


def main(root: Tk, settings: Settings, pack: Pack, targets: list[RollTarget]) -> None:
    roll_targets(settings, targets)
    Thread(target=lambda: fill_drive(root, settings, pack, state), daemon=True).start()  # Thread for performance reasons
    root.after(settings.delay, lambda: main(root, settings, pack, targets))


if __name__ == "__main__":
    utils.init_logging("main")

    first_launch_configure()

    root = Tk()
    root.withdraw()
    settings = Settings()
    ensure_panic_wallpaper()  # Before pack/wallpaper handling, so Panic never falls back to a generic image

    do_not_press = read_do_not_press_armed()
    if do_not_press:
        random_pack = pick_random_pack_path()
        if random_pack is not None:
            settings.pack_path = random_pack
        # Force panic lockout on for this session regardless of the saved
        # setting, in case config.pyw's own write of it didn't take for some
        # reason - the whole point of this feature is that this is never
        # skipped by accident.
        settings.panic_lockout = True

    pack = Pack(settings.pack_path)
    state = State()

    settings.corruption_mode = settings.corruption_mode and pack.corruption_levels
    corruption_danger_check(settings, pack)

    # TODO: Use a dict?
    targets = [
        RollTarget(lambda: ImagePopup(root, settings, pack, state), lambda: settings.image_chance if not settings.mitosis_mode else 0),
        RollTarget(lambda: VideoPopup(root, settings, pack, state), lambda: settings.video_chance if not settings.mitosis_mode else 0),
        RollTarget(lambda: SubliminalPopup(settings, pack), lambda: settings.subliminal_chance),
        RollTarget(lambda: Prompt(settings, pack, state), lambda: settings.prompt_chance),
        RollTarget(lambda: play_audio(root, settings, pack, state), lambda: settings.audio_chance),
        RollTarget(lambda: open_web(pack), lambda: settings.web_chance),
        RollTarget(lambda: send_notification(settings, pack), lambda: settings.notification_chance),
    ]

    # For some reason, when two windows are spawned very quickly, some WMs will place the most
    # recent one /below/ the other rather than on top. This can cause subliminals to be occluded.
    if is_linux() and get_desktop_environment() in ("i3", "dwm", "bspwm", "xmonad", "openbox"):
        targets = targets[::-1]

    def start_main() -> None:
        make_tray_icon(root, settings, pack, state, lambda: main_hibernate(root, settings, pack, state, targets))
        make_desktop_icons(settings)
        if not do_not_press:
            # Already started immediately below instead, so panic (and its
            # lockout) is live for the whole silent wait, not just from here.
            handle_keyboard(root, settings, state)
            start_panic_listener(root, settings, state)
        Thread(target=lambda: replace_images(settings, pack), daemon=True).start()  # Thread for performance reasons
        handle_corruption(root, settings, pack, state)
        handle_discord(settings, pack)
        if not do_not_press:
            handle_panic_lockout(root, settings, state)
        handle_mitosis_mode(root, settings, pack, state)
        run_script(root, settings, pack, state)

        if settings.hibernate_mode:
            start_main_hibernate(root, settings, pack, state, targets)
        else:
            handle_wallpaper(root, settings, pack, state)
            main(root, settings, pack, targets)

    if do_not_press:
        # Panic (and its lockout) start right away, before the wait below,
        # not inside start_main() - the point of this feature is that panic
        # is reachable (gated by the safeword/lockout timer, same as normal)
        # for the entire wait, not only once something visible happens.
        handle_keyboard(root, settings, state)
        start_panic_listener(root, settings, state)
        handle_panic_lockout(root, settings, state)
        delay_ms = int(random.uniform(5, 90) * 60 * 1000)
        logging.info(f"Do Not Press is armed: waiting {delay_ms / 60000:.1f} minutes before starting")
        if settings.startup_splash:
            root.after(delay_ms, lambda: StartupSplash(settings, pack, start_main))
        else:
            root.after(delay_ms, start_main)
    elif settings.startup_splash:
        StartupSplash(settings, pack, start_main)
    else:
        start_main()

    root.mainloop()
