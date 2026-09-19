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
from random import choice, randint
from tkinter import Label, TclError, Tk
from typing import Callable

import booru
import requests
from config.settings import Settings
from features import booru_scraper
from features.popup import Popup
from features.video_player import VideoPlayer
from pack import Pack
from PIL import Image, ImageTk
from roll import roll
from state import State

# Every site the "booru" package supports, minus Lolibooru - not included,
# not configurable, not up for discussion via a pack's own config either
# (see download_booru_image below, which re-checks against this same list
# regardless of what a pack or saved config claims booru_sites contains).
ALLOWED_BOORU_SITES = {
    "Atfbooru",
    "Behoimi",
    "Danbooru",
    "Derpibooru",
    "E621",
    "E926",
    "Furbooru",
    "Gelbooru",
    "Hypnohub",
    "Konachan",
    "Konachan_Net",
    "Paheal",
    "Realbooru",
    "Rule34",
    "Safebooru",
    "Tbib",
    "Xbooru",
    "Yandere",
}

# Maps config/items.py's "imageResizeFilter" choice to the actual PIL filter.
# Bilinear is the default: on a typical downscale (a large source image into
# a much smaller popup) it is visually very close to Lanczos while costing a
# few times less CPU - Lanczos's real advantage shows up upscaling or with
# fine line art/text near native size, not shrinking a photo into a popup.
# Bicubic sits in between. Exposed as a choice rather than only ever
# Bilinear since a person is free to judge the trade-off differently on
# their own hardware/packs.
RESIZE_FILTERS = {
    "Bilinear": Image.BILINEAR,
    "Bicubic": Image.BICUBIC,
    "Lanczos": Image.LANCZOS,
}


def download_booru_image(settings: Settings) -> str | None:
    """Search a random site from settings.booru_sites (comma-separated) for
    an image matching settings.booru_tags, filtered by settings.booru_min_score.
    Returns an image URL, or None if nothing usable was found. Never raises -
    any failure (bad site name, network error, no results, an unfamiliar
    response shape) just means "nothing found", left for the caller to fall
    back to the pack's own local image the same way a tag search finding
    nothing already does.

    Gelbooru-engine-family sites (see booru_scraper.GELBOORU_FAMILY_DOMAINS)
    go through booru_scraper instead of the third-party "booru" package,
    since that package only speaks each site's JSON API, and as of writing
    two of these sites' JSON APIs are broken in ways no client can fix
    (Gelbooru requires credentials it was never sent; RealBooru's API is
    reported dead server-side). Every other site stays on the "booru"
    package - not reported broken, not rewritten.

    "Score" isn't guaranteed to be a consistent field across every site's API,
    so this is deliberately lenient: a result missing score info is kept
    rather than discarded, only ones with a score below the threshold are
    dropped. This is best-effort filtering, not a hard guarantee for every
    site.
    """
    requested = {name.strip() for name in settings.booru_sites.split(",") if name.strip()}
    valid_sites = list(requested & ALLOWED_BOORU_SITES)
    if not valid_sites:
        return None

    site = choice(valid_sites)

    if site in booru_scraper.GELBOORU_FAMILY_DOMAINS:
        try:
            for url in booru_scraper.search_gelbooru_family(
                site, settings.booru_tags, settings.booru_min_score, api_key=settings.booru_api_key, user_id=settings.booru_user_id
            ):
                return url  # Already shuffled inside search_gelbooru_family() - first is as good as random
        except Exception as e:
            logging.warning(f'booru_scraper failed for "{site}": {e}')
        return None

    site_obj = getattr(booru, site)()
    results = booru.resolve(asyncio.run(site_obj.search(query=settings.booru_tags, limit=20)))
    if not results:
        return None

    for post in results:
        score = post.get("score")
        if isinstance(score, (int, float)) and score < settings.booru_min_score:
            continue
        try:
            return post["file_url"]
        except KeyError:
            try:
                return post["file"]["url"]
            except (KeyError, TypeError):
                continue
    return None


class ImagePopup(Popup):
    def __init__(self, root: Tk, settings: Settings, pack: Pack, state: State, media: Path | None = None, on_close: Callable[[], None] | None = None) -> None:
        self.media = media or pack.random_image()
        self.hypno = roll(settings.hypno_chance)
        if not self.should_init():
            return
        super().__init__(root, settings, pack, state, on_close)

        if self.settings.booru_download and roll(50):
            try:
                url = download_booru_image(self.settings)
                if not url:
                    raise ValueError("No qualifying results")
                data = requests.get(url, stream=True)
                image = Image.open(data.raw)
            except Exception:
                logging.error(f'No results for tags "{self.settings.booru_tags}" on {self.settings.booru_sites}')
                image = Image.open(self.media)
        else:
            image = Image.open(self.media)
        self.compute_geometry(image.width, image.height)
        logging.info(f'Image popup: "{self.media.name}" (corruption level {self.state.corruption_level}) at ({self.x}, {self.y}), monitor {self.monitor.name}')

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
            resized = image.resize((self.width, self.height), RESIZE_FILTERS.get(self.settings.image_resize_filter, Image.BILINEAR)).convert("RGBA")
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
