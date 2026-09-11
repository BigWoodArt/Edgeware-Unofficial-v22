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

## 13. Fixes and additions from the crash report + follow-up requests

**Fixed the save crash from the screenshot.** `apply_startup_toggle()` (added
last round) does `import os_utils`, and `os_utils/windows.py` imports the
`mpv` Python binding at module level for unrelated features bundled in that
same file. `main_edgeware.py`/`panic.py` already add libmpv's DLL folder to
`PATH` before touching anything mpv-related; `apply_startup_toggle()` never
did, since it never needed to before. Fixed the same way, using the same
`data/` folder both of those already point at.

**"Do Not Press" moved to the sidebar.** It's now a text button at the
bottom of the left column, under "Open Edgeware folder", instead of a big
button on the Start page. It reads "DO NOT PRESS" normally and switches to
"Disarm 'Do Not Press'" once armed - same confirmation flow either way,
just relocated and always visible regardless of which page you're on.

**Pack override visibility, upgraded.** The "Pack to run" setting now shows
a summary of every setting the selected pack's own config.json declares,
right where you pick it, using friendly names instead of raw keys (e.g.
"Image popup chance -> 80" instead of "popupMod -> 80"). The intensity
presets' pack-conflict note was upgraded to match.

**New "Priority" setting**, in Start right under Safe Mode. This replaces
the old "only apply a pack's override if you haven't customized that
setting" heuristic with an explicit choice:
- OFF (default) - the pack's values win. This is now enforced both when you
  select a pack *and* again right before every save, so it's a standing
  guarantee, not just a one-time nudge you could quietly undo by editing the
  field afterward.
- ON - your saved values always win; pack overrides are never applied.

Every affected setting's "PACK OVERRIDE" note now reflects which mode is
active and what will actually happen on save, instead of the old wording
that assumed the "only if default" behavior.

## Feasibility: using this config.pyw against older/unpatched Edgeware

Worth clarifying first: upstream, "v21" is the actual latest official tag,
and it's the exact codebase all of this has been built against and patched
on top of - "v22" is a label I've been using purely for tracking our own
config.pyw and source patches, not a separate official release. So the real
question is: would this config.pyw work against a *vanilla, unpatched* v21
install (none of the `main_edgeware.py`/`panic.py`/`image_popup.py`/
`popup.py`/`startup_splash.py`/`EdgewareSetup.bat` changes applied)?

- **Everything that just reads/writes config.json** (all the settings tabs,
  the WebP<->GIF converters, intensity presets, pack override display,
  Priority) - yes, this should work fine. None of it depends on anything I
  changed in Edgeware's actual Python source; it only depends on the
  config.json key schema, which I never touched.
- **"Fix Edgeware theme background"** - checked this directly rather than
  assuming: it does an exact-text patch against `popup.py`, and the specific
  text it looks for is untouched by my topmost fix (which lives elsewhere in
  the same file), so this works against both the patched and unpatched
  version.
- **"Do Not Press"** - this is the real exception. Arming it only *sets
  config flags*; the random-pack/random-delay/early-lockout behavior is
  implemented in the `main_edgeware.py` patch. Against vanilla v21, arming
  would silently do nothing beyond turning on ordinary "Run at Startup" and
  "Panic Lockout" - no random pack, no delay, no early lockout. Not broken,
  just quietly inert, which is arguably worse than an error. If this
  matters to you, say so and I'll add a startup check that warns instead of
  going silent.
- **The two runtime bugfixes** (popups appearing behind other windows,
  animated WebP as a black square) obviously don't apply at all without
  their respective source patches - vanilla v21 would still have both bugs.

## 14. Fixed: config.pyw wouldn't start at all

Sorry - this one was on me. When I replaced `apply_pack_chance_overrides`'s
old `only_if_default` parameter with the Priority-flag design, I updated
three of the four call sites but missed the one in `App.__init__` (the very
first thing that runs on startup), which still passed the old
`only_if_default=True` argument the method no longer accepts - hence the
error on every launch.

Fixed, and this time verified properly instead of just syntax-checking:
actually constructed the App under a virtual display, rendered every single
settings section (exercising every setting row, not just a sample), and ran
a full save() cycle end to end. All clean. That test would have caught this
before it shipped, so it's now part of how I check config.pyw changes rather
than an afterthought.

## 15. "Do Not Press" looks like a button now; Priority reworked properly

**1. Button styling** - "DO NOT PRESS" in the sidebar now has a solid red
background with white text (matching the danger color used elsewhere),
instead of just colored text sitting on the normal sidebar background.

**2/3. Priority redesigned, and moved to where it actually belongs.** You
were right on both counts, and the second point (Save+Exit, then running
edgeware.pyw later, separately) is exactly the flaw that made the whole
approach wrong, not just incomplete:

- The old "Priority" bool only covered the 7 chance settings
  (`PACK_CHANCE_KEYS`), which is why your Pack Builder pack's corruption
  settings weren't affected by it at all - corruption keys were never in
  scope to begin with.
- More importantly, the old design applied pack overrides *inside
  config.pyw*, baking them into the saved config.json at pack-selection and
  save time. That's exactly what breaks the moment you Save & Exit and then
  launch `edgeware.pyw` on its own later, or via Windows startup, or however
  else - config.pyw isn't in the loop at that point, so nothing re-applies.
- Fixed by moving the actual enforcement into `main_edgeware.py` itself, so
  it runs fresh every time Edgeware actually starts, regardless of *how* -
  config.pyw's Save/Exit/Run, edgeware.pyw directly, Do Not Press, Windows
  startup, a scheduled task. New function `apply_pack_priority()`, called
  right after the pack loads, before anything reads corruption/hibernate/etc.
  It reuses each setting's own `Item` schema and unit-conversion callable
  from `config/items.py` - the exact same validation and coercion
  `Settings.load_settings()` itself uses - rather than a simplified
  reimplementation that could silently drift out of sync (e.g. get a
  seconds-vs-milliseconds conversion wrong). Verified this directly against
  the real `CONFIG_ITEMS`, including a value that should get rejected by
  validation and one that needs unit conversion, both behaving correctly.
- It also now covers **every setting a pack can specify**, not just the old
  7-key subset - corruption pacing, hibernate mode, whatever the Pack
  Builder writes.
- Renamed per your suggestion: "Priority" is now "Pack Priority" (default -
  matches what you described as the expected behavior) or "Default
  Priority", instead of an ON/OFF toggle.
- config.pyw itself no longer bakes pack overrides into the saved file at
  all - it now only *displays* what a pack declares and what would happen
  (both on the "Pack to run" row and on each affected setting), without
  mutating your actual saved preferences. This matters for the same reason
  as above: if it baked pack values into config.json, switching to Default
  Priority later wouldn't actually restore your real settings, since they'd
  already have been overwritten.

This effectively replaces the old v21 manual "Load Pack Configuration ->
then Save/Exit" workflow with something that just happens correctly on its
own, for the case that actually matters (Priority: Pack, the default).

## 16. Final batch for v22.0.2 - all items from the last review round

**UI cleanup:**
- Font sizes bumped across config.pyw (~+2pt everywhere).
- "Run when Save and Exit is used" removed - redundant now that "Save, Exit,
  and Run" exists as its own button. Plain "Save and Exit" now only ever
  saves and closes.
- "Create Edgeware desktop shortcuts" removed from the UI per request.
- "DO NOT PRESS" and "Arm it" now use a dedicated crimson (`#DC143C`),
  separate from the shared caution-red used for warning text elsewhere.
- Purple "pack override" text cut down to one line per setting
  ("Pack default for this setting is X. Pack Priority is ON."), booleans
  shown as ON/OFF instead of 1/0, and only shown at all when Priority is
  set to Pack Priority - hidden entirely under Default Priority.
- The pack-selection summary (and the intensity-preset conflict note) no
  longer lists every overridden setting inline - for a pack overriding many
  settings, that line grew unbounded and pushed the Save/Cancel buttons
  off-screen. It now shows a fixed-length count instead ("This pack
  specifies N setting(s)..."), with full detail still available on each
  individual setting's own row.

**Real bugs fixed:**
- Panic wallpaper going black: `restore_panic_wallpaper()`'s check for
  whether the captured "original" wallpaper file had drifted from the saved
  snapshot only ran when Replace Images was on. Windows regenerates its own
  wallpaper cache independent of that setting, so the check now always
  runs, closing the gap that was producing a black screen on Panic even
  with a completely empty pack.

**New features:**
- Corruption Preview tab: pack image/video/audio counts, corruption trigger
  type, level count, and a compact scrollable per-level dump (mood
  add/remove, wallpaper, config overrides) - built as a single text block
  rather than one widget per level, since packs can have 20+ levels.
- "Corruption Level Increased to N" notification, gated behind the
  (previously unexposed) `corruptionDevMode` setting, now surfaced as a
  toggle in the Corruption section.
- Subliminal caption text can now use White/Black/Pink text with a
  White/Black outline (`capPopTextColor`/`capPopOutlineColor` - two new
  real Settings/Item entries, not config.pyw-only). Required rewriting
  `subliminal_popup.py` from a Label to a Canvas, since Tkinter Labels have
  no native text outline; verified the sizing/positioning math directly
  under a real Tk instance.

**Diagnosed, not a bug in this patch:** subliminal text not appearing was
traced to two issues in the specific pack being tested (from Pack Builder),
not to anything in config.pyw or these source changes:
1. The pack's first active mood had zero subliminal lines defined (later
   confirmed intentional).
2. The pack's corruption escalation tuned `subliminalsChance`/
   `subliminalsAlpha`, which actually control the hypno/image-overlay
   effect, not subliminal caption text (`capPopChance`/`capPopOpacity`) -
   a genuinely confusing pre-existing naming collision in Edgeware itself.
Feedback text for the Pack Builder tool was provided separately in chat.

## 17. v22.0.3

1. **Status bar overflow (same class of bug as the earlier purple-text
   overflow, just a spot I missed)** - the "Pack selected: ..." status line
   at the bottom of the window still listed every overridden setting by
   name, which for a pack overriding many settings pushed the Save/Cancel
   buttons off-screen exactly like before. Now shows a bounded count
   ("It specifies N setting(s)...") like everywhere else.
2. **Priority dropdown didn't update anything live** - switching between
   Pack Priority/Default Priority only updated the on-screen dropdown
   itself; `self.cfg` (and therefore every "Pack Priority is ON" note)
   didn't actually change until the next save, so clicking back and forth
   showed stale text. Added a proper change handler so switching the
   dropdown updates immediately and the purple notes appear/disappear in
   real time - verified directly (switched modes without saving, confirmed
   notes vanish and reappear correctly).
3. **Investigated the corruption level report, did not change any code.**
   Reproduced the reported pack's exact `corruption.json` against
   Edgeware's real level-loading and mood-matching logic directly - it
   produces the correct result, not what the debug label showed. More
   importantly, found that Edgeware's "fade" mechanism only ever previews
   one level ahead of the actual current level, so seeing level-3 and
   level-5 mood content while the debug label reads "Current Level: 1"
   is much better explained by the *label* being stale/wrong than by
   corruption actually being stuck - fade couldn't reach that far ahead
   otherwise. Didn't touch this code without being able to confirm it
   live; flagged what would confirm it either way.
4. Version bumped to v22.0.3.

## 18. v22.0.4 - the real Priority bug, settings cleanup, README replacement

**Found and fixed the actual reason Default Priority "wasn't working."** This
is bigger than the corruption_full scope gap from last round. `main_edgeware.py`'s
`read_priority_mode()` was checking the saved value against the strings "Pack"/
"Default" - but config.pyw's dropdown saves the full strings "Pack Priority"/
"Default Priority". Neither ever matched, so the function always fell back to
"Pack Priority" regardless of what was actually selected - meaning Default
Priority has never been honored by the runtime at all, for any setting, since
it was introduced. Fixed the string comparison, and combined it with the
corruption_full fix agreed on last round: Default Priority now also forces
`settings.corruption_full = False` in memory for that session (never writes
over the saved value), so it's a complete "ignore what the pack wants"
guarantee covering both the flat config.json overrides and corruption's
separate per-level escalation permission. Verified both directly against the
real Settings/Pack/CONFIG_ITEMS classes: Default Priority now correctly
applies nothing and forces corruption_full off; Pack Priority still applies
everything as before.

**Removed 5 settings confirmed to have no effect on Edgeware's runtime or on
this tool** (all checked directly against actual usage in the codebase, not
guessed): `safeMode`, `messageOff`, `toggleMoodSet`, `toggleInternet` (all
four only ever mattered inside Edgeware's *original* built-in config window,
which this tool replaces), and `toggleHibSkip` (referenced nowhere at all
outside its own definition - currently does nothing anywhere).

**Fixed stale/inaccurate tooltips** on the three Troubleshooting settings that
remain: Lanczos resizing no longer references the pre-v22 WebP behavior;
hardware acceleration and separate-video-process wording clarified.

**README.md fully replaced** with the version provided, dropping a broken
`screenshots/demo.png` reference that isn't in this repo.

Version bumped to v22.0.4.

## 19. Two real, serious bugs in config.pyw's save flow - found and fixed

**The main one: `render()` reset the widget-tracking dict on every tab
switch.** `self.vars={}` ran every single time you navigated to a different
tab, wiping the entries collect() (called by every Save variant) reads from.
So collect() could only ever see whatever tab happened to be open at the
exact moment you clicked Save - any change made on a tab you'd since
navigated away from was silently discarded, reverting to its old value with
no warning. This is almost certainly what you were running into. Reproduced
it directly (changed a setting, switched tabs, saved, watched it revert) and
confirmed the fix the same way - changes across multiple tabs, none of them
the currently-open one, now all survive correctly.

**Found a second, related bug while fixing the first.** The "multiline" type
(used for the Protected Folders / avoidList setting) stores the actual
Tkinter Text widget in that same tracking dict, not a persistent Variable
like every other setting type. Unlike a StringVar or BooleanVar, a Text
widget is destroyed the moment you leave its tab - so simply keeping entries
around (the fix above) meant collect() would crash with a TclError if you
edited that field, switched tabs, and saved. Fixed by having the Text widget
sync its content straight into self.cfg on every edit (via Tk's `<<Modified>>`
event) instead of collect() trying to read the widget later. Verified against
the exact scenario that crashed: edit, navigate away, save - works correctly
now, and confirmed a full pass through every section still saves cleanly.

## 20. v22.0.5 - the actual complete fix for cross-tab saving, dialog removed, presets rewritten, dependent-setting graying

**1) Found the real, deeper bug behind "still not saving."** Your repro
(change a value, switch tabs, switch back to the SAME tab, value reverted -
no save involved at all) pointed at something more fundamental than the
save-time fix from last round: every setting widget only wrote into
self.cfg at save time. Navigating back to a tab rebuilds its widgets from
self.cfg, which never received your in-progress edit - so it always showed
your last *saved* value, never your last *typed* one. Fixed properly this
time: every single setting now writes into self.cfg immediately as you
change it (a trace on the underlying Variable for typed/dragged fields, a
direct call for the bool click-toggle and comboboxes), the same pattern I
used for the multiline field previously - just applied everywhere instead
of one field. collect() still runs at save time too, as a redundant safety
net, but the actual fix is that nothing depends on it being the *only*
place values get written anymore. Verified directly: change a value,
navigate away, navigate back to the same tab with no save in between -
value now persists correctly.

**2) Corruption Config Warning dialog removed.** It was a blocking
`messagebox.askyesno` in `main_edgeware.py` itself that calls `sys.exit()`
on "No" - and it's actively dangerous with Do Not Press specifically, since
an unattended session has nobody there to click it, meaning it could hang
Edgeware at startup forever. Removed the call entirely; config.pyw already
surfaces the same information non-blockingly.

**3) Intensity presets rewritten to the finalized table**, all clean
integers throughout (including explicit 0s for inactive fields like
`mitosisStrength` when mitosis is off, per your note about the Pack
Builder's float-value bug), expanded to cover the full set of settings
from our table: popup pacing, movement, denial, subliminals, notifications,
audio/video limits, and corruption/mitosis/hibernate.

**4) Built dependent-setting graying.** Every setting that only matters
when a "parent" setting is on (or, for five percentage-based settings,
above zero) now visually grays out and disables its input when its parent
is off - and updates immediately in place, without a full section re-render,
so it can't cause the same jerky/wrong-reset behavior the hibernate dropdown
had. Covers every parent/child pair discussed: timeoutPopups, rotateWallpaper,
downloadEnabled, low-key mode, mitosis, hibernate, corruption (including the
three-way corruptionTrigger branching - only the setting matching the
current trigger choice is enabled), scheduling, fill/replace (sharing
drivePath/avoidList), panic lockout, and the five threshold-gated settings
(movingChance, capPopChance, subliminalsChance, notificationChance,
promptMod). `showCaptions` and `webPopup` deliberately left standalone, per
your call. Verified all four dependency categories directly (bool-gated,
threshold-gated, the corruptionTrigger 3-way case, and the shared
fill/replace case), plus confirmed the in-place widget disable/enable
actually happens without needing render() to run again.

Also fixed properly this round while touching hibernate: `hibernate_changed()`
now persists which preset name was picked (`hibernateType`), the item-4 fix
from last round - included here since it's part of the same pass.

Version bumped to v22.0.5. Per your note, I'll bump the patch number on
every future build from here on, regardless of how small the change is.

## 21. v22.0.6 - disabled-row styling fixes

Grayed-out (disabled) settings weren't actually reading as "disabled" -
found three separate causes and fixed all three:

1. **Text was too light.** The gray-out feature was reusing `dim`, but
   `dim` is also used elsewhere (nav title, status bar, wallpaper caption,
   group headers) as legible secondary text - darkening it globally would've
   hurt those. Added a new dedicated `disabled` color per theme instead,
   set close to each theme's own `border` color (deliberately low-contrast,
   as requested - it doesn't need to stay readable).
2. **Dropdowns ignored the theme entirely when disabled.** The
   `Pretty.TCombobox` ttk style only had colors mapped for the `readonly`
   state, nothing for `disabled` - so a disabled dropdown fell back to
   ttk's default light-colored look regardless of theme. Added a `disabled`
   mapping using the same theme colors as everything else.
3. **Entry boxes went white when disabled.** Plain Tkinter Entry widgets
   have dedicated `disabledbackground`/`disabledforeground` options that
   were never set, so they fell back to Tk's default (light) disabled
   look. Set explicitly now.

Also worth noting: there are actually 7 manager themes, not 6 - "Crimson/
Violet" (the default, and what your screenshot was actually showing) is
built straight from the base palette rather than being one of the 6 named
overrides. Caught this because the test suite checked every theme in
`THEME_PALETTES` rather than just the 6 I initially touched, not because
the visual issue would've shown up any other way - worth keeping in mind
that this file has 7 themes total, not 6, next time a palette-wide change
comes up.

Version bumped to v22.0.6.

## 22. v22.0.7 - real fix: Pack Priority overrides were being silently wiped by corruption's first level

Found via the buttonless report - and it's not specific to `buttonless` at
all, it affects every setting Pack Priority applies. Root cause:
`apply_pack_priority()` set each overridden setting directly via `setattr`,
but never touched `settings.config` (the raw dict). Corruption's own level
application (`apply_corruption_level`) calls `settings.load_settings()`
every time a level applies - including essentially immediately at startup,
for Timed/Popup/Script triggers, since `corruptionFullPerm` is itself
usually one of the things Pack Priority just turned on. That reload
re-derives every setting FROM `settings.config`, which still had the
original (un-overridden) values - silently wiping out everything Pack
Priority had just applied, within moments of startup.

Fixed: `apply_pack_priority()` now writes into `settings.config[key]`
alongside the derived attribute, for both the Pack Priority apply loop and
the Default Priority `corruption_full` forcing - so any later
`load_settings()` call re-derives the *same* value instead of reverting.
Verified directly: reproduced the exact failure (`buttonless` reverting to
False the instant a corruption level applied) against the real Settings/
Pack/CONFIG_ITEMS classes, confirmed the fix holds under the same sequence,
and separately confirmed Default Priority's `corruption_full = False` also
survives a later reload rather than reverting.

Version bumped to v22.0.7.

## 23. v22.0.8 - real fix: Edgeware wouldn't start at all on newer Python

Traced via a direct console run (thank you for grabbing that traceback -
this would have been very hard to pin down blind, since `run_edgeware()`
launches Edgeware via `subprocess.Popen()` with no output captured at all,
so a crash like this is completely invisible through normal use).

**Root cause, confirmed via the actual traceback:** `OSError: Cannot find
mpv-1.dll, mpv-2.dll or libmpv-2.dll in your system %PATH%`. This is a
real, pre-existing fragility that was already in the codebase (not
something introduced by v22.0.7) - `main_edgeware.py`, `main_config.py`,
and `panic.py` all try to make libmpv findable by mutating
`os.environ["PATH"]` at runtime. Since Python 3.8, Windows' ctypes-based
DLL loading (which `python-mpv` uses internally) runs in "safe DLL search
mode" and does not reliably respect `PATH` changes made after the process
starts - the officially recommended fix since 3.8 is
`os.add_dll_directory(path)`. You're on Python 3.14, well past that
change, so the old approach was silently failing.

**Fixed in all 4 places this pattern appears**: the 3 above (unmodified by
me until now) plus config.pyw's own `apply_startup_toggle()` (added a few
rounds back for the "Run when Windows starts" fix, and likely equally
broken on your machine, just not something you'd hit unless you toggled
that specifically). Each now calls `os.add_dll_directory()` in addition to
the existing PATH mutation (kept as a harmless fallback), wrapped in a
try/except for non-Windows platforms where that function doesn't exist.

Verified: confirmed `os.add_dll_directory` correctly falls back via
try/except on this non-Windows sandbox, and ran the full startup sequence
end to end with no crash. Can't fully verify the Windows-specific DLL
loading itself without a live Windows test, but the underlying cause and
fix are both textbook, well-documented Python/Windows behavior, not a
guess.

Version bumped to v22.0.8.

## 24. v22.0.9 - real fix: video popups freezing all clicks, especially in video-heavy packs

**Root cause, confirmed by reading the actual code path:** every time a
video popup was about to appear, `get_video_properties()` (in
`video_popup.py`) spawned `ffprobe.exe` and waited for it to finish -
synchronously, on the same thread that runs Tkinter's entire event loop.
While that's running, nothing in the whole program can respond to input,
including clicks on unrelated image popups already on screen - the OS
still queues the clicks, but Tk can't drain that queue until ffprobe
returns. That exactly explains the reported symptom: images not closing on
click, then several closing at once right as a video popup appears - the
queued clicks all firing together the instant the freeze ends. Confirmed
`VideoPlayer.play()` itself is not a second freeze point (it launches mpv
via a non-blocking `subprocess.Popen` in the default mpv-subprocess mode).
Hardware acceleration was never related - this freeze happens before mpv
or any decoding is involved.

**Fix:** `get_video_properties()` now runs on a background thread, and the
popup window itself isn't created until the probe returns - avoiding both
the freeze and a jarring resize-into-place after the window is already
visible (the window now simply appears a beat later than before, already
correctly sized, rather than appearing immediately and blocking everything
while it resizes). `state.video_number`'s reservation is correctly rolled
back if the probe fails or the app is shutting down mid-probe, so a failed
video doesn't permanently eat into `max_video`'s cap.

Verified directly: measured the constructor returning in ~0.2ms instead of
blocking for the probe's duration, confirmed a simulated click scheduled
during a simulated slow (300ms) probe fires exactly on time instead of
being delayed, and confirmed the popup successfully completes full
initialization (correct geometry from the probed dimensions, `.player`
created, `init_finish()` reached) once the probe returns. Caught and fixed
a real bug of my own along the way: an early draft used `self._root` as a
staging attribute name, which collided with Tkinter's own internal
`Misc._root` method and broke widget creation - renamed to `_pending_root`
etc. before shipping.

Version bumped to v22.0.9.
