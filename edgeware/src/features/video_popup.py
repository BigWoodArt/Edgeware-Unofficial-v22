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

import logging
from pathlib import Path
from threading import Thread
from tkinter import TclError, Tk
from typing import Callable

from config.settings import Settings
from features.popup import Popup
from features.video_player import VideoPlayer
from pack import Pack
from state import State
from videoprops import get_video_properties


class VideoPopup(Popup):
    def __init__(self, root: Tk, settings: Settings, pack: Pack, state: State, media: Path | None = None, on_close: Callable[[], None] | None = None) -> None:
        self.media = media or pack.random_video()
        if not self.should_init(settings, state):
            return
        self._pending_root, self._pending_settings, self._pending_pack, self._pending_state, self._pending_on_close = root, settings, pack, state, on_close
        # get_video_properties() spawns ffprobe and blocks waiting for it -
        # on the main thread, that would freeze the whole program (every
        # popup, every click) for however long that takes, every single
        # time a video is about to appear, and the more video-heavy a pack
        # is, the more often. Probing on a background thread instead, and
        # only creating the actual popup once its final size is already
        # known, avoids both the freeze and a jarring resize-into-place
        # after the window is already visible.
        Thread(target=self._probe, daemon=True).start()

    def _probe(self) -> None:
        try:
            properties = get_video_properties(self.media)
        except Exception as e:
            logging.warning(f"Failed to read video properties for {self.media}: {e}")
            self._pending_state.video_number -= 1  # Undo should_init()'s reservation - this popup never shows
            return
        try:
            self._pending_root.after(0, lambda: self._finish_init(properties))
        except TclError:
            self._pending_state.video_number -= 1  # App is shutting down - same as above

    def _finish_init(self, properties: dict) -> None:
        # Not "self._pending_root" etc. here - Tkinter's own Misc._root is a
        # bound method, and a same-named plain attribute on self would shadow
        # it and break widget creation, hence the "_pending_" staging names.
        super().__init__(self._pending_root, self._pending_settings, self._pending_pack, self._pending_state, self._pending_on_close)

        self.compute_geometry(properties["width"], properties["height"])

        self.player = VideoPlayer(self, self.settings, self.width, self.height)
        self.player.properties["volume"] = self.settings.video_volume
        self.player.properties["glsl-shaders"] = self.try_denial_filter(True)
        self.player.play(self.media)

        self.init_finish()

    def should_init(self, settings: Settings, state: State) -> bool:
        if state.video_number < settings.max_video and self.media:
            state.video_number += 1
            return True
        return False

    def close(self) -> None:
        self.player.close()
        super().close()
        self.state.video_number -= 1
