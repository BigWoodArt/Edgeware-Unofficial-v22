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

from tkinter import Canvas, Toplevel

import os_utils
import utils
from config.settings import Settings
from pack import Pack

TEXT_COLORS = {"White": "white", "Black": "black", "Pink": "deep pink"}
OUTLINE_COLORS = {"White": "white", "Black": "black"}
# The 8 surrounding positions a 1px-offset outline copy gets drawn at.
OUTLINE_OFFSETS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


class SubliminalPopup(Toplevel):
    def __init__(self, settings: Settings, pack: Pack, subliminal: str | None = None) -> None:
        self.subliminal = subliminal or pack.random_subliminal()
        if not self.should_init():
            return
        super().__init__()

        self.attributes("-topmost", True)
        os_utils.set_borderless(self)
        self.attributes("-alpha", settings.subliminal_opacity)
        if os_utils.is_windows():
            self.wm_attributes("-transparentcolor", settings.theme.transparent_bg)

        monitor = utils.random_monitor(settings)
        font = (settings.theme.font, min(monitor.width, monitor.height) // 10)
        text_color = TEXT_COLORS.get(settings.subliminal_text_color, "white")
        outline_color = OUTLINE_COLORS.get(settings.subliminal_outline_color, "black")
        bg = settings.theme.transparent_bg if os_utils.is_windows() else settings.theme.bg

        # Tkinter has no native text outline, so this is the standard trick for
        # faking one on a 2D canvas: draw the same text several times, offset by
        # a pixel in each direction in the outline color, then once more in the
        # actual text color on top.
        canvas = Canvas(self, highlightthickness=0, bg=bg)
        canvas.pack()
        for dx, dy in OUTLINE_OFFSETS:
            canvas.create_text(dx, dy, text=self.subliminal, font=font, fill=outline_color, anchor="nw", width=monitor.width / 1.5)
        text_id = canvas.create_text(0, 0, text=self.subliminal, font=font, fill=text_color, anchor="nw", width=monitor.width / 1.5)

        # Resize the canvas to fit the text (plus a 1px margin for the outline
        # offsets above) and shift everything to sit inside that margin.
        bbox = canvas.bbox(text_id)
        width, height = (bbox[2] - bbox[0]) + 2, (bbox[3] - bbox[1]) + 2
        canvas.configure(width=width, height=height)
        canvas.move("all", 1 - bbox[0], 1 - bbox[1])

        x = monitor.x + (monitor.width - width) // 2
        y = monitor.y + (monitor.height - height) // 2

        self.geometry(f"+{x}+{y}")
        self.after(settings.subliminal_timeout, self.destroy)

    def should_init(self) -> bool:
        return self.subliminal
