# Edgeware++ Advanced Pack Builder

A GUI tool for building Edgeware++ resource packs from a folder of mood
subfolders, without having to hand-write JSON or YAML.

## Features

- Point it at a folder of mood subfolders and it builds a full pack -
  index, corruption levels, config, and (through the real Pack Tool
  compiler) the final `.zip` - without hand-editing YAML or JSON.
- **Media Review** page: review, add, or remove the images/videos/audio
  and wallpaper for each mood - handy for touching up a pack someone
  else made, not just fresh builds. Removing a file only excludes it
  from the built pack; your original source folder is never touched.
- **Per-Mood** page with a sidebar of mood tabs (cropped preview
  thumbnails, click to switch), captions/notifications/subliminal text,
  per-mood Advanced Settings (auto two-column on a wide enough window),
  and mood removal rules.
- Four built-in **Presets** (Slight Annoyance / Bit of a Problem / Real
  Addiction / Life-Ending Slavery) that spread a full set of intensity
  values across however many moods your pack has, plus standalone
  Escalating Spirals and Escalating Denial ramps with their own
  Start/End/Apply controls.
- **Pack-Wide Settings**: Corruption mode, Hibernate mode, Mitosis mode
  (+ strength), Level transition (Normal/Abrupt), and Buttonless popups,
  all as simple on/off toggles.
- Loads an existing pack (folder or `.zip`) back in for editing,
  reusing its `plan.json` when present or reconstructing settings from
  the pack's own files otherwise.
- Background loading/building throughout - extracting a zip, scanning a
  folder, generating media previews, and compiling the final pack all
  run off the main thread with a progress indicator, so the window
  never just freezes.
- Every build writes a `<pack name>_build.log` next to the zip, and
  offers to clean up the temporary working folders afterward.

## Version History

A quick-reference changelog, oldest to newest:

- **v0.1** - Initial pack builder: folder-to-pack pipeline, per-mood
  cards (captions/notifications/subliminal/prompts/web/advanced
  settings) in a single scrolling page, wallpaper/audio pickers,
  Escalating Spirals/Denial, four original presets, Load Existing Pack.
- **v0.2** - Fixed a `corruptionTrigger` typo ("Popups" instead of
  "Popup") that silently broke popup-count-based mood cycling; added a
  reminder that "Allow full corruption permissions" has to be turned on
  in Edgeware itself for any per-level escalation to apply; fixed
  reconstruction only recovering the first mood when a corruption level
  listed several; stopped stale files from old builds surviving into
  new ones by wiping `pack_build/`/`pack_source/media/` before every
  compile.
- **v0.3** - Corrected subliminal-text keys (`capPopChance` /
  `capPopOpacity` / `capPopTimer`) that had been conflated with the
  hypno-overlay keys (`subliminalsChance` / `subliminalsAlpha`); added a
  persistent build log file.
- **v0.4** - Found and fixed the root cause of corruption levels not
  triggering at all in real packs: Advanced Settings and presets could
  produce fractional (non-integer) values, and Edgeware++'s loader
  rejects the *entire* corruption file if even one value anywhere isn't
  a plain int - now everything is rounded before it's written.
- **v0.5** - All four presets replaced with new tiers (Slight Annoyance
  / Bit of a Problem / Real Addiction / Life-Ending Slavery) covering a
  much wider set of fields; added System Notification chance/image
  fields and Popup Opacity; added the Pack-Wide Settings panel
  (Corruption/Hibernate/Mitosis mode, Mitosis Strength).
- **v0.6** - Per-Mood page redesigned around a sidebar of mood tabs with
  cropped preview thumbnails (Pillow added as a dependency) instead of
  one long scrolling list of collapsible cards; Advanced Settings made
  always-visible instead of collapsed, with an auto two-column layout
  on wide windows; loading a zip or folder now runs in the background
  with a progress bar instead of freezing the window.
- **v0.7** - Added Level Transition (Normal/Abrupt) and Buttonless
  popups toggles; fixed a bug where some Advanced Settings on/off
  toggles could stop responding to clicks.
- **v0.8 (current)** - Added the Media Review page between
  Whole-Experience Settings and Per-Mood: review/add/remove each mood's
  images, videos, and audio (non-destructively), with Wallpaper moved
  here from the Per-Mood page. Images and Videos display separately in
  collapsible, 3-column preview grids and load lazily in the background
  per mood, so opening the page or switching moods stays fast even on
  packs with a lot of media.

## Requirements

- **Python 3.10+** on Windows, with the box checked to "Add python.exe
  to PATH" during install (get it from python.org if you don't have it).
  Tkinter and Tcl/Tk ship with the standard Windows installer, so no
  extra install is needed for the GUI itself.
- **pyyaml** and **pillow** - `run.bat` installs both automatically the
  first time you run it. (If pyyaml is missing, pack.yml still gets
  written using a simple fallback writer, just without pyyaml's cleaner
  formatting. Pillow is needed for the mood/media preview thumbnails -
  without it, the app still runs, just with plain placeholders instead
  of images.)

## How to run

Double-click **`run.bat`**. It will check for/install `pyyaml` and
`pillow`, then launch the app.

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

The app is four pages: Source & Pack Tool, Whole-Experience Settings,
Media Review, and Per-Mood Configuration.

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

- **Presets** - four one-click pacing curves (Slight Annoyance / Bit of
  a Problem / Real Addiction / Life-Ending Slavery), each spreading a
  full set of Advanced Settings knobs (popup speed, image/video/web/
  prompt chance, audio volume/concurrency, video volume/concurrency,
  auto-close/single-popup-mode, moving popups, subliminal text chance/
  opacity/duration, system notification chance/image chance, and
  per-mood cycle length) across every mood at once, on an exponential
  curve - later moods ramp up faster than a straight line would. You'll
  get a confirmation warning first, since this overwrites Advanced
  Settings for every mood. Applied values land as real, visible,
  editable numbers in each mood's Advanced Settings on the Per-Mood
  page - nothing about a preset is hidden or locked in, it's just a
  fast starting point. Presets don't touch the hypno overlay
  (Spiral) fields - use the Escalating Spirals control below for that.
- Pack info (name/ID/creator/version/description).
- **Mood Cycling** - timer (in **seconds**) or popup count, plus an
  optional "ramp cycle length across moods" Start/End + Apply that
  spreads different cycle lengths per mood (e.g. early moods last
  longer, later ones cycle faster).
- **Pack-Wide Settings** - things Edgeware++ can only apply to the
  whole pack at once, not per mood: **Corruption mode**, **Hibernate
  mode**, **Mitosis mode** (with a Strength slider, 2-10, grayed out
  unless Mitosis mode is on), and **Level transition** (Normal/Abrupt -
  Abrupt shown in red) and **Buttonless popups** toggles.
- **Escalating Spirals** and **Escalating Denial** - each has a Start %/
  End % and an Apply button, which writes the actual per-mood numbers
  into Advanced Settings on the Per-Mood page so you can see and
  hand-tune them afterward.
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

### Page 3 - Media Review

A sidebar of mood tabs (same cropped-thumbnail style as the Per-Mood
page) down the left; pick a mood to review its media on the right.

- **Images** and **Videos** - separate, independently collapsible
  sections, each showing a 3-column grid of preview thumbnails (videos
  show a plain icon, not an actual frame - the tool doesn't pull real
  video previews). Each tile has a **Remove** button; **Add Images...**/
  **Add Videos...** bring in more. Removing a file here only excludes it
  from what gets built - your original source folder is never touched
  or deleted from.
- **Audio** - same idea, a plain list with Remove/Add Audio Files.
- **Wallpaper** - the per-mood wallpaper picker lives here now (moved
  from the Per-Mood page).

The first time you open a mood here, whatever's currently governing its
media (a folder scan, or an already-explicit file list) gets turned
into one concrete, editable list - from then on, that list is what
actually gets built, regardless of what's added to or removed from the
original source folder afterward. A mood you never click into on this
page is untouched and just uses its folder contents normally.

Loading previews runs in the background with a progress indicator, and
only for the mood you're currently looking at - switching to a mood you
haven't opened yet loads its previews on the spot; switching back to
one you've already viewed is instant.

### Page 4 - Per-Mood Configuration

A sidebar of mood tabs down the left (150px, with a cropped preview
thumbnail and the mood's name - crimson when selected, gray otherwise);
pick a mood to edit its settings on the right. Both the sidebar and the
main panel scroll independently if there's more content than fits.
Switching tabs never loses anything you've typed - every mood's fields
stay alive in memory for the whole time you're on this page, only
hidden, not rebuilt, when you switch away.

Inside each mood's settings:

- **Captions / Notifications / Subliminal messages / Prompts / Denial
  captions / Website popups** - all free text, one per line, per mood.
  Website popups support an optional `| arg1, arg2` suffix on a line to
  have one argument picked at random and appended to the URL (e.g.
  `https://example.com/search?q= | kittens, puppies`).
- **Remove these moods when this one starts** - only lists moods that
  come *before* this one in the list (a mood can't remove something
  that isn't active yet). Leave everything unchecked and this mood's
  content just adds on top of what's already showing; check specific
  earlier moods to turn them off.
- **Advanced Settings** - always visible below the fields above (no
  more expand/collapse), automatically laid out in two columns per
  group instead of one if the window's wide enough when the page is
  built. Covers popup speed, image/video/web/prompt chance, auto-close/
  single-popup-mode (on/off switches, not text fields), audio/video
  volume and concurrency, hypno overlay chance/strength, subliminal
  text chance/opacity/duration, system notification chance/image
  chance, popup opacity, denial chance, moving-popup chance/speed, and
  a per-mood cycle-length override (in seconds, or popup count -
  whichever matches the cycle mode picked on Page 2). Leaving a numeric
  field blank, or leaving an on/off switch on its "(inherit)" state,
  means "keep whatever the previous mood had" - it does not reset to a
  default; click an on/off switch to cycle inherit -> ON -> OFF ->
  inherit. This is also where Presets and the Page 2 Apply buttons
  (spiral/denial/cycle length) write their values, so after using any
  of those you'll see real numbers already filled in here, ready to
  hand-tune.

  **Two different "subliminal" features, easy to mix up:** Edgeware++
  has a hypno/spiral picture overlay (config keys `subliminalsChance` /
  `subliminalsAlpha`, labeled here as "Hypno overlay chance/strength")
  *and*, separately, subliminal caption text - the actual "Subliminal
  messages" you type in per mood (config keys `capPopChance` /
  `capPopOpacity` / `capPopTimer`, labeled here as "Subliminal text
  chance/opacity/duration"). The names are backwards from what you'd
  guess - `subliminalsChance` is the *picture* overlay, not the text.
  Use the "Hypno overlay" fields to ramp the spiral picture, and the
  "Subliminal text" fields to ramp how often/how visible/how long your
  actual subliminal message text shows up. Escalating the wrong pair is
  a real trap: the pack will build and run fine, it'll just be ramping
  something other than what you intended, silently.

**Hover over anything** for a plain-language explanation.

**One setting you have to turn on yourself:** everything in a mood's
Advanced Settings (and anything a Preset or Page 2 Apply button writes
into it) is delivered to Edgeware++ as per-level `config` overrides in
`corruption.json`. Those overrides only take effect if **"Allow full
corruption permissions" (`corruptionFullPerm`)** is turned on in
Edgeware's own Configure window - this can't be turned on by the pack
itself, only by whoever runs it, and it has to be done (and saved)
before launching. Without it, moods will still add and remove on
schedule, but every escalation - popup speed, hypno overlay, subliminal
text, denial chance, all of it - will stay flat at whatever the base
config already has, and the pack will look static despite being built
correctly. A reminder about this is now also shown in the "Pack
built!" dialog after every build.

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
- `<PackName>_build.log`, also right inside that folder - the full
  compiler output for this build, every time, not just when something
  looks off.

A progress bar runs while this happens (compiling can take a while on
larger packs). It's an indeterminate spinner, not a percentage - the
Pack Tool compiler doesn't report incremental progress, so a real
percentage isn't available to show.

After a successful build, you'll be asked whether to delete the
temporary working files (`pack_source/`, `pack_build/`, and - if this
pack was loaded from a `.zip` - the original extracted copy in
`loaded_packs/`), since everything in them is already inside the
finished zip at that point.

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

- Do the four presets feel right in-game? Numbers are easy to adjust
  once you've seen them play out.
- Do the Pack-Wide Settings (Hibernate/Mitosis mode especially) behave
  as expected? These haven't been tested in-game yet from this tool.
- Does loading a pack with no `plan.json` produce a reasonable
  reconstruction? What's in the warning banner, if anything?
- Does the Media Review page correctly reflect what's actually in a
  pack you load, and does removing a file there actually keep it out of
  the rebuilt pack?
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
  that wallpaper on the Media Review page.
- Video thumbnails on the Media Review page are a plain icon, not an
  actual frame from the file - getting a real preview frame would mean
  adding a video-processing dependency just for that, which didn't seem
  worth it for a preview thumbnail.
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
