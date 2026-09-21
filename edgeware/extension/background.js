// Edgeware++ Web Video Takeover - background service worker
//
// content.js can't reliably POST to the local server itself: Manifest V3
// content scripts inherit the page's own Content-Security-Policy, which on
// some sites would block a cross-origin fetch to 127.0.0.1 outright. A
// background service worker isn't subject to the page's CSP, so it does
// the actual network call instead - content.js just detects, this
// delivers.

const LOCAL_SERVER_URL = "http://127.0.0.1:58217/takeover";

chrome.runtime.onMessage.addListener((message) => {
  if (message.type !== "edgeware-video-detected") return;

  fetch(LOCAL_SERVER_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ videoUrl: message.videoUrl, pageUrl: message.pageUrl }),
  }).catch(() => {
    // Edgeware isn't running, or the takeover setting is off (server never
    // started) - not an error worth surfacing, the person just doesn't get
    // the takeover this time and the site behaves normally otherwise.
  });
});
