# Edgeware++ v22 (minimal patch over v21)

## Files changed
- `edgeware/src/panic.py`
- `edgeware/src/features/image_popup.py`
- `edgeware/src/main_edgeware.py`
- `edgeware/config.pyw` (replaces ChatGPT's version - see notes below)

## 1. Fixed a fatal SyntaxError in `panic.py`
`except OSError, AssertionError:` is Python 2 syntax, invalid in Python 3. This file
is imported at the top of `main_edgeware.py` and every popup type, so this crashed
on import. Fixed to `except (OSError, AssertionError):`.

## 2. Fixed animated WebP rendering as a black square
mpv plays animated media through ffmpeg, and ffmpeg's native WebP decoder does not
implement the `ANIM`/`ANMF` animation chunks that hold an animated WebP's actual
frames (confirmed directly: ffmpeg 6.1.1 logs "skipping unsupported chunk: ANIM/ANMF"
then "image data not found"). mpv renders nothing - that's the black square. Pillow
decodes animated WebP correctly (via libwebp, not ffmpeg), so `image_popup.py` now
plays animated WebP back natively frame-by-frame in Tkinter instead of routing it to
mpv. GIF and other animated formats are untouched and still use mpv.

Known remaining gap: hypno/subliminal overlay assets (`pack.random_hypno()`, files
under a pack's `hypno` or `subliminals` folder) still go through mpv unconditionally
and would hit the same black square if one happens to be an animated WebP. Not fixed
in image_popup.py itself - instead, `config.pyw`'s GIF-to-WebP tool refuses to touch
files in those folders, so it can't be used to accidentally create one.

## 3. Fixed WebP playback lag with large images
The animated-WebP player added above was decoding and Lanczos-resizing *every*
frame up front before the popup could even appear - a real freeze on a big or
long animated WebP. Frames are now decoded and resized one at a time, right
before each is shown, using bilinear resize instead of Lanczos (much cheaper,
and the quality difference isn't really visible on a playing animation the way
it would be on a still image). Only the currently-displayed frame is kept in
memory instead of the whole animation.

## 4. Panic wallpaper auto-capture
Edgeware's config window has always had a manual "Auto Import" button for
setting your current wallpaper as the panic wallpaper - if you never click it
(or "Set Panic Wallpaper"), Panic falls back to a generic bundled image that
looks nothing like your desktop, which is exactly what Panic exists to avoid
(the existing tooltip in `wallpaper.py` already warns about this).
`main_edgeware.py` now calls `ensure_panic_wallpaper()` (new, in `panic.py`) at
startup, before anything touches the wallpaper: if no panic wallpaper has ever
been set, it silently captures whatever wallpaper is currently on screen and
uses that. Costs nothing if you've already set one manually. Covers every
launch path (config.pyw, edgeware.pyw, scheduled starts), not just one.

## 5. config.pyw changes
Rewrote in place rather than as a diff, since ChatGPT's version doesn't have
line-for-line stable structure across edits. What changed from the version
you shared:

- **Fixed a real transparency bug in the WebP-to-GIF converter**: it flattened
  alpha onto a black background before quantizing colors, then never actually
  wrote a `transparency` index to the saved GIF (a palette slot was reserved
  for it in the shared-palette code path, per the code comment, but nothing
  ever assigned it) - so any transparent region silently became solid black in
  the output. Fixed: fully-transparent pixels are now mapped to a real GIF
  transparent index. Partial alpha still can't survive (GIF only supports
  all-or-nothing transparency - that part is a real format limitation, not a
  bug), but full transparency now round-trips correctly.
- **Added the GIF-to-WebP button you asked for**, converting and deleting
  the originals the same way the existing tool does, skipping hypno/subliminals
  folders for the reason in item 2 above.
- Extracted the two tools' near-identical progress-dialog code into one shared
  method instead of duplicating it a second time.
- Updated the "WebP compatibility" card text, which described the pre-v22
  black-square behavior and was no longer accurate.
- Added a version stamp: `VERSION = "22.0.1"` at the top, shown in the window
  title/subtitle, and written into `config.json` as `_configVersion` on save.

**Flagging, not changing (your call):** the "Fix Edgeware theme background"
button rewrites `src/features/popup.py`'s source code at runtime via exact
string matching. It's guarded (checks the file matches expected content first,
keeps a backup), but a config tool silently patching the main program's source
based on brittle text matching is a fragile pattern in general - a future
change to `popup.py` (like the ones in this patch) only has to shift a few
characters to make the match silently fail, or, worse, partially succeed
somewhere it wasn't tested. If this is a fix you want, I'd suggest making it a
permanent change to `popup.py` directly instead (which is a five-minute change
I'm glad to make) rather than a runtime patcher shipped to end users. Left it
as-is for now since removing/changing it wasn't asked for.

Also cosmetic, not touched: `App.add_setting`/`App.render` are monkey-patched
from module-level code after the class body, rather than being written into
the class directly. Works fine, just harder to follow than it needs to be -
worth folding in whenever config.pyw gets touched again for something bigger.

## To install
Drop these four files over your v21 install at the matching paths, or extract
the full patch zip fresh. Same as before - no reinstall required for the
`edgeware/src/` changes; `config.pyw` fully replaces the copy in `edgeware/`.

## 6. EdgewareSetup.bat no longer overwrites your files on every run
Found while explaining why the new config.pyw didn't show up after running
the installer: `EdgewareSetup.bat` unconditionally regenerated `config.pyw`,
`edgeware.pyw`, and `panic.pyw` on every run, always overwriting them with the
plain 4-line stub that launches Edgeware's stock config window - discarding
any customized `config.pyw` (like this one) every single time the installer
runs. `setup.sh` (Linux) already guarded this correctly with `if [ ! -f
"$script.sh" ]`; the `.bat` just never got the same treatment. Fixed to match:
it now only creates a `.pyw` launcher if one doesn't already exist.

**Action needed on your end**: this only stops future runs from clobbering
your file. It doesn't retroactively restore anything, so you still need to
manually copy `edgeware/config.pyw` from this patch into your install folder,
overwriting whatever's there now.

## 7. config.pyw rebased onto ChatGPT's newer "spacing and labelling" pass
The version you shared this time was built from an earlier base and didn't
carry forward any of the fixes above (transparency bug, GIF-to-WebP button,
version stamp, updated card text) - re-applied all of them on top of it.
Everything genuinely new in this pass was kept: pack-aware smart defaults
(`PRETTY_DEFAULTS`/`apply_pack_chance_overrides`), grouped section headers,
the styled ttk widgets, and the now-functional panic wallpaper preview
buttons.

**Found and fixed one real regression in the process:** this pass had
dropped the "Edgeware appearance" (`themeType`) row from the Start section
entirely - all the code behind it (`edge_theme_changed`, the combo box
handler, the save logic) was still there and wired up, just the actual
settings row referencing it was gone, so there was no longer any way to
change Edgeware's actual popup theme from this UI. Restored it as the first
entry in Start, where it was before.

## 8. Popups appearing behind other windows after "Save, Exit, and Run"
Real bug, not config.pyw's fault. All popups already set `-topmost`, but on
Windows a freshly spawned process's first topmost window can still end up
behind whatever already has focus - "-topmost" isn't a request for focus,
and Windows' focus-stealing prevention doesn't grant it one automatically.
This is worst right after "Save, Exit, and Run" specifically, since
config.pyw's window is closing at the same instant Edgeware's first window
(the startup splash, then popups) is appearing.

Fixed in both `features/popup.py` (the shared base class for every popup
type) and `features/startup_splash.py` (the very first window you see):
shortly after the window is mapped, topmost is toggled off and back on, then
`.lift()`/`.focus_force()` are called. This is the standard, reliable fix for
this exact class of Tkinter/Windows issue.

## 9. Missing units on ms/sec/min settings
Several settings only mentioned their unit ("in milliseconds", "how many
seconds") in the helptext sentence, not in the label itself, so the compact
entry box next to them gave no hint at a glance. Rather than manually editing
each one (easy to miss some, and the same gap reappears for any setting added
later), `add_setting()` now automatically appends "(ms)"/"(sec)"/"(min)" to
any label of that type that doesn't already have it - covers every current
setting and any future one without needing to remember to do it by hand.

## 10. Pack override visibility
Packs can ship their own `config.json` with values for a small fixed set of
settings (`PACK_CHANCE_KEYS`: popup/video/audio/prompt/website chance,
subliminals chance, notification chance) that override yours when the pack
is selected and the setting is still at default. This was happening silently
- extracted the read side into `read_pack_overrides()` (pure, doesn't touch
your config, just tells you what a pack declares) and used it in two places:
- Every affected setting now shows a note under its helptext when the
  selected pack overrides it, and whether that override is currently in
  effect or not (e.g. if you'd already customized it yourself).
- The intensity presets below (item 11) show a shared note listing anything
  the current pack overrides regardless of preset choice.

Scope note: this only covers `PACK_CHANCE_KEYS` - if a pack's config.json
contains other keys, Edgeware doesn't currently read them at all (that's
existing behavior, not something this patch changes). Say the word if you'd
like that expanded to arbitrary keys instead of just those seven.

## 11. Intensity presets
Added four buttons at the top of the Start section - "A slight annoyance",
"A bit of a problem", "A real addiction", "Life-ending slavery" - each
setting a bundle of related knobs at once (popup/video/audio chance, delay
between popups, movement, denial chance, and corruption/mitosis/hibernate).
These are a reasonable starting point I picked, not a precise science -
adjust freely afterward, same as any other setting. Whatever the currently
selected pack overrides (item 10) is called out right below the buttons, so
it's clear at a glance which parts of a preset won't actually take effect
against that particular pack.

## 12. "Do Not Press" button (v22.0.2)
Added per request, after pushing back on and dropping the self-persisting/
disguised-copy part of the original idea (not built, not included here - see
chat for why). What's actually implemented, all built from existing Edgeware
mechanisms rather than new ones:

- A big red "DO NOT PRESS" button on the Start page in config.pyw. Clicking
  it opens a confirmation screen (full explanation, a safeword field, a
  lockout-time field, and a "type ARM to confirm" field) - nothing happens
  from a single accidental click.
- Arming sets three *real*, pre-existing Edgeware settings - "Run when
  Windows starts" (`start_on_logon`), Panic Lockout (`timerMode`), and the
  safeword/lockout time (`safeword`/`timerSetupTime`) - plus one new
  config.pyw-only bookkeeping flag (`_doNotPressArmed`) that main_edgeware.py
  checks at startup.
- When armed, `main_edgeware.py` picks a random installed pack and waits a
  random 5-90 minutes (silently) before starting, every time it launches -
  with the panic hotkey and lockout active for the *entire* wait, not just
  after something visible happens. The global panic hotkey itself is never
  disabled - only whether it responds immediately depends on the safeword/
  lockout time, exactly like using Panic Lockout manually anywhere else.
- A "Disarm" button undoes it (turns the startup shortcut and lockout back
  off); the feature is fully described in `README.md` under "Do Not Press",
  per the request that this be documented, not hidden.

**Found and fixed a real, pre-existing bug along the way:** config.pyw's
"Run when Windows starts" checkbox was cosmetic-only - it saved a flag to
`config.json`, but Edgeware's actual Settings loader never reads that key at
runtime (its `Item` has no `setting` callable in `config/items.py`), and the
real config window only makes it work by calling `os_utils.toggle_run_at_startup()`
directly as a side effect of saving. config.pyw never did this, so the
toggle never actually created or removed the Windows Startup shortcut.
Fixed in `save()` for every use of that setting, not just this feature.

Version bumped to v22.0.2 per request.
