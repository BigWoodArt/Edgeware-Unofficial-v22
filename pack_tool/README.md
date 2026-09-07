# Edgeware++ Advanced Pack Builder

A GUI tool for building Edgeware++ resource packs from a folder of mood
subfolders, without having to hand-write JSON or YAML.

## Requirements

- **Python 3.10+** on Windows, with the box checked to "Add python.exe
  to PATH" during install (get it from python.org if you don't have it).
  Tkinter and Tcl/Tk ship with the standard Windows installer, so no
  extra install is needed for the GUI itself.
- **pyyaml** - `run.bat` installs this automatically the first time you
  run it. (If it's missing, pack.yml still gets written using a simple
  fallback writer, just without pyyaml's cleaner formatting.)

## How to run

Double-click **`run.bat`**. It will check for/install `pyyaml`, then
launch the app.

(Alternative: open a terminal in this folder and run
`py edgeware_pack_builder_gui.py` directly.)

`banner.png` needs to stay in the same folder as the script - it's the
image on the front page.

**Tip:** if you place this whole folder *inside* your Pack Tool folder
(the one with `src/main.py` in it) - or as a sibling one level up from
it - the app auto-detects it on startup and you won't need to browse
for it. Once you've pointed it at the Pack Tool folder manually even
once, it's also remembered for next time via `builder_settings.json`,
regardless of where you put the two folders.

## How to use it

The app is three pages:

### Page 1 - Source & Pack Tool

- **Load Existing Pack** (folder or .zip) - reopens a pack you've
  already built, or attempts to reconstruct settings from any Edgeware++
  pack even if you didn't build it with this tool (see "Loading a pack"
  below).
- **Where is the folder of images?** - pick the folder containing one
  subfolder per mood. The first one (alphabetically) becomes the
  starting mood.
- **Pack Tool location** - auto-detected or remembered if possible (see
  above); set manually otherwise. If set, Build Pack compiles straight
  to a finished `.zip`. If left unset, you get a `pack.yml` + `media/`
  folder to compile yourself via `PackToolScript.bat` -> option 3.

### Page 2 - Whole-Experience Settings

- **Presets** - four one-click pacing curves (A Fun Distraction / A
  Slight Annoyance / A Real Addiction / Total Enslavement), each
  spreading a whole set of Advanced Settings knobs (popup speed, image/
  video/web/prompt chance, audio/video volume and concurrency, spiral
  chance/strength, denial chance, moving popups, and per-mood cycle
  length) across every mood at once - later presets ramp faster and, on
  several knobs, exponentially rather than evenly. You'll get a
  confirmation warning first, since this overwrites Advanced Settings
  for every mood. Applied values land as real, visible, editable numbers
  in each mood's Advanced Settings on Page 3 - nothing about a preset is
  hidden or locked in, it's just a fast starting point.
- Pack info (name/ID/creator/version/description).
- **Mood Cycling** - timer (in **seconds** now, not minutes - see note
  below) or popup count, plus an optional "ramp cycle length across
  moods" Start/End + Apply that spreads different cycle lengths per
  mood (e.g. early moods last longer, later ones cycle faster).
- **Escalating Spirals** and **Escalating Denial** - each has a Start %/
  End % and an Apply button. The Spiral checkbox alone still works as
  a build-time-only auto-ramp if you don't click Apply; Apply instead
  writes the actual per-mood numbers into Advanced Settings on Page 3 so
  you can see and hand-tune them.
- Pack-wide extras (hypno overlay images, a default wallpaper, a loading
  screen image), and build options (image/video compression, filename
  renaming) if a Pack Tool folder is set.

**Seconds, not minutes:** cycle length is now entered in seconds. This
followed from finding that Edgeware++'s own `config.pyw` offers a
seconds-based entry mode for this same setting, which is stronger
evidence than what I had before (a single log value that was *consistent
with* minutes but didn't actually prove it). The number you enter is
now sent to Edgeware's `corruptionTime` field completely unconverted -
no more risk of a unit-conversion bug like the last one. **Still worth
confirming in-game** that actual cycle timing matches what you set,
since the exact native unit hasn't been independently confirmed, just
narrowed down with better evidence. If you reload an older pack built
before this change, its cycle length will reset to the default (5
minutes' worth, now expressed as 300 seconds) since the field was
renamed - a one-time inconvenience, not a repeating one.

### Page 3 - Per-Mood Configuration

Each mood gets a collapsed card - click its name to expand. Inside:

- **Captions / Notifications / Subliminal messages / Prompts / Denial
  captions / Website popups** - all free text, one per line, per mood.
  Website popups support an optional `| arg1, arg2` suffix on a line to
  have one argument picked at random and appended to the URL (e.g.
  `https://example.com/search?q= | kittens, puppies`).
- **Wallpaper** - a background image to switch to when this mood starts.
- **Remove these moods when this one starts** - only lists moods that
  come *before* this one in the list (a mood can't remove something
  that isn't active yet). Leave everything unchecked and this mood's
  content just adds on top of what's already showing; check specific
  earlier moods to turn them off.
- **Advanced Settings** (collapsed by default) - popup speed, image/
  video/web/prompt chance, audio/video volume and concurrency, spiral
  chance/strength, denial chance, moving-popup chance/speed, and a
  per-mood cycle-length override (in seconds, or popup count - whichever
  matches the cycle mode picked on Page 2). Leaving a field blank means
  "keep whatever the previous mood had" - it does not reset to a
  default. This is also where Presets and the Page 2 Apply buttons
  (spiral/denial/cycle length) write their values, so after using any of
  those you'll see real numbers already filled in here, ready to
  hand-tune.

**Hover over anything** for a plain-language explanation.

Nothing you enter is lost by clicking **Back** - the app saves the
current page into memory before switching, and restores everything if
you come back to it.

### Building

Click **Build Pack**. You'll be asked to pick (or create) **one**
folder - everything is organized predictably from there:

- `<that folder>/pack_source/` - pack.yml + arranged media (the
  compiler's input)
- `<that folder>/pack_build/` - raw compiled output (only created if a
  Pack Tool folder was set)
- `<PackName>.zip`, sitting right inside the folder you picked - the
  file to actually load into Edgeware++ / hand to someone else. It
  includes a `plan.json`, so anyone you send it to can drop it straight
  into **Load Existing Pack** here and get an exact (not reconstructed)
  copy to keep editing.
  `pack_source`/`pack_build` are working files, safe to delete once
  you've confirmed the zip works.

A progress bar runs while this happens (compiling can take a while on
larger packs). It's an indeterminate spinner, not a percentage - the
Pack Tool compiler doesn't report incremental progress, so a real
percentage isn't available to show.

## Loading a pack

Two buttons on Page 1: **Load Existing Pack (Folder)** and **(ZIP)**.

- If the pack has a `plan.json` in it (anything built by this tool),
  loading is **exact** - every setting comes back precisely as entered.
- If there's no `plan.json` (a pack from anywhere else, or one that
  lost it), you'll be asked: *"plan.json not available for this pack.
  Want to try reconstructing settings from the pack's own files
  instead? This will be an approximation, not an exact match."*
  Saying yes reads `info.json`, `index.json`, `media.json`,
  `corruption.json`, and `config.json` directly and rebuilds pack name,
  mood list, captions/notifications, corruption levels (mapped back to
  wallpaper triggers, audio settings, Advanced Settings fields, and the
  remove-checklist), and re-groups media files back into per-mood
  buckets using `media.json`'s own tags.

  **This reconstruction path is best-effort and not yet verified
  against a real compiled pack's exact JSON layout** - it's built from
  pack.yml's documented structure (which the compiler is described as
  generating these files from) plus the `config.json` shape confirmed
  from actual Edgeware++ log output. If a file doesn't parse the way
  expected, that specific piece is skipped (not the whole load) and
  reported back to you as a warning banner on the front page, rather
  than failing silently. If reconstruction doesn't work well on a real
  pack, the warnings + the actual `info.json`/`index.json`/`media.json`/
  `corruption.json` contents are exactly what's needed to fix it - same
  as everything else in this project so far.

## What to test / report back

- **Does the cycle-length number in seconds actually match real in-game
  timing?** This is the main open question from this build (see the
  seconds/minutes note above).
- Do the four presets feel right? These are a first draft, not
  something final - specific numbers are easy to adjust once you've
  seen them play out in-game.
- Does the finished pack load correctly in Edgeware++?
- **Does mood 1's content show up immediately when the pack loads, or
  only after the first mood-cycle interval elapses?** Every mood now
  gets explicitly activated by its own corruption level (no more
  reliance on Edgeware's reserved "default" mood, which testing showed
  doesn't reliably display its content even when nominally active).
  This is the one open question I couldn't verify without running
  Edgeware myself.
- Do the Advanced Settings values actually show up/behave as expected
  in-game (popup speed, spiral strength, etc)?
- Does loading a pack with no `plan.json` produce a reasonable
  reconstruction? What's in the warning banner, if anything?
- Any tooltip that's confusing, wrong, or missing.
- Any error dialog - screenshot it, the full text is usually copyable
  and helps a lot for tracking down what happened.

## Known limitations

- Loaded packs (via **Load Existing Pack (ZIP)**) get extracted into a
  `loaded_packs/` folder next to this script, not a temp folder - this
  is deliberate, so file paths (wallpapers especially) stay valid even
  if you load a pack, walk away, and build much later. Old subfolders
  in there are safe to delete once you're done with that particular
  loaded pack.
- If a wallpaper file referenced by a mood (or the default wallpaper)
  can't be found at build time, the build now stops with a clear error
  naming exactly which mood and file - it used to fail silently and
  ship a pack with a black wallpaper instead. If you hit this, re-pick
  that wallpaper on the Per-Mood page.
- No numeric "notification frequency" dial - notification *text* is
  per-mood, but Edgeware++'s published config reference doesn't list a
  separate frequency knob for notifications specifically. Notifications
  continuing to display for a bit after hitting Panic also looks like
  core Edgeware behavior (already-fired notifications running out their
  own timer) rather than something this tool's config controls.
- Dangerous system settings (junk-file filling, disabling the panic
  button) are intentionally left out of this tool entirely.
- Some images (webp especially) may render as a black square in
  Edgeware++. Confirmed as a known Edgeware++ bug independent of this
  tool during earlier testing - not something this tool can fix.
- The progress bar is indeterminate (no real percentage available from
  the compiler).
- Pack reconstruction (loading a pack with no `plan.json`) is
  best-effort and unverified against a real compiled pack - see
  "Loading a pack" above.
