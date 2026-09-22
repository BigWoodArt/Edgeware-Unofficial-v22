# Copyright (C) 2025 Araten & Marigold
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

import ast
import io
import sys
from pathlib import Path

import mpv
from PIL import Image

argv = sys.argv[1:]
wid, properties_str, media, overlay = argv[:4]
signal_path = argv[4] if len(argv) > 4 else None
properties = ast.literal_eval(properties_str)


def _log_handler(loglevel: str, component: str, message: str) -> None:
    # Always active - cheap and harmless if nobody's listening. The
    # parent only actually captures this (via stdout=subprocess.PIPE)
    # when a caller opts in via VideoPlayer's on_log_message hook;
    # otherwise this output goes wherever stdout normally would, exactly
    # as before this existed. Filtered to warn-and-above so this doesn't
    # flood with mpv's own routine chatter.
    if loglevel in ("warn", "error", "fatal"):
        print(f"MPVLOG|{loglevel}|{component}|{message}", flush=True)


player = mpv.MPV(wid=wid, log_handler=_log_handler)
for key, value in properties.items():
    player[key] = value

if int(overlay):
    bytes = sys.stdin.buffer.read()
    image = Image.open(io.BytesIO(bytes))
    player.create_image_overlay().update(image)

if signal_path:
    # Touches a file the parent process polls for, the moment mpv is
    # genuinely decoding and rendering again - not just that the URL
    # resolved. Only present when the caller (VideoPlayer.play(), via its
    # opt-in on_playback_start hook) actually asked for it; every other
    # caller's command line is unaffected. Wrapped defensively - a
    # missing "reveal early" signal must never be allowed to interrupt
    # actual playback.
    try:

        @player.event_callback("playback-restart")
        def _on_restart(_event: object, _path: str = signal_path) -> None:
            Path(_path).touch()

    except Exception:
        pass

player.play(media)
player.wait_for_playback()
