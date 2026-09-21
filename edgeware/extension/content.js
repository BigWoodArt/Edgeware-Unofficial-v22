// Edgeware++ Web Video Takeover - content script
//
// Video-finding logic here matches BambiBrowser's own Hypnotube detector
// (github.com/sissy3city/BambiBrowser, MIT licensed - reused directly per
// that license, adapted into this file's structure rather than copied
// as-is, since this file also owns the MutationObserver/reporting side
// BambiBrowser's own detector object doesn't). Two things that earlier
// guesses here got wrong or missed entirely: blob: URLs need to be
// skipped (temporary MSE/DRM buffer references, not something mpv could
// actually fetch), and scoring should weight a candidate's real screen
// area but double it when the URL is served from Hypnotube's own CDN
// domain - so an ad rendering larger doesn't win over the real player
// unless it's more than 2x the size.

(function () {
  "use strict";

  function findMainVideo() {
    const videos = document.querySelectorAll("video");
    let best = null;
    let bestScore = 0;

    for (const v of videos) {
      const src = v.currentSrc || v.src;
      if (!src || src.startsWith("blob:")) continue;

      const isHypnotubeCdn = src.includes("media.hypnotube.com");
      const rect = v.getBoundingClientRect();
      const area = rect.width * rect.height;
      const score = isHypnotubeCdn ? area * 2 : area;

      if (score > bestScore) {
        bestScore = score;
        best = v;
      }
    }

    return best;
  }

  function reportVideo(videoUrl) {
    chrome.runtime.sendMessage({ type: "edgeware-video-detected", videoUrl: videoUrl, pageUrl: window.location.href });
  }

  let reported = false;
  const observer = new MutationObserver(() => {
    if (reported) return;
    const video = findMainVideo();
    if (video) {
      reported = true;
      reportVideo(video.currentSrc || video.src);
      observer.disconnect();
    }
  });

  observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["src"] });

  // Also check immediately, in case the video is already present and
  // playable by the time this script runs (document_idle, so often true).
  const initial = findMainVideo();
  if (initial) {
    reported = true;
    reportVideo(initial.currentSrc || initial.src);
    observer.disconnect();
  }
})();
