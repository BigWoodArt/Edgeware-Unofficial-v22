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
browser tab. All three currently-supported sites embed a direct/HLS video
URL in the page's own static HTML - a plain HTTP fetch and a bit of
parsing is all that's needed, no JavaScript execution required for any of
them (confirmed directly for Hypnotube specifically, despite its own
client-side age-gate - that gate doesn't block the server from returning
the real video page to a plain, cookieless request).

Hypnotube also has a fallback path: a companion browser extension plus a
tiny local HTTP server (loopback-only), for the case a future page change
brings back a real requirement for a live browser session. The direct
fetch above is tried first and is expected to cover the common case.
"""

import http.server
import json
import logging
import re
import threading
from collections.abc import Callable
from tkinter import TclError, Tk, Toplevel
from urllib.parse import urlparse

import requests
from config.settings import Settings
from features.video_player import VideoPlayer
from state import State
from utils import primary_monitor

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
REQUEST_TIMEOUT = 10
RELIFT_INTERVAL_MS = 250  # Matches panic.py's ask_panic_password() - see WebVideoTakeover's docstring
DEFAULT_REVEAL_DELAY_MS = 10000  # Used only when the file size can't be determined at all (e.g. a HEAD request itself fails)
MIN_REVEAL_DELAY_MS = 2000
MAX_REVEAL_DELAY_MS = 20000
# Deliberately rough, not a precise calculation (that would need the
# video's actual bitrate, which needs a reliable duration figure this
# isn't available everywhere) - but directly matches what was actually
# reported: larger files generally mean higher resolution/bitrate, which
# generally means slower to buffer enough to start playing.
ASSUMED_BUFFERING_BYTES_PER_SECOND = 2 * 1024 * 1024  # ~2 MB/s - conservative for a typical home connection

LOCAL_SERVER_PORT = 58217  # Arbitrary, unregistered - only listens on 127.0.0.1


def referer_for(page_url: str) -> str:
    """The Referer a real browser would send for a request made from this
    page - i.e. the page's own origin. Several video CDNs (confirmed
    directly against PMVHaven's) reject a request with no Referer at all as
    hotlinking, which is exactly what mpv sends by default - this is what
    was silently causing a black screen rather than a fetch error."""
    parsed = urlparse(page_url)
    return f"{parsed.scheme}://{parsed.netloc}/"


def _extract_redgifs(html: str) -> str | None:
    # The direct .mp4 URL sits in a plain Open Graph tag - no JS needed.
    match = re.search(r'<meta property="og:video" content="([^"]+)"', html)
    return match.group(1) if match else None


def _extract_pmvhaven(html: str) -> str | None:
    # Confirmed directly against a real, current page: neither of this
    # page's two JSON-LD VideoObject blocks carries a usable .m3u8
    # contentUrl anymore - both just reuse it for the page's own
    # canonical link instead, which is why the original JSON-LD-based
    # version of this extractor was silently returning nothing on every
    # real page tested here, despite working on an earlier version of
    # this exact page months ago. The real video data now loads
    # client-side from the page's own __NUXT_DATA__ payload - not worth
    # parsing generically (Nuxt's own flat, index-referenced
    # serialization), but the HLS master playlist URL still appears in
    # there as one complete, literal JSON string, escaped forward
    # slashes and all - a direct regex match on that, decoded through
    # json.loads() to undo the \u002F escaping, gets it cleanly without
    # resolving any indices.
    match = re.search(r'"(https:\\u002F\\u002F[^"]*?master\.m3u8)"', html)
    if not match:
        return None
    try:
        return json.loads(f'"{match.group(1)}"')
    except json.JSONDecodeError:
        return None


def _extract_hypnotube(html: str) -> str | None:
    # The direct, token-bearing .mp4 URL sits right in a <source> tag
    # inside the page's own player markup - confirmed directly against a
    # real video page's source, and confirmed separately that a plain,
    # cookieless fetch of the page reaches this same content: the
    # client-side age-gate doesn't block the server from returning it.
    match = re.search(r'id="plyr_player"[^>]*>\s*<source src="([^"]+)"', html)
    return match.group(1) if match else None


# (url pattern, extractor function) - checked in order, first match wins.
# Deliberately a short, explicit allowlist rather than "any site": each
# entry here has been individually confirmed to actually expose a playable
# video URL this way, the same standard the booru site list holds itself
# to. A site that isn't a match at all falls through to the normal
# open-in-browser behavior, same as before this feature existed.
SUPPORTED_SITES: list[tuple[re.Pattern, callable]] = [
    (re.compile(r"redgifs\.com/watch/"), _extract_redgifs),
    (re.compile(r"pmvhaven\.com/videos?/"), _extract_pmvhaven),
    (re.compile(r"hypnotube\.com/video/"), _extract_hypnotube),
]


def is_supported_site(url: str) -> bool:
    return any(pattern.search(url) for pattern, _ in SUPPORTED_SITES)


def _estimate_file_size_bytes(html: str, video_url: str) -> int | None:
    """Best-effort file size in bytes, used only to scale how long the
    takeover window waits before revealing itself - never required, never
    treated as an error if it can't be determined."""
    # Some sites show a human-readable file size directly on the page
    # (confirmed on PMVHaven) - cheaper and more reliable than a network
    # round trip when available, and works even for HLS (.m3u8), which has
    # no single file a HEAD request could measure.
    match = re.search(r"File Size:</span>\s*<span[^>]*>([\d.]+)\s*(KB|MB|GB)</span>", html)
    if match:
        value, unit = float(match.group(1)), match.group(2)
        multiplier = {"KB": 1024, "MB": 1024**2, "GB": 1024**3}[unit]
        return int(value * multiplier)
    if video_url.endswith(".m3u8"):
        return None  # No single file size for a streaming manifest
    try:
        head = requests.head(video_url, headers={"User-Agent": USER_AGENT}, timeout=5, allow_redirects=True)
        content_length = head.headers.get("Content-Length")
        return int(content_length) if content_length else None
    except (requests.RequestException, ValueError):
        return None


def _estimate_reveal_delay_ms(file_size_bytes: int | None) -> int:
    """How long to keep the takeover window tucked in its tiny corner
    before revealing full size, scaled to the video's size when known.
    Deliberately rough (see ASSUMED_BUFFERING_BYTES_PER_SECOND's own
    comment) - clamped so a huge file doesn't wait forever and a tiny one
    doesn't get revealed before anything has actually started."""
    if not file_size_bytes:
        return DEFAULT_REVEAL_DELAY_MS
    delay_ms = int((file_size_bytes / ASSUMED_BUFFERING_BYTES_PER_SECOND) * 1000)
    return max(MIN_REVEAL_DELAY_MS, min(MAX_REVEAL_DELAY_MS, delay_ms))


def fetch_video_url(url: str) -> tuple[str | None, str | None, int]:
    """Fetch the page and extract a playable video URL. Returns
    (video_url, detail, reveal_delay_ms): video_url is None on any
    failure, with detail describing specifically what went wrong (timeout,
    HTTP status, no match found, etc.) rather than collapsing every
    failure mode into one generic message - a failure report should be
    actionable without another round of guessing. reveal_delay_ms is a
    rough, size-based estimate of how long playback startup will likely
    take (see _estimate_reveal_delay_ms), always populated even on
    failure so a caller can use it as a sensible default. Never raises -
    every caller treats a failure here as "fall back to opening the page
    normally", not an error worth crashing over."""
    extractor = next((fn for pattern, fn in SUPPORTED_SITES if pattern.search(url)), None)
    if extractor is None:
        return None, "not a recognized/supported site", DEFAULT_REVEAL_DELAY_MS
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.Timeout:
        detail = f"the request timed out after {REQUEST_TIMEOUT}s"
        logging.warning(f"Web video takeover: {detail} fetching {url}")
        return None, detail, DEFAULT_REVEAL_DELAY_MS
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else "?"
        detail = f"the site returned HTTP {status}"
        logging.warning(f"Web video takeover: {detail} fetching {url}")
        return None, detail, DEFAULT_REVEAL_DELAY_MS
    except requests.RequestException as e:
        detail = f"network error: {e}"
        logging.warning(f"Web video takeover: {detail} fetching {url}")
        return None, detail, DEFAULT_REVEAL_DELAY_MS
    try:
        video_url = extractor(response.text)
    except Exception as e:
        detail = f"error parsing the page: {e}"
        logging.warning(f"Web video takeover: {detail} for {url}")
        return None, detail, DEFAULT_REVEAL_DELAY_MS
    if not video_url:
        detail = f"fetched the page (HTTP {response.status_code}, {len(response.text)} bytes) but found no matching video data in it"
        return None, detail, DEFAULT_REVEAL_DELAY_MS
    reveal_delay_ms = _estimate_reveal_delay_ms(_estimate_file_size_bytes(response.text, video_url))
    return video_url, None, reveal_delay_ms


class WebVideoTakeover(Toplevel):
    """A single fullscreen, topmost, borderless mpv playback window. Same
    contract as the spiral overlay and binaural audio for Panic's cleanup:
    a close() that's safe to call more than once (the max-length timer and
    Panic can each trigger it independently). The real Panic key is a
    global OS-level hook (pynput), not a Tkinter binding, so it fires
    regardless of which window has focus - but this window still
    periodically reclaims its own focus (matching panic.py's own
    ask_panic_password() pattern) as defense-in-depth, since the embedded
    mpv video surface can otherwise hold onto focus indefinitely."""

    def __init__(
        self,
        root: Tk,
        settings: Settings,
        video_url: str,
        referer: str | None = None,
        reveal_delay_ms: int = DEFAULT_REVEAL_DELAY_MS,
        on_log_message: Callable[[str, str], None] | None = None,
    ) -> None:
        super().__init__(root, bg="black")
        self.closed = False

        monitor = primary_monitor()
        width = monitor.width if monitor else self.winfo_screenwidth()
        height = monitor.height if monitor else self.winfo_screenheight()
        x = monitor.x if monitor else 0
        y = monitor.y if monitor else 0

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        # Reported directly: a real black screen was visible for the whole
        # ~10s a slower network+HLS startup can take before mpv actually
        # has a frame to show. Same shape of problem VideoPopup already
        # solves for local files (a visible flash while loading) - reused
        # here at a longer, network-appropriate delay: tuck into a 2x2
        # corner first (an imperceptible dot, not a blank fullscreen
        # rectangle), create the player and start it at the REAL target
        # size regardless, then reveal the real geometry only once
        # startup has typically finished.
        corner_x = monitor.x + monitor.width - 2 if monitor else self.winfo_screenwidth() - 2
        corner_y = monitor.y + monitor.height - 2 if monitor else self.winfo_screenheight() - 2
        self.geometry(f"2x2+{corner_x}+{corner_y}")

        self.player = VideoPlayer(self, settings, width, height)
        # Forces software decoding for this window specifically,
        # regardless of the person's general hardware-acceleration
        # setting. Confirmed directly by a real mpv error, finally seen
        # thanks to the diagnostics added last version: "Impossible to
        # convert between the formats supported by the filter
        # 'Parsed_split_0' and the filter 'auto_scale_0'" - the classic
        # signature of hardware-decoded frames (a different, GPU-specific
        # pixel format) hitting a software-only filter chain. The blur-
        # fill filter graph below needs regular, software-decoded frames
        # to work on at all; other popups are unaffected; this only
        # overrides hwdec for this one window's own properties.
        self.player.properties["hwdec"] = "no"
        # Reported directly: the same video kept repeating instead of the
        # system moving on to a new one. VideoPlayer sets loop: inf by
        # default for every caller, which is correct for a normal
        # background-video popup but not for a video found and played
        # once here - overridden for this window specifically, the same
        # way hwdec is just above. Paired with on_playback_end below,
        # which closes this window itself once the (now non-looping)
        # video actually finishes, so a fresh roll can play something new
        # rather than leaving this one sitting on its last frame forever.
        self.player.properties["loop"] = "no"
        self.player.on_playback_end = self.close

        def _log_and_forward(level: str, message: str) -> None:
            # Real mpv diagnostic output - always logged (so it lands in
            # a real log file for the production engine, which already
            # calls init_logging()), and also relayed live to whichever
            # caller asked for it (the dev test tool, to show directly
            # rather than requiring a log file at all).
            logging.warning(f"mpv: {message}")
            if on_log_message:
                on_log_message(level, message)

        self.player.on_log_message = _log_and_forward

        if referer:
            # Several video CDNs reject a request with no Referer as
            # hotlinking - mpv sends none by default. See referer_for()'s
            # own docstring for how this was confirmed.
            self.player.properties["http-header-fields"] = [f"Referer: {referer}", f"User-Agent: {USER_AGENT}"]
        # Standard two-copy blur-fill technique: one copy scaled to fill the
        # whole screen and heavily blurred as a background, the real video
        # scaled to fit within the screen preserving its own aspect ratio
        # and overlaid centered on top. Needed because these sites are
        # frequently vertical/portrait video - without this, only the
        # correctly-proportioned foreground would show, framed by plain
        # black bars either side instead of filling the screen.
        #
        # This is the one thing genuinely unique to this window - nowhere
        # else in the codebase sets a "vf" filter chain like this, so
        # there was no working precedent to check the syntax against, and
        # three guesses at its exact syntax in a row have each been wrong
        # in a new way: wrapped in lavfi=[...] but as a bare string, video
        # played with plain black bars (no blur, filter silently not
        # applying); wrapped as a one-element list instead (reasoning by
        # analogy with http-header-fields, confirmed needing a list) broke
        # playback entirely - no video, no audio - meaning that guess was
        # wrong too, not just insufficient. Reverted to the bare-string
        # form below, the last version that at least played something,
        # while real mpv log output (see on_mpv_log below) replaces
        # further guessing.
        self.player.properties["vf"] = (
            "lavfi=["
            f"split[o][c];"
            f"[c]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},gblur=sigma=30[bg];"
            f"[o]scale={width}:{height}:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2"
            "]"
        )
        # keepaspect stays at mpv's own default (not overridden either
        # way) - the last version's "no" override was solving a problem
        # that, per the above, wasn't actually what was wrong.
        # Real readiness signal, tried first: reveals the instant mpv is
        # genuinely decoding and rendering (see VideoPlayer's own
        # on_playback_start for exactly what that means and how it's
        # detected in both mpv modes) rather than waiting out a guess.
        # reveal_delay_ms (the size-based estimate) stays wired up as a
        # safety net regardless - whichever of the two fires first wins,
        # so a video still reveals reasonably even if this specific
        # signal never arrives for some reason.
        self._reveal_geometry = (width, height, x, y)
        self._reveal_timer_id: str | None = None
        self._revealed = False
        self.player.on_playback_start = self._reveal_now
        self.player.play(video_url)

        self.close_timer_id = None
        if settings.web_video_max_length > 0:
            self.close_timer_id = self.after(settings.web_video_max_length * 60 * 1000, self.close)

        self._reveal_timer_id = self.after(reveal_delay_ms, self._reveal_now)
        self._relift()

    def _reveal_now(self) -> None:
        if self._reveal_timer_id:
            try:
                self.after_cancel(self._reveal_timer_id)
            except TclError:
                pass
            self._reveal_timer_id = None
        self._reveal(*self._reveal_geometry)

    def _reveal(self, width: int, height: int, x: int, y: int) -> None:
        if self.closed:
            return  # Closed (e.g. via Panic) during the wait - nothing to reveal
        self._revealed = True  # Stops _relift() below from rescheduling itself any further
        try:
            self.geometry(f"{width}x{height}+{x}+{y}")
        except TclError:
            pass  # Already destroyed

    def _relift(self) -> None:
        try:
            if self.closed or self._revealed:
                # Reported directly: a popup would appear over the video
                # briefly, then get covered again within a couple hundred
                # milliseconds - exactly this loop's own interval. The
                # previous version stopped re-toggling -topmost here
                # specifically to let popups stay on top, but kept calling
                # focus_force() every tick on the theory that forcing focus
                # and raising a window's stacking position were separate
                # concerns - on Windows specifically, they're not: forcing
                # focus onto a window typically brings it to the foreground
                # as a coupled operation, which was still stealing the top
                # spot back from a popup that had just appeared above it.
                # Only still useful during the brief tiny-corner phase
                # before reveal, when nothing else should be competing for
                # the foreground anyway and mpv's own embedding is most
                # likely to have just stolen focus - stops entirely once
                # revealed, rather than continuing to fight with popups for
                # the rest of a video's whole playback.
                return
            self.focus_force()
        except TclError:
            return  # Already destroyed
        self.after(RELIFT_INTERVAL_MS, self._relift)

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
    """Returns True if this URL was handled as a takeover, or if one was
    already playing and this roll was skipped rather than starting a
    second, overlapping video - either way the caller shouldn't also open
    it in a browser tab. False only when the URL isn't a supported site
    at all, in which case the caller falls back to its normal
    browser-opening behavior exactly as before this feature existed -
    unrelated to whether a video happens to be playing right now."""
    if not is_supported_site(url):
        return False
    if state.web_video_takeover is not None and not state.web_video_takeover.closed:
        return True  # Already one playing - skip this roll rather than overlapping it
    video_url, _detail, reveal_delay_ms = fetch_video_url(url)
    if not video_url:
        return False
    state.web_video_takeover = WebVideoTakeover(root, settings, video_url, referer=referer_for(url), reveal_delay_ms=reveal_delay_ms)
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
        # Extension-detected videos (Hypnotube's fallback path, currently
        # not the primary path - see the module docstring) skip
        # fetch_video_url() entirely, so there's no page HTML here to look
        # for a displayed file size in - falls straight to the HEAD-request
        # estimate (or the flat default if even that fails). Referer comes
        # from the extension's own reported pageUrl - falls back to the
        # video URL's own origin if that's somehow missing.
        referer = referer_for(payload.get("pageUrl") or video_url)
        reveal_delay_ms = _estimate_reveal_delay_ms(_estimate_file_size_bytes("", video_url))

        def start_takeover() -> None:
            state = self.server.state
            if state.web_video_takeover is not None and not state.web_video_takeover.closed:
                return  # Already one playing - skip rather than overlapping it, matching open_web_video_takeover()
            state.web_video_takeover = WebVideoTakeover(self.server.root, self.server.settings, video_url, referer=referer, reveal_delay_ms=reveal_delay_ms)

        self.server.root.after(0, start_takeover)


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
