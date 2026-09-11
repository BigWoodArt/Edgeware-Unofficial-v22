# Edgeware++ (v22 patch)

**18+ only.** Edgeware++ is a fetish-designed program that spawns popups (images, video,
audio, prompts, and more) over your screen, highly customizable via downloadable "packs."
It can be ended at any time and scheduled for more passive use.

This is a personal patch on top of [Araten \& Marigold's Edgeware++](https://github.com/araten10/EdgewarePlusPlus)
(latest official release: v21) - all credit for the original program goes to them. It
fixes several bugs and rebuilds `config.pyw` into a proper tool with extra features,
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



## Changelog

Roughly newest to oldest. This is a summary - see
[V22\_PATCH\_NOTES.md](V22_PATCH_NOTES.md) if you want the full blow-by-blow.

**The biggest changes, regardless of version number:**

* Animated WebP images no longer show up as a black square - ffmpeg/mpv genuinely cannot
decode them at all, so they're now played back natively instead of being handed to mpv.
* Edgeware would fail to start at all on Python 3.8+ due to a DLL-loading issue in how
it locates libmpv - fixed.
* `config.pyw` rebuilt from a 4-line stub into an actual tool (see Usage above).
* A pack's own settings (under Pack Priority) were being silently wiped out the instant
corruption's first level applied - fixed.
* Popups appearing behind other windows, especially right after launching - fixed.

**v22.0.8** - Edgeware wouldn't start at all on newer Python, due to the DLL-loading
issue above.

**v22.0.7** - Pack Priority's settings were silently reverting moments after startup -
not just one setting, every setting a pack overrides.

**v22.0.6** - Disabled/grayed-out settings weren't actually reading as disabled (text
too light, dropdowns and text boxes ignoring the theme).

**v22.0.5** - The real fix for settings appearing to revert when switching tabs
(previously only fixed at save time, not while actively editing). Removed a blocking
confirmation dialog that could hang Edgeware forever during an unattended Do Not Press
session. Intensity presets rewritten with clean integer values throughout. Settings that
only matter when a "parent" setting is on now gray out automatically.

**v22.0.4** - Found and fixed the actual Priority bug: Default Priority wasn't being
honored at all, due to a string-comparison mismatch. Removed 5 settings confirmed to
have no effect on Edgeware's runtime. README replaced.

**v22.0.3** - Pack-selection summary text no longer overflows and pushes buttons
off-screen. Priority dropdown updates live instead of needing a save first.

**v22.0.2** - Added Do Not Press. Introduced the Priority system (your settings vs. a
pack's own). Fixed a crash-on-launch bug in config.pyw.

**v22.0.1 and earlier** - Fixed the animated WebP black square and related lag. Fixed a
fatal Python syntax error in `panic.py` that could crash Panic outright. Fixed popups
appearing behind other windows. Panic now auto-captures your wallpaper automatically,
and no longer goes black if the captured file gets overwritten later. Fixed "Run when
Windows starts" being cosmetic-only. `config.pyw` rebuilt with WebP⇄GIF conversion
tools, intensity presets, and pack override visibility.

