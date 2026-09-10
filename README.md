# Edgeware++ (v22 patch)

**18+ only.** Edgeware++ is a fetish-designed program that spawns popups (images, video,
audio, prompts, and more) over your screen, highly customizable via downloadable "packs."
It can be ended at any time and scheduled for more passive use.

This is a personal patch on top of [Araten & Marigold's Edgeware++](https://github.com/araten10/EdgewarePlusPlus)
(latest official release: v21) - all credit for the original program goes to them. This
fork doesn't change what Edgeware fundamentally does; it fixes a few bugs and rebuilds
`config.pyw` with some extra tooling. See below for the specifics.

**Edgeware++ is not a virus and does not install itself onto your computer.** All it
installs by default is Python and a few libraries (plus a portable 7zip on Windows to
extract the video player). Edgeware *can* modify or delete files on your computer, but
only via settings you explicitly turn on yourself - none of that is on by default.

**This also includes my new Pack Builder, which you can download separately at**
[https://github.com/BigWoodArt/Edgeware-Pack-Builder](https://github.com/BigWoodArt/Edgeware-Pack-Builder)


## What's different in this fork

* Fixed animated WebP images showing up as a black square (ffmpeg/mpv can't decode
animated WebP at all - it's now played back natively instead of handed to mpv), and a
related freeze/lag on large animated WebP files.
* Fixed a Python syntax error in `panic.py` that could crash Panic outright.
* Fixed popups sometimes appearing behind other windows, especially right after
launching from config.pyw.
* Panic now auto-captures your current wallpaper the first time Edgeware runs, so Panic
never falls back to a generic placeholder wallpaper if you forgot to set one, and no
longer goes black if that captured wallpaper's original file path gets overwritten later.
* Fixed "Run when Windows starts" being cosmetic-only in config.pyw (it saved a setting
but never actually created the Startup shortcut).
* Rebuilt `config.pyw`: cleaner layout, WebP ⇄ GIF conversion tools, intensity presets,
a Corruption Preview tab, and visibility into which settings the selected pack overrides
(with a "Priority" toggle to decide who wins, you or the pack).
* Subliminal caption text can use White/Black/Pink text with a White/Black outline.
* Added an optional **Do Not Press** feature - see below.


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


## Do Not Press

config.pyw has a "DO NOT PRESS" button in the sidebar. Pressing it opens a confirmation
screen (not a single accidental click) asking for a safeword, a lockout time, and typing
ARM to confirm. Once armed, every time Edgeware starts (including automatically at
Windows login, since arming turns that on):

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
