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

"""Gelbooru-engine-family image search: JSON API first, HTML-scrape fallback
for when the API is unavailable or unusable (e.g. requires auth, or dead
server-side). Covers sites confirmed to run this specific engine with the
same index.php URL scheme - NOT every "-booru"-named site runs this (Paheal,
for one, runs a different engine with a different URL scheme).
"""

import logging
import random
import re
import time
from collections.abc import Iterable, Iterator
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

import requests

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
REQUEST_TIMEOUT = 5
# Searches pick a random page from the first MAX_RANDOM_PAGE pages of results
# instead of always taking page one, so repeated searches for the same tags
# don't keep returning the same newest handful of posts.
MAX_RANDOM_PAGE = 10
# Gelbooru-engine listing pages are offset-based (pid = posts skipped), and
# each page holds this many posts.
HTML_PAGE_SIZE = 42
RATE_LIMIT_SECONDS = 1.0

GELBOORU_FAMILY_DOMAINS = {
    "Gelbooru": "gelbooru.com",
    "Realbooru": "realbooru.com",
    "Hypnohub": "hypnohub.net",
    "Rule34": "rule34.xxx",
    "Safebooru": "safebooru.org",
    "Xbooru": "xbooru.com",
    "Tbib": "tbib.org",
    "Atfbooru": "booru.allthefallen.moe",
    "Behoimi": "behoimi.org",
}

_last_request_time: dict[str, float] = {}


def _rate_limit(domain: str) -> None:
    last = _last_request_time.get(domain, 0.0)
    wait = RATE_LIMIT_SECONDS - (time.time() - last)
    if wait > 0:
        time.sleep(wait)
    _last_request_time[domain] = time.time()


def _get(url: str, domain: str) -> requests.Response:
    _rate_limit(domain)
    return requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)


def _try_json_api(domain: str, tags: str, limit: int, api_key: str, user_id: str, page: int = 0) -> list[dict] | None:
    """Try the dapi JSON endpoint. Returns a list of post dicts (empty if the
    page has none), or None if the API is unavailable or returned something
    unusable - the caller should fall back to HTML scraping in that case,
    not give up."""
    url = f"https://{domain}/index.php?page=dapi&s=post&q=index&json=1&tags={quote(tags, safe='')}&limit={limit}&pid={page}"
    if api_key and user_id:
        url += f"&api_key={api_key}&user_id={user_id}"
    try:
        response = _get(url, domain)
        # Don't trust the HTTP status alone - a 200 with an HTML error page
        # or an XML "API offline" response (observed on RealBooru) inside is
        # exactly the failure mode that needs to fall through to scraping,
        # not be treated as "zero results found".
        data = response.json()
    except Exception as e:
        logging.warning(f"booru scraper: JSON API unusable for {domain} ({e}) - falling back to HTML scrape")
        return None

    if isinstance(data, dict):
        posts = data.get("post", [])
    elif isinstance(data, list):
        posts = data
    else:
        return None
    return posts


_THUMB_BLOCK_RE = re.compile(r'<a[^>]*\bid="p(\d+)"[^>]*>\s*<img([^>]+)>', re.IGNORECASE)
_ATTR_RE = re.compile(r'(\w+)\s*=\s*"([^"]*)"')


def _scrape_listing_html(domain: str, tags: str, page: int = 0) -> list[str]:
    """Fallback for when the JSON API is unavailable: scrape the ordinary
    search-listing page for post IDs. Returns post IDs only - the listing
    page doesn't carry a full-resolution URL or reliable score data, only
    thumbnails (see _resolve_full_image for the next step)."""
    url = f"https://{domain}/index.php?page=post&s=list&tags={quote(tags, safe='')}&pid={page * HTML_PAGE_SIZE}"
    try:
        html = _get(url, domain).text
    except Exception as e:
        logging.warning(f"booru scraper: listing page fetch failed for {domain} ({e})")
        return []

    post_ids = [match.group(1) for match in _THUMB_BLOCK_RE.finditer(html)]
    if not post_ids:
        logging.warning(f"booru scraper: no thumbnail blocks matched on {domain}'s listing page - its markup may have changed")
    return post_ids


_ORIGINAL_LINK_RE = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>\s*Original(?:\s+image)?\s*</a>', re.IGNORECASE)
_OG_IMAGE_RE = re.compile(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', re.IGNORECASE)
_INLINE_IMAGE_RE = re.compile(r'<img[^>]+id="image"[^>]+src="([^"]+)"', re.IGNORECASE)


_DOUBLE_SLASH_RE = re.compile(r"(https?://[^/]+)//+")


def _fix_double_slash(url: str) -> str:
    """Some sites' own markup (confirmed directly on RealBooru's post pages)
    has an href with a doubled leading slash after the domain, which
    urljoin() faithfully preserves rather than normalizes - collapse it so
    the resulting URL actually resolves."""
    return _DOUBLE_SLASH_RE.sub(r"\1/", url)


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
# Videos and other non-image files are skipped, not fatal - at most this many
# candidates are examined before giving up, so a tag that mostly returns
# videos can't turn one search into dozens of requests.
MAX_URL_CANDIDATES = 5


def is_image_url(url: str) -> bool:
    return Path(urlparse(url).path).suffix.lower() in IMAGE_EXTENSIONS


def first_image_url(urls: Iterable[str]) -> str | None:
    """First still-image URL among the first MAX_URL_CANDIDATES of `urls`."""
    for count, url in enumerate(urls, 1):
        if is_image_url(url):
            return url
        if count >= MAX_URL_CANDIDATES:
            break
    return None


def extract_file_url(post: dict) -> str | None:
    """Full-size file URL from a post dict, whichever shape the site's API
    uses: "file_url" (most), "file": {"url"} (e621 family), or
    "representations": {"full"} (Derpibooru/Furbooru)."""
    url = post.get("file_url")
    if not url and isinstance(post.get("file"), dict):
        url = post["file"].get("url")
    if not url and isinstance(post.get("representations"), dict):
        url = post["representations"].get("full")
    return _fix_double_slash(url) if url else None


def image_request_headers(url: str) -> dict[str, str]:
    """Headers for fetching an image file. Some sites (RealBooru confirmed)
    redirect any file request that doesn't come from their own pages to an
    error page, so the Referer is the file's own site."""
    parts = urlparse(url)
    return {"User-Agent": USER_AGENT, "Referer": f"{parts.scheme}://{parts.netloc}/"}


def verify_image_url(url: str, info: dict | None = None) -> tuple[bool, str]:
    """Actually request `url` the way a real download would, and report
    whether it serves an image. Returns (ok, detail-if-not). If `info` is
    given, it's filled with what the server answered (status, content type,
    final URL, redirect count) for logging."""
    try:
        response = requests.get(url, headers=image_request_headers(url), stream=True, timeout=REQUEST_TIMEOUT)
    except Exception as e:
        return False, f"request failed: {e}"
    try:
        if info is not None:
            info.update(
                status=response.status_code,
                content_type=response.headers.get("Content-Type", ""),
                final_url=response.url,
                redirects=len(response.history),
            )
        if response.status_code >= 400:
            return False, f"HTTP {response.status_code}"
        content_type = response.headers.get("Content-Type", "").lower()
        if not content_type.startswith("image/"):
            return False, f"served {content_type or 'an unknown type'} instead of an image (ended at {response.url})"
        return True, ""
    finally:
        response.close()


def _resolve_full_image(domain: str, post_id: str) -> str | None:
    """Visit a post's own page for its real full-resolution image URL -
    never guessed from the thumbnail filename, which is unreliable. Tries
    the "Original image" link first, then an og:image meta tag, then the
    inline #image tag as a last resort (that one can be a downscaled sample
    rather than the original on some sites, e.g. Hypnohub)."""
    url = f"https://{domain}/index.php?page=post&s=view&id={post_id}"
    try:
        html = _get(url, domain).text
    except Exception as e:
        logging.warning(f"booru scraper: post page fetch failed for {domain}#{post_id} ({e})")
        return None

    for match in _ORIGINAL_LINK_RE.finditer(html):
        href = match.group(1)
        if href.startswith("index.php"):
            # Gelbooru trap: a post can have an actual "original" (= "not a
            # repost") tag, rendered as an ordinary sidebar tag-link with
            # anchor text "original" - e.g. index.php?page=post&s=list&
            # tags=original. That's never a real media URL, only ever
            # internal site navigation, and it usually appears earlier in
            # the page than the real download link.
            continue
        return _fix_double_slash(urljoin(url, href))

    match = _OG_IMAGE_RE.search(html)
    if match:
        return _fix_double_slash(match.group(1))

    match = _INLINE_IMAGE_RE.search(html)
    if match:
        return _fix_double_slash(urljoin(url, match.group(1)))

    logging.warning(f"booru scraper: no image URL found on {domain}#{post_id}'s post page - its markup may have changed")
    return None


def search_gelbooru_family(site_name: str, tags: str, min_score: int, limit: int = 20, api_key: str = "", user_id: str = "") -> Iterator[str]:
    """Search a Gelbooru-engine-family site for images matching tags,
    yielding image URLs from a random page of results (see MAX_RANDOM_PAGE)
    one at a time as they're found/resolved, so a
    caller can start downloading the first result immediately rather than
    waiting for a whole batch to resolve first. Score filtering only
    applies on the JSON API path - the HTML-scrape fallback has no
    reliable score signal available at all, so every result found that way
    is yielded regardless of score. This is deliberately not hidden: it's
    a best-effort filter, not a guarantee, same as it's always been.
    """
    domain = GELBOORU_FAMILY_DOMAINS.get(site_name)
    if not domain:
        return

    page = random.randrange(MAX_RANDOM_PAGE)
    posts = _try_json_api(domain, tags, limit, api_key, user_id, page)
    if posts == [] and page > 0:
        # Random page was past the end of this tag's results - use the first.
        page = 0
        posts = _try_json_api(domain, tags, limit, api_key, user_id, page)
    if posts:
        random.shuffle(posts)
        for post in posts:
            score = post.get("score")
            if isinstance(score, (int, float)) and score < min_score:
                continue
            file_url = extract_file_url(post)
            if file_url:
                yield file_url
        return

    post_ids = _scrape_listing_html(domain, tags, page)
    if not post_ids and page > 0:
        post_ids = _scrape_listing_html(domain, tags, 0)
    random.shuffle(post_ids)
    for post_id in post_ids:
        image_url = _resolve_full_image(domain, post_id)
        if image_url:
            yield image_url
