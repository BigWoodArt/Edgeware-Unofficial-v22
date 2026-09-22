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

import io
import logging
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from threading import Thread
from tkinter import Label, Misc

import mpv
import os_utils
from config.settings import Settings
from os_utils import close_mpv
from paths import Process
from PIL import Image


class VideoPlayer(Label):
    def __init__(self, master: Misc, settings: Settings, width: int, height: int) -> None:
        super().__init__(master, width=width, height=height, bg="black")
        self.pack()

        self.settings = settings
        # Optional, opt-in hook: if set before play() is called, it's
        # invoked (on the Tk main thread, safe to touch widgets from)
        # the moment mpv is genuinely decoding and rendering frames, not
        # just once the URL has resolved. Every existing caller leaves
        # this None, which keeps behavior (and the subprocess command
        # line built in play()) identical to before this existed.
        self.on_playback_start: Callable[[], None] | None = None
        self._playback_start_signal_path: Path | None = None
        # Optional, opt-in hook: if set before play() is called, it's
        # invoked (on the Tk main thread) with (loglevel, message) for
        # each mpv log line at "warn" level or above - real diagnostic
        # output instead of guessing at property syntax from outside.
        # Every existing caller leaves this None, which keeps behavior
        # (including whether the subprocess branch below captures
        # stderr at all) identical to before this existed.
        self.on_log_message: Callable[[str, str], None] | None = None
        self.properties = {
            "loop": "inf",
            "hwdec": "auto" if self.settings.video_hardware_acceleration else "no",
            "input-cursor-passthrough": "yes",  # Required for buttonless closing
            # A candidate fix for a reported brief flash of a window with a
            # native title bar before a video popup properly appears -
            # consistent large size regardless of varying position pointed
            # at mpv's own window (created during its GPU/render context
            # init, before it's fully embedded into the given wid), not the
            # Tkinter popup window itself (which was already ruled out - see
            # the reverted v22.2.7 attempt at this same report). This is
            # mpv's own documented "no window border" option, independent of
            # anything Tkinter/Windows-window-manager related, so it can't
            # interact with that reverted code at all. Unverified here -
            # GPU-level window creation timing inside a separate subprocess
            # isn't something this sandbox can observe.
            "border": "no",
        }

        if os_utils.is_linux():
            # Required on Wayland for embedding the player
            temp = mpv.MPV()
            for context in ["x11", "x11egl", "x11vk"]:
                try:
                    temp["gpu-context"] = context  # Check if context is supported
                    self.properties["gpu-context"] = context
                    break
                except TypeError:
                    logging.warning(f"mpv GPU context {context} is not supported")

    def play(self, media: Path, overlay: Image.Image | None = None) -> None:
        if not self.settings.mpv_subprocess:
            # update_idletasks(), not wait_visibility() - the latter enters
            # a nested Tcl event loop (tkwait visibility) that can hang the
            # whole app indefinitely if the visibility event never fires
            # for any reason, not just throw on an already-destroyed
            # window. Already identified and fixed the same way in
            # features/spiral_overlay.py and features/popup.py - this was
            # the one remaining caller still using the dangerous version,
            # reported directly as a real hang (Config's title bar fading
            # the way Windows does for an unresponsive app, nothing ever
            # appearing, needing to be closed manually).
            self.update_idletasks()

            mpv_kwargs = {}
            if self.on_log_message:
                # Real mpv diagnostic output, filtered to warn-and-above so
                # it doesn't flood with routine chatter - replaces guessing
                # at property syntax from outside with what mpv itself
                # actually reports. Wrapped in the handler itself, not
                # here, so a problem in this specific python-mpv call can
                # never be allowed to interrupt playback - the same
                # standard already applied to the playback-start callback
                # below.
                def _handle_log(loglevel: str, component: str, message: str) -> None:
                    if loglevel in ("warn", "error", "fatal") and self.on_log_message:
                        self.after(0, lambda: self.on_log_message(loglevel, f"[{component}] {message}"))

                mpv_kwargs["log_handler"] = _handle_log

            self.mpv = mpv.MPV(wid=self.winfo_id(), **mpv_kwargs)
            for key, value in self.properties.items():
                self.mpv[key] = value

            if self.on_playback_start:
                # mpv's own event marking that it's genuinely decoding and
                # rendering again, not just that the URL resolved -
                # registered before play() so it's armed for the very
                # first firing. Wrapped defensively: if this specific
                # python-mpv call ever doesn't behave as expected, playback
                # itself must never be put at risk over a "reveal early"
                # nicety - the caller's own delay-based fallback still
                # covers that case either way.
                try:

                    @self.mpv.event_callback("playback-restart")
                    def _on_restart(_event: object, _callback: Callable[[], None] = self.on_playback_start) -> None:
                        self.after(0, _callback)

                except Exception as e:
                    logging.warning(f"VideoPlayer: couldn't register playback-start callback: {e}")

            if overlay:
                self.mpv.create_image_overlay().update(overlay)

            self.mpv.play(str(media))
        else:
            args = [
                sys.executable,
                Process.MPV,
                str(self.winfo_id()),
                str(self.properties),
                media,
                "1" if overlay else "0",
            ]
            if self.on_playback_start:
                # No direct channel back from a separate process - mpv_
                # subprocess.py touches this file itself the moment its
                # own playback-restart event fires (same signal as the
                # in-process branch above, just relayed through a file
                # since there's no Python object to attach an event
                # callback to from here), and this side polls for it.
                # Passed as one extra, optional argument at the end - if
                # on_playback_start is never set (every other caller of
                # VideoPlayer), this list is exactly what it always was.
                signal_path = Path(tempfile.gettempdir()) / f"edgeware_playback_ready_{id(self)}.signal"
                signal_path.unlink(missing_ok=True)
                self._playback_start_signal_path = signal_path
                args.append(str(signal_path))
                self._poll_playback_start_signal()

            self.process = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                # Only captured (rather than left to inherit the parent's,
                # exactly as before this existed) when a caller actually
                # asked for mpv's log output via on_log_message - every
                # other caller of VideoPlayer never sets this up.
                stdout=subprocess.PIPE if self.on_log_message else None,
                # Without this, spawning a new Python process on Windows can
                # briefly flash a plain console window - default black
                # background, default title bar - before anything suppresses
                # it, independent of anything mpv or Tkinter itself is doing.
                # Reported directly: a large, roughly consistent-sized window
                # with Windows' default title bar, appearing briefly and in a
                # varying position, specifically before video popups (the
                # only popup type that spawns this subprocess at all). Two
                # earlier attempts at this report (mpv's own render-context
                # window, and Tkinter's own borderless-timing) were both
                # ruled out - this targets the subprocess launch itself
                # instead, a well-established fix for exactly this class of
                # flash. CREATE_NO_WINDOW only exists on Windows.
                creationflags=subprocess.CREATE_NO_WINDOW if os_utils.is_windows() else 0,
                text=True if self.on_log_message else False,
            )

            if self.on_log_message:
                # mpv_subprocess.py always prints its own warn-and-above
                # log lines (harmless if nobody's capturing stdout, which
                # is the case for every other caller) - this thread reads
                # them back out and relays them the same way the
                # in-process branch above does.
                def read_mpv_log() -> None:
                    for line in self.process.stdout:
                        parts = line.rstrip("\n").split("|", 3)
                        if len(parts) == 4 and parts[0] == "MPVLOG" and self.on_log_message:
                            _marker, loglevel, component, message = parts
                            self.after(0, lambda lv=loglevel, c=component, m=message: self.on_log_message(lv, f"[{c}] {m}"))

                Thread(target=read_mpv_log, daemon=True).start()

            if overlay:

                def send_overlay() -> None:
                    bytes_io = io.BytesIO()
                    overlay.save(bytes_io, format="PNG")
                    self.process.communicate(input=bytes_io.getvalue())

                Thread(target=send_overlay).start()

    def _poll_playback_start_signal(self) -> None:
        """Only used in subprocess mode with on_playback_start set (see
        play()). Polls for the signal file mpv_subprocess.py touches the
        moment its own mpv instance actually starts decoding and
        rendering. Self-cancels once found, once the callback's been
        cleared (close() already ran), or once the widget itself is
        gone."""
        if not self.on_playback_start or not self._playback_start_signal_path:
            return
        try:
            if self._playback_start_signal_path.exists():
                self._playback_start_signal_path.unlink(missing_ok=True)
                callback = self.on_playback_start
                self.on_playback_start = None  # One-shot
                callback()
                return
            self.after(150, self._poll_playback_start_signal)
        except RuntimeError:
            return  # Widget already destroyed

    def close(self) -> None:
        self.on_playback_start = None  # Stop any pending signal-file poll from firing after close
        if self._playback_start_signal_path:
            self._playback_start_signal_path.unlink(missing_ok=True)
        if not self.settings.mpv_subprocess:
            close_mpv(self.mpv)
        else:
            self.process.kill()
