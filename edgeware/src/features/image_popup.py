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

import asyncio
import logging
from pathlib import Path
from random import randint
from tkinter import Label, TclError, Tk
from typing import Callable

import booru
import requests
from config.settings import Settings
from features.popup import Popup
from features.video_player import VideoPlayer
from pack import Pack
from PIL import Image, ImageTk
from roll import roll
from state import State


class ImagePopup(Popup):
    def __init__(self, root: Tk, settings: Settings, pack: Pack, state: State, media: Path | None = None, on_close: Callable[[], None] | None = None) -> None:
        self.media = media or pack.random_image()
        self.hypno = roll(settings.hypno_chance)
        if not self.should_init():
            return
        super().__init__(root, settings, pack, state, on_close)

        # TODO: Better booru integration
        if self.settings.booru_download and roll(50):
            try:
                gel = booru.Gelbooru()
                result = booru.resolve(asyncio.run(gel.search_image(query=self.settings.booru_tags, limit=1)))
                data = requests.get(result[0], stream=True)
                image = Image.open(data.raw)
            except Exception:
                logging.error(f'No results for tags "{self.settings.booru_tags}" on Gelbooru')
                image = Image.open(self.media)
        else:
            image = Image.open(self.media)
        self.compute_geometry(image.width, image.height)

        # Static          -> image
        # Static,   hypno -> image overlay, mpv
        # Animated        -> mpv, except WebP (see play_frames)
        # Animated, hypno -> mpv, ?

        if getattr(image, "n_frames", 0) > 1:
            if image.format == "WEBP":
                # mpv plays animated media through ffmpeg's own decoders, and
                # ffmpeg's native WebP decoder does not implement the ANIM/ANMF
                # animation chunks (a long-standing, well-documented ffmpeg gap,
                # unrelated to hardware decoding) - it just logs "image data not
                # found" and mpv renders nothing, which is the black square.
                # Pillow reads animated WebP fine via libwebp, so play it back
                # natively instead of going through mpv. Every other animated
                # format (gif, apng, ...) is unaffected and keeps using mpv,
                # since ffmpeg decodes those correctly and mpv is lighter on
                # CPU for anything bigger than a sticker-sized loop.
                self.play_frames(image)
            else:
                self.player = VideoPlayer(self, self.settings, self.width, self.height)
                self.player.properties["glsl-shaders"] = self.try_denial_filter(True)
                self.player.play(str(self.media))
        else:
            resized = image.resize((self.width, self.height), Image.LANCZOS).convert("RGBA")
            filter = self.try_denial_filter(False)
            if filter == "resizeblur":
                shrink_d = randint(5, 15)
                resized = resized.resize((int(self.width / shrink_d), int(self.height / shrink_d)), Image.BILINEAR)
                resized = resized.resize((self.width, self.height), Image.NEAREST)
                filter = ""
            final = resized.filter(filter) if filter else resized

            if self.hypno:
                self.player = VideoPlayer(self, self.settings, self.width, self.height)
                self.player.properties["video-scale-x"] = max(self.width / self.height, 1)
                self.player.properties["video-scale-y"] = max(self.height / self.width, 1)
                # NOTE: same ffmpeg limitation as above applies here in theory if
                # a pack's hypno asset happens to be an animated WebP rather than
                # a GIF, since this still goes through mpv unconditionally. Not
                # fixed here since the reported bug was about img-folder popups;
                # flagging for anyone who hits it with hypno/subliminal assets.
                final.putalpha(int((1 - self.settings.hypno_opacity) * 255))
                self.player.play(self.pack.random_hypno(), final)
            else:
                label = Label(self, width=self.width, height=self.height)
                label.pack()
                self.photo_image = ImageTk.PhotoImage(final)
                label.config(image=self.photo_image)

        self.init_finish()

    def play_frames(self, image: Image.Image) -> None:
        """Play back a Pillow-decoded animated image (currently only used for
        WebP) natively in Tkinter, instead of handing it to mpv.

        Frames are decoded and resized one at a time, right before each is
        shown, rather than all up front: a large animated WebP (big pixel
        dimensions and/or many frames) decoded and Lanczos-resized entirely
        before the popup even appears is a noticeable freeze, and Lanczos
        specifically is the slowest resample filter Pillow has. Bilinear is
        used here instead - the quality difference is not really visible on a
        playing animation the way it would be on a still image - and only the
        currently-displayed frame is kept in memory instead of the whole
        animation."""
        filter = self.try_denial_filter(False)
        shrink_d = randint(5, 15) if filter == "resizeblur" else None
        n_frames = image.n_frames

        label = Label(self, width=self.width, height=self.height)
        label.pack()

        def render_frame(index: int) -> ImageTk.PhotoImage:
            image.seek(index)
            frame = image.convert("RGBA").resize((self.width, self.height), Image.BILINEAR)
            if shrink_d:
                frame = frame.resize((max(1, self.width // shrink_d), max(1, self.height // shrink_d)), Image.BILINEAR)
                frame = frame.resize((self.width, self.height), Image.NEAREST)
            elif filter:
                frame = frame.filter(filter)
            return ImageTk.PhotoImage(frame)

        def advance(index: int) -> None:
            try:
                photo = render_frame(index)
                label.config(image=photo)
                # Keep a reference alive - Tkinter drops a PhotoImage with no
                # remaining Python references even while still displayed. Only
                # the current frame needs to be kept, not the whole animation.
                self.current_frame_image = photo
            except TclError:
                return  # Popup was closed; stop the playback loop
            duration = max(image.info.get("duration", 100), 20)  # Guard against 0ms/missing durations
            self.after(duration, lambda: advance((index + 1) % n_frames))

        advance(0)

    def should_init(self) -> bool:
        return self.media

    def close(self) -> None:
        if hasattr(self, "player"):
            self.player.close()
        super().close()
