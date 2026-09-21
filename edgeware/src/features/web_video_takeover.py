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

"""Web Video Takeover: for a small, explicit list of supported sites, plays
the linked video fullscreen via mpv instead of just opening the page in a
browser tab. Two different mechanisms depending on the site:

- RedGifs and PMVHaven embed a direct/HLS video URL in the page's own static
  HTML (an Open Graph tag or a JSON-LD VideoObject block) - a plain HTTP
  fetch and a bit of parsing is all that's needed, no JavaScript execution.
- Hypnotube's video only exists after a JS-driven age-gate resolves, so it
  needs a real browser to have already loaded the page. A tiny local HTTP
  server (loopback-only) accepts a detected video URL from a companion
  browser extension running in the person's own, already-verified browser
  session, and hands it to the same takeover window either way.
"""

import http.server
import json
import logging
import re
import threading
from tkinter import TclError, Tk, Toplevel

import requests
from config.settings import Settings
from features.video_player import VideoPlayer
from state import State
from utils import primary_monitor

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
REQUEST_TIMEOUT = 10

LOCAL_SERVER_PORT = 58217  # Arbitrary, unregistered - only listens on 127.0.0.1


def _extract_redgifs(html: str) -> str | None:
    # The direct .mp4 URL sits in a plain Open Graph tag - no JS needed.
    match = re.search(r'<meta property="og:video" content="([^"]+)"', html)
    return match.group(1) if match else None


def _extract_pmvhaven(html: str) -> str | None:
    # Prefer the JSON-LD VideoObject block's contentUrl when it's the real
    # media URL (some of this site's own JSON-LD blocks reuse contentUrl for
    # the page's own canonical link instead - only trust one ending in the
    # HLS manifest extension mpv actually needs).
    for match in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        content_url = data.get("contentUrl", "")
        if data.get("@type") == "VideoObject" and content_url.endswith(".m3u8"):
            return content_url
    return None


# (url pattern, extractor function) - checked in order, first match wins.
# Deliberately a short, explicit allowlist rather than "any site": each
# entry here has been individually confirmed to actually expose a playable
# video URL this way, the same standard the booru site list holds itself
# to. A site that isn't a match at all falls through to the normal
# open-in-browser behavior, same as before this feature existed.
SUPPORTED_SITES: list[tuple[re.Pattern, callable]] = [
    (re.compile(r"redgifs\.com/watch/"), _extract_redgifs),
    (re.compile(r"pmvhaven\.com/video/"), _extract_pmvhaven),
]


def is_supported_site(url: str) -> bool:
    return any(pattern.search(url) for pattern, _ in SUPPORTED_SITES)


def fetch_video_url(url: str) -> str | None:
    """Fetch the page and extract a playable video URL, or None if the site
    isn't supported or extraction failed for any reason. Never raises -
    every caller treats a failure here as "fall back to opening the page
    normally", not an error worth surfacing."""
    extractor = next((fn for pattern, fn in SUPPORTED_SITES if pattern.search(url)), None)
    if extractor is None:
        return None
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.warning(f"Web video takeover: couldn't fetch {url}: {e}")
        return None
    try:
        return extractor(response.text)
    except Exception as e:
        logging.warning(f"Web video takeover: couldn't extract a video URL from {url}: {e}")
        return None


class WebVideoTakeover(Toplevel):
    """A single fullscreen, topmost, borderless mpv playback window. Same
    contract as the spiral overlay and binaural audio for Panic's cleanup:
    a close() that's safe to call more than once (the max-length timer and
    Panic can each trigger it independently)."""

    def __init__(self, root: Tk, settings: Settings, video_url: str) -> None:
        super().__init__(root, bg="black")
        self.closed = False

        monitor = primary_monitor()
        width = monitor.width if monitor else self.winfo_screenwidth()
        height = monitor.height if monitor else self.winfo_screenheight()
        x = monitor.x if monitor else 0
        y = monitor.y if monitor else 0

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.geometry(f"{width}x{height}+{x}+{y}")

        self.player = VideoPlayer(self, settings, width, height)
        # Standard two-copy blur-fill technique: one copy scaled to fill the
        # whole screen and heavily blurred as a background, the real video
        # scaled to fit within the screen preserving its own aspect ratio
        # and overlaid centered on top. Needed because these sites are
        # frequently vertical/portrait video - without this, only the
        # correctly-proportioned foreground would show, framed by plain
        # black bars either side instead of filling the screen.
        self.player.properties["vf"] = (
            f"split[o][c];"
            f"[c]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},gblur=sigma=30[bg];"
            f"[o]scale={width}:{height}:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2"
        )
        self.player.play(video_url)

        self.close_timer_id = None
        if settings.web_video_max_length > 0:
            self.close_timer_id = self.after(settings.web_video_max_length * 60 * 1000, self.close)

    def close(self) -> None:
        if self.closed:
            return  # Idempotent - the max-length timer and Panic can each call this independently
        self.closed = True
        if self.close_timer_id:
            try:
                self.after_cancel(self.close_timer_id)
            except TclError:
                pass
        try:
            self.player.close()
        except Exception as e:
            logging.warning(f"Web video takeover: error closing player: {e}")
        try:
            self.destroy()
        except TclError:
            pass  # Already gone


def open_web_video_takeover(root: Tk, settings: Settings, state: State, url: str) -> bool:
    """Returns True if this URL was handled as a takeover (caller should not
    also open it in a browser tab), False if it's not a supported site."""
    video_url = fetch_video_url(url)
    if not video_url:
        return False
    state.web_video_takeover = WebVideoTakeover(root, settings, video_url)
    return True


class _TakeoverRequestHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass  # Suppress the default per-request stderr logging

    def do_POST(self) -> None:
        if self.path != "/takeover":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length))
            video_url = payload["videoUrl"]
        except (json.JSONDecodeError, KeyError, ValueError):
            self.send_response(400)
            self.end_headers()
            return
        self.send_response(204)
        self.end_headers()
        # Extension-detected videos (Hypnotube, currently) skip
        # fetch_video_url() entirely - the extension already ran inside a
        # real, fully-loaded browser tab and did the detection itself; all
        # this server does is receive the result and hand it to the same
        # takeover window every other supported site uses.
        self.server.root.after(
            0, lambda: self.server.state.__setattr__("web_video_takeover", WebVideoTakeover(self.server.root, self.server.settings, video_url))
        )


def start_takeover_server(root: Tk, settings: Settings, state: State) -> http.server.HTTPServer | None:
    """Starts the loopback-only HTTP server the browser extension posts
    detected videos to. Best-effort: if the port's unavailable, the
    extension-based sites just won't work this session - never worth
    failing startup over."""
    try:
        server = http.server.HTTPServer(("127.0.0.1", LOCAL_SERVER_PORT), _TakeoverRequestHandler)
    except OSError as e:
        logging.warning(f"Web video takeover: local server couldn't start: {e}")
        return None
    server.root = root
    server.settings = settings
    server.state = state
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
