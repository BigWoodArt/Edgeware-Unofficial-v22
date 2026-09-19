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

import ctypes
import datetime
import logging
import os
import subprocess
import sys
import tempfile
from ctypes import windll
from pathlib import Path
from tkinter import Toplevel

import mpv
import win32com.client
from paths import PATH, CustomAssets, Process

PYW = {
    Process.CONFIG: PATH / "config.pyw",
    Process.MAIN: PATH / "edgeware.pyw",
    Process.PANIC: PATH / "panic.pyw",
}

DWMWA_TRANSITIONS_FORCEDISABLED = 3


def close_mpv(player: mpv.MPV) -> None:
    player.terminate()


def set_borderless(window: Toplevel) -> None:
    window.overrideredirect(True)
    _disable_dwm_transitions(window)


def _disable_dwm_transitions(window: Toplevel) -> None:
    # A third attempt at a real, twice-narrowed-down report: a brief,
    # transparent, blue-bordered window - just an outline, desktop/other
    # windows visible straight through it - appearing right before a video
    # popup's real content is ready, confirmed via frame capture to be a
    # distinct window from the popup itself. That's a known Windows DWM
    # (compositor) behavior: it can draw a window's creation/resize
    # transition (an outline/chrome) before the window's actual content has
    # been composited, so the still-unpainted client area shows whatever is
    # behind it. DWMWA_TRANSITIONS_FORCEDISABLED tells DWM to skip that
    # transition for this window entirely - a genuine Windows compositor
    # API, distinct in kind from both earlier attempts at this same report
    # (Tkinter's own withdraw/deiconify visibility timing, which broke
    # popups outright and was reverted in v22.2.8; and mpv's own window
    # property plus its subprocess launch flag, neither of which turned out
    # to be the actual cause). Best-effort and silently ignored on failure -
    # this is a cosmetic mitigation, never worth risking popup creation
    # itself over, which is exactly the mistake the first attempt made.
    try:
        hwnd = windll.user32.GetParent(window.winfo_id())
        value = ctypes.c_int(1)
        windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_TRANSITIONS_FORCEDISABLED, ctypes.byref(value), ctypes.sizeof(value))
    except Exception as e:
        logging.warning(f"Failed to disable DWM window transitions: {e}")


def set_clickthrough(window: Toplevel) -> None:
    ws_ex_layered = 0x00080000
    ws_ex_transparent = 0x00000020
    gwl_exstyle = -20

    hwnd = windll.user32.GetParent(window.winfo_id())
    ex_style = windll.user32.GetWindowLongW(hwnd, gwl_exstyle)
    ex_style |= ws_ex_transparent | ws_ex_layered
    windll.user32.SetWindowLongW(hwnd, gwl_exstyle, ex_style)


def get_wallpaper() -> Path | None:
    spi_getdeskwallpaper = 0x0073
    wallpaper = ctypes.create_unicode_buffer(260)  # Max path length on Windows
    ctypes.windll.user32.SystemParametersInfoW(spi_getdeskwallpaper, ctypes.sizeof(wallpaper), wallpaper, 0)
    return Path(wallpaper.value)


def set_wallpaper(wallpaper: Path) -> None:
    spi_setdeskwallpaper = 0x0014
    ctypes.windll.user32.SystemParametersInfoW(spi_setdeskwallpaper, 0, str(wallpaper), 0)


def open_directory(url: str) -> None:
    subprocess.Popen(f'explorer "{url}"')


def make_shortcut(title: str, process: Path, icon: Path, location: Path | None = None) -> None:
    filename = f"{title}.lnk"
    file = (location if location else Path(os.path.expanduser("~\\Desktop"))) / filename

    pyw_process = PYW[process]

    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".bat",
        delete=False,
    ) as bat:
        bat.writelines(
            [
                '@echo off\nset SCRIPT="%TEMP%\\%RANDOM%-%RANDOM%-%RANDOM%-%RANDOM%.vbs"\n',
                'echo Set oWS = WScript.CreateObject("WScript.Shell") >> %SCRIPT%\n',
                'echo sLinkFile = "' + str(file) + '" >> %SCRIPT%\n',
                "echo Set oLink = oWS.CreateShortcut(sLinkFile) >> %SCRIPT%\n",
                'echo oLink.WorkingDirectory = "' + str(pyw_process.parent) + '\\" >> %SCRIPT%\n',
                'echo oLink.IconLocation = "' + str(icon) + '" >> %SCRIPT%\n',
                'echo oLink.TargetPath = "' + str(pyw_process) + '" >> %SCRIPT%\n',
                "echo oLink.Save >> %SCRIPT%\n",
                "cscript /nologo %SCRIPT%\n",
                "del %SCRIPT%",
            ]
        )  # write built shortcut script text to temporary batch file

    try:
        result = subprocess.run(bat.name, capture_output=True, text=True)
    except Exception as e:
        raise OSError(f"Couldn't run the shortcut-creation script: {e}") from e
    finally:
        if os.path.exists(bat.name):
            os.remove(bat.name)

    # subprocess.run() has no way to know the VBS script's own internal
    # result - "cscript /nologo" suppresses the interpreter banner but not
    # a script-level error (e.g. WshShortcut.Save failing because the
    # target folder is a OneDrive-synced Desktop that refused the write),
    # and that failure doesn't turn into a nonzero exit code or a raised
    # Python exception either way. The only way to actually know if this
    # worked is to check whether the .lnk file exists afterward.
    if not file.exists():
        detail = result.stdout.strip() or result.stderr.strip() or "no further detail was reported"
        raise OSError(f'Shortcut "{file}" was not created ({detail})')


def toggle_run_at_startup(state: bool) -> None:
    startup_path = Path(os.path.expanduser("~\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Startup"))
    if state:
        make_shortcut("Edgeware++", Process.MAIN, CustomAssets.icon(), startup_path)
    else:
        (startup_path / "Edgeware++.lnk").unlink(missing_ok=True)


def set_schedule(vars) -> None:  # noqa: ANN001
    scheduler = win32com.client.Dispatch("Schedule.Service")
    scheduler.Connect()
    root_folder = scheduler.GetFolder("\\")
    task_def = scheduler.NewTask(0)

    # Create trigger
    # If we're adding "X hours from now", formula is datetime.datetime.now() + datetime.timedelta(minutes=5)
    # if vars.variance_type.get() == "Minutes":
    #     variance = datetime.timedelta(minutes=vars.variance_time.get())
    # elif vars.variance_type.get() == "Hours":
    #     variance = datetime.timedelta(hours=vars.variance_time.get())
    # elif vars.variance_type.get() == "Days":
    #     variance = datetime.timedelta(days=vars.variance_time.get())

    if vars.time_type.get() == "Minutes":
        start_time = datetime.datetime.now() + datetime.timedelta(minutes=vars.schedule_time.get())
    elif vars.time_type.get() == "Hours":
        start_time = datetime.datetime.now() + datetime.timedelta(hours=vars.schedule_time.get())
    elif vars.time_type.get() == "Days":
        start_time = datetime.datetime.now() + datetime.timedelta(days=vars.schedule_time.get())

    task_trigger_time = 1
    trigger = task_def.Triggers.Create(task_trigger_time)
    trigger.StartBoundary = start_time.isoformat()

    # Repetition
    # The repetition interval needs to be in ISO8601 format, so lets make that
    if vars.repeat_schedule.get():
        if vars.repeat_type.get() == "Minutes":
            repetition_time = f"PT{vars.repeat_time.get()}M"
        elif vars.repeat_type.get() == "Hours":
            repetition_time = f"PT{vars.repeat_time.get()}H"
        elif vars.repeat_type.get() == "Days":
            repetition_time = f"P{vars.repeat_time.get()}D"

        trigger.Repetition.Interval = repetition_time
    # Variance
    if vars.variance_time.get() > 0:
        if vars.variance_type.get() == "Minutes":
            variance_time = f"PT{vars.variance_time.get()}M"
        elif vars.variance_type.get() == "Hours":
            variance_time = f"PT{vars.variance_time.get()}H"
        elif vars.variance_type.get() == "Days":
            variance_time = f"P{vars.variance_time.get()}D"

        trigger.RandomDelay = variance_time

    # Create action
    task_action_exec = 0
    action = task_def.Actions.Create(task_action_exec)
    action.ID = "EDGEWARE"
    # A .pyw file isn't itself an executable - pointing Task Scheduler's
    # action.Path directly at it makes Windows fall back to file-association
    # resolution to figure out how to open it, the same mechanism that
    # decides what happens on a double-click. Reported directly: this shows
    # Windows' "How do you want to open this file?" chooser every time the
    # scheduled task actually runs. Launching the real interpreter directly,
    # with the .pyw file passed as an argument, avoids that resolution step
    # entirely - the same approach edgeware.pyw's own stub already uses
    # (subprocess.run([sys.executable, ...])) to launch a script.
    action.Path = sys.executable
    action.Arguments = f'"{PYW[Process.MAIN]}"'

    # Set parameters
    task_def.RegistrationInfo.Description = "Edgeware++"
    task_def.Settings.Enabled = True
    task_def.Settings.StopIfGoingOnBatteries = False

    # Register task
    # If task already exists, it will be updated
    task_create_or_update = 6
    task_logon_none = 0
    root_folder.RegisterTaskDefinition(
        "Edgeware++",  # Task name
        task_def,
        task_create_or_update,
        "",  # No user
        "",  # No password
        task_logon_none,
    )


def delete_schedule() -> None:
    try:
        scheduler = win32com.client.Dispatch("Schedule.Service")
        scheduler.Connect()
        root_folder = scheduler.GetFolder("\\")
        root_folder.DeleteTask("Edgeware++", 0)
    except Exception:
        pass
