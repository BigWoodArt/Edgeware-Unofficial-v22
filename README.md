# Edgeware++ (v22 patch)

**18+ only.** Edgeware++ is a fetish-designed program that spawns popups (images, video,
audio, prompts, and more) over your screen, highly customizable via downloadable "packs."
It can be ended at any time and scheduled for more passive use.

This is a personal patch on top of [Araten & Marigold's Edgeware++](https://github.com/araten10/EdgewarePlusPlus)
(latest official release: v21) - all credit for the original program goes to them. It
fixes several real bugs and rebuilds `config.pyw` into a proper tool with extra features,
including an optional **Do Not Press** mode (see Usage below). Full list of changes is in
the Changelog at the bottom.

**Edgeware++ is not a virus and does not install itself onto your computer.** All it
installs by default is Python and a few libraries (plus a portable 7zip on Windows to
extract the video player). Edgeware *can* modify or delete files on your computer, but
only via settings you explicitly turn on yourself - none of that is on by default.

**This also includes my new Pack Builder, which you can download separately at**
[https://github.com/BigWoodArt/Edgeware-Pack-Builder](https://github.com/BigWoodArt/Edgeware-Pack-Builder)


## Installation

Same as upstream Edgeware++:

1. Download this repo as a ZIP (Code → Download ZIP) and extract it.
2. **Windows:** run `edgeware/EdgewareSetup.bat`. It installs Python and dependencies,
then opens `config.pyw`. Check the top of the installer window for a Python version
warning - Edgeware needs 3.12+, not 3.10.
3. **Linux:** install `python3 python3-pip mpv gcc python3-dev libmpv-dev python3-tk`
yourself first, then run `setup.sh` in the `edgeware` directory. This creates a
virtual environment and `config.sh`/`edgeware.sh` launcher scripts.
4. **macOS:** not supported here - see [this fork](https://github.com/blissfull-ignorance/EdgewarePlusPlus-ReactElectron) instead.

You'll also need a pack to run - see upstream's
[README](https://github.com/araten10/EdgewarePlusPlus#packs) for sample packs and where
to find more.

**Any damage you do to your own computer with Edgeware is your own responsibility.**
Read the "About" tab in the config window and back up your data before touching the
more disruptive settings.


## Usage

Open `config.pyw` to pick a pack and change settings, then either **Save, Exit, and Run**
to launch immediately, or just **Save and Exit** and run `edgeware.pyw` later. Panic
(hotkey or tray icon) stops everything immediately, unless Panic Lockout is on.

`config.pyw` also has: WebP⇄GIF conversion tools, intensity presets, a Corruption
Preview tab, and a **Priority** setting deciding whether your saved settings or a
selected pack's own settings win when they disagree.

**Do Not Press** is an optional button in `config.pyw`'s sidebar. Pressing it opens a
confirmation screen (not a single accidental click) asking for a safeword, a lockout
time, and typing ARM to confirm. Once armed, every time Edgeware starts (including
automatically at Windows login, since arming turns that on):

* It picks a random installed pack, ignoring whatever pack is normally selected.
* It waits a random 5-90 minutes after starting before doing anything - silently, with
no indication it's about to start.
* Panic Lockout is active for the entire wait and the session after: Panic (hotkey or
tray icon) asks for your safeword and does nothing without it, until the lockout time
you set runs out. The panic hotkey itself is never disabled - only whether it responds
immediately depends on the safeword/lockout time, same as using Panic Lockout manually.

This repeats every time Edgeware starts until you press "Disarm" in the sidebar, or edit
`data/config.json` directly.


## Bugs / issues

This is a personal patch, maintained casually. For bugs in upstream Edgeware++ itself,
use [their issues page](https://github.com/araten10/EdgewarePlusPlus/issues). For bugs
specific to this fork's changes, open an issue here.


## Content Removal Policy

If you own art or assets used by this program or its linked demo packs and want them
removed, reach out and we'll work it out.


## License

Edgeware++ (as of April 28, 2025) is licensed under GPLv3 or later. Contributions prior
to that date are licensed under MIT. This fork retains the same license.


## Not Yet Verified

Things that exist in the code but haven't been specifically tested this round -
worth a look before relying on them:

* Fill Drive - copies pack images across your entire drive.
* Do Not Press - full armed session flow never run.
* Danger/pack-permission gate - untested whether limits are enforced.
* Mitosis Mode (duplicate popups) - active, not confirmed working.
* Prompt popups - typing challenges, mistake lockout untested.
* Web popups - opening links on close, untested.
* Moving popups - active, not confirmed working correctly.
* Wallpaper rotation and Corruption Wallpaper/Theme Cycle - untested.
* Discord Rich Presence - never mentioned or tested at all.
* Multi-click closing, Mood Set toggle - both active, unconfirmed.
* Popup auto-close/fade timing - worth re-confirming visually.
* Web Video Takeover - RedGifs/PMVHaven extraction tested, real playback isn't.
* Hypnotube detector is a generic placeholder, not site-specific yet.
* Self-update's real-Windows restart/file-overwrite: logic tested, not that.


## Changelog

Roughly newest to oldest. This is a summary - see
[V22_PATCH_NOTES.md](V22_PATCH_NOTES.md) if you want the full blow-by-blow.
Entries are kept to 20 words or less.

**The biggest changes, regardless of version number:**
* Animated WebP images no longer show as a black square - now played back natively instead of via mpv.
* Real scraper built for Gelbooru-family sites, plus a tool that tests all 18 known sites and shows why any fail.
* `config.pyw` rebuilt from the ground up for clear, full control over pack runs.
* A pack's own settings under Pack Priority were silently wiped out at corruption's first level - fixed.
* New optional full-screen spiral overlay with paired binaural audio, reacting to session intensity with hard opacity/volume caps.

**v22.2.24** - Config.pyw can now actually apply its own updates: download, backup code, apply, restart - not just notify.

**v22.2.23** - New dev tool: paste a link in the Internet tab, test Web Video Takeover directly, close with your Panic key.

**v22.2.22** - Hypnotube detector now matches BambiBrowser's actual code: skips blob URLs, weights Hypnotube's own CDN domain.

**v22.2.21** - Narrowed Hypnotube's detector using real, confirmed page structure from an independent source - still not fully verified.

**v22.2.20** - New: Web Video Takeover plays RedGifs/PMVHaven fullscreen via mpv. Hypnotube extension scaffolded. Config now warns on old Python.

**v22.2.19** - Fixed misleading fade-time description (audio only, not popups). Rewrote changelog to 20 words or less. Added untested-features list.

**v22.2.18** - Tray icon now fully hides with Panic disabled, not just its menu. Fixed a Panic cleanup race that skipped popups.

**v22.2.17** - New setting hides Panic from the tray icon. Fixed Panic Lockout's buried prompt, Scheduler's open-with prompt, and hibernate timing bugs.

**v22.2.16** - Five UI fixes: stuck theme color, swapped Low-key corners, wrong Purity description, trimmed text, new Adopt Pack Settings button.

**v22.2.15** - Scheduler now actually works - config.pyw never registered the Windows Task Scheduler entry, so it silently did nothing before.

**v22.2.14** - Fixed a real freeze - a blocking Tk call could crash and leave the app stuck until Panic was pressed.

**v22.2.13** - Fourth attempt at the video-flash bug, targeting Windows' compositor directly. Best-supported attempt yet, still not visually confirmed.

**v22.2.12** - Third attempt at the video-flash bug - a missing flag let Windows briefly flash a console window on launch.

**v22.2.11** - Second attempt at the video-flash bug, this time targeting mpv's own window instead of Tkinter's.

**v22.2.9** - Image popups now log their filename, corruption level, and screen position, to help debug a missing-images report.

**v22.2.8** - Reverted v22.2.7's video-flash fix - it broke image and video popups entirely. Everything else from that version stays.

**v22.2.7** - Setup script now checks Python version and warns properly. Fixed a video flash. Image resizing now defaults to Bilinear.

**v22.2.6** - Fixed subliminal text and notifications wrongly borrowing captions when empty. Fixed a wrong "denial" description. Added a new Hypnotics tab.

**v22.2.5** - Real bug: the spiral overlay was blocking clicks instead of passing them through. Now fixed.

**v22.2.4** - Fixed "Test Download Sites" misreporting some working sites as failing. Traced (but didn't fix) why Paheal always fails.

**v22.2.3** - Spiral overlay opacity now tracks corruption live instead of staying fixed. Added paired binaural audio. Subliminal text stays on top.

**v22.2.2** - Subliminal text no longer gets buried by later popups. Added a booru site tester and an optional spiral overlay.

**v22.2.1** - Real bug: one failed startup step (a desktop shortcut) could silently kill Panic and every popup. Now isolated and logged.

**v22.2.0** - Original v21 config menu restored as `config_original.pyw`. Fixed its update check pointing at the wrong repo.

**v22.1.0** - Real scraper built for the Gelbooru-engine site family. Other engines stay dimmed as "not rebuilt yet."

**v22.0.11** - Fixed video popups freezing every click while reading video size. Booru downloads expanded from one site to ~18.

**v22.0.8** - Edgeware wouldn't start at all on newer Python, due to a DLL-loading issue - fixed.

**v22.0.7** - Pack Priority's settings were silently reverting moments after startup - every setting a pack overrides, not just one.

**v22.0.6** - Disabled/grayed-out settings weren't actually reading as disabled - text too light, widgets ignoring the theme.

**v22.0.5** - Real fix for settings reverting when switching tabs. Removed a dialog that could hang unattended sessions. Dependent settings now auto-gray.

**v22.0.4** - Fixed Default Priority not being honored at all, due to a string-comparison bug. Removed 5 dead settings.

**v22.0.3** - Pack-selection text no longer overflows and pushes buttons off-screen. Priority dropdown now updates live.

**v22.0.2** - Added Do Not Press and the Priority system (your settings vs. a pack's own). Fixed a launch crash.

**v22.0.1 and earlier** - Fixed WebP lag, a Panic-crashing syntax error, and popups appearing behind windows. Rebuilt config.pyw with conversion tools and presets.
