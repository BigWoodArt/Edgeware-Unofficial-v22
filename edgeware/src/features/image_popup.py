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
from collections.abc import Iterator
from pathlib import Path
from random import choice, randint
from threading import Thread
from tkinter import Label, TclError, Tk
from typing import Callable

import booru
import requests
from config.settings import Settings
from features import booru_scraper
from features.booru_scraper import MAX_RANDOM_PAGE, REQUEST_TIMEOUT
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
            # Already shuffled inside search_gelbooru_family() - first is as good as random
            return booru_scraper.first_image_url(
                booru_scraper.search_gelbooru_family(
                    site, settings.booru_tags, settings.booru_min_score, api_key=settings.booru_api_key, user_id=settings.booru_user_id
                )
            )
        except Exception as e:
            logging.warning(f'booru_scraper failed for "{site}": {e}')
        return None

    site_obj = getattr(booru, site)()
    # Random page for variety; if it's past the end of this tag's results
    # (or otherwise fails), fall back to the first page.
    page = randint(1, MAX_RANDOM_PAGE)
    results = None
    for attempt in (page, 1) if page > 1 else (1,):
        try:
            results = booru.resolve(asyncio.run(asyncio.wait_for(site_obj.search(query=settings.booru_tags, limit=20, page=attempt), timeout=REQUEST_TIMEOUT)))
        except Exception as e:
            logging.warning(f'"booru" package search failed for "{site}" (page {attempt}): {e}')
            results = None
        if results:
            break
    if not results:
        return None

    return booru_scraper.first_image_url(_candidate_urls(results, settings.booru_min_score))


def _candidate_urls(results: list[dict], min_score: int) -> Iterator[str]:
    for post in results:
        score = post.get("score")
        if isinstance(score, (int, float)) and score < min_score:
            continue
        url = booru_scraper.extract_file_url(post)
        if url:
            yield url


def _fetch_booru_image(settings: Settings) -> Image.Image | None:
    """The actual network+decode work behind the booru_download setting -
    pulled out of ImagePopup.__init__ so it can run on a worker thread
    instead of Tkinter's single main thread. Returns None on any failure
    (bad site, network error, no results), same "never raises, caller falls
    back to local media" contract as download_booru_image itself. Fully
    decodes the image (.load()) before returning, rather than handing back
    a lazy PIL Image still backed by the HTTP response stream, so nothing
    about the network connection needs to stay alive past this function -
    the caller can safely use the result on a different thread, later."""
    try:
        url = download_booru_image(settings)
        if not url:
            raise ValueError("No qualifying results")
        data = requests.get(url, headers=booru_scraper.image_request_headers(url), stream=True, timeout=REQUEST_TIMEOUT)
        data.raise_for_status()
        image = Image.open(data.raw)
        image.load()
        return image
    except Exception:
        logging.error(f'No results for tags "{settings.booru_tags}" on {settings.booru_sites}')
        return None


class ImagePopup(Popup):
    def __init__(self, root: Tk, settings: Settings, pack: Pack, state: State, media: Path | None = None, on_close: Callable[[], None] | None = None) -> None:
        self.media = media or pack.random_image()
        self.hypno = roll(settings.hypno_chance)
        if not self.should_init():
            return

        if settings.booru_download and roll(50):
            # The actual network fetch (and everything the rest of __init__
            # needs the fetched image for) used to happen right here, inline,
            # on Tkinter's single main thread - meaning a slow or stalled
            # booru site froze the entire UI until it resolved, including
            # already-registered clicks on other, unrelated popups (reported
            # directly as "Close doesn't work"). Popup creation itself still
            # can't happen off the main thread (Tkinter widgets aren't
            # thread-safe to create), so only the network I/O + image decode
            # - the actually slow part - moves to a worker thread; the popup
            # is then finished on the main thread exactly as before, via
            # root.after(), once that thread has an image ready one way or
            # another. No caller depends on ImagePopup(...) returning a
            # fully-initialized popup synchronously (every call site either
            # discards the return value or reacts to state.popup_number
            # ticking up later, not to this call returning) - see the
            # v22.3.2 patch notes entry this replaces for why a plain
            # timeout wasn't a full fix.
            def fetch_then_finish() -> None:
                image = _fetch_booru_image(settings) or Image.open(self.media)
                try:
                    root.after(0, lambda: self._finish_init(root, settings, pack, state, on_close, image))
                except (TclError, RuntimeError):
                    pass  # root was torn down (e.g. Panic) while this was in flight

            Thread(target=fetch_then_finish, daemon=True).start()
        else:
            self._finish_init(root, settings, pack, state, on_close, Image.open(self.media))

    def _finish_init(self, root: Tk, settings: Settings, pack: Pack, state: State, on_close: Callable[[], None] | None, image: Image.Image) -> None:
        super().__init__(root, settings, pack, state, on_close)
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
                # NOTE: this same ffmpeg limitation would apply here too if a
                # pack's hypno asset were an animated WebP rather than a GIF -
                # Pack.random_hypno() filters those out at pack-load time
                # instead (see _is_unplayable_hypno_asset in pack/__init__.py),
                # since neither this popup nor spiral_overlay.py's full-screen
                # overlay has a native-Pillow fallback the way this file's own
                # img-folder path does above.
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
