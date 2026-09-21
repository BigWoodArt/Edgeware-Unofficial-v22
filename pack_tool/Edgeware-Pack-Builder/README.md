# Edgeware++ Advanced Pack Builder

GUI for building Edgeware++ packs from a folder of mood subfolders - no hand-written JSON/YAML.

## Setup

Python 3.10+ (Windows, "Add to PATH" checked). Double-click `run.bat` - auto-installs `pyyaml` + `pillow`, launches app. `banner.png` must stay next to the script. Pack Tool folder auto-detects if placed inside/next to it; otherwise remembered after first manual set.

## Pages

**1 - Source & Pack Tool:** folder of mood subfolders (first = starting mood) + optional Pack Tool folder (enables one-click `.zip` build). **Load Existing Pack** (folder/zip) reopens one for editing.

**2 - Whole-Experience:** 4 **Presets** (Slight Annoyance → Life-Ending Slavery) spread full intensity curves across all moods, editable after; doesn't touch hypno overlay. Pack info. **Mood Cycling** (seconds or popup-count) + optional per-mood ramp. **Pack-Wide Settings** (Corruption/Hibernate/Mitosis mode, Level Transition, Buttonless). **Escalating Spirals/Denial** with Apply. Hypno/wallpaper/splash extras.

**3 - Media Review:** per-mood Images/Videos/Audio (add/remove, non-destructive) + Wallpaper picker. Unopened moods use source folder as-is.

**4 - Per-Mood:** Captions/Notifications/Subliminal/Prompts/Denial/Website text (one per line; website supports `| arg1, arg2`). "Remove these moods" (earlier moods only). **Advanced Settings**: speed, popup-type odds, volume/concurrency, hypno & subliminal-text chance/strength, notifications, denial, movement, cycle override - blank/"(inherit)" = keep previous mood's value.

⚠️ **Hypno overlay** (`subliminalsChance/Alpha`) ≠ **subliminal text** (`capPopChance/Opacity/Timer`) - names are swapped from what you'd expect.

⚠️ **`corruptionFullPerm`** must be enabled in Edgeware's own config, or escalation stays flat regardless of what the pack sets.

Hover for tooltips. Back never loses data.

## Building

One folder → `pack_source/`, `pack_build/`, `<Name>.zip` (includes `plan.json`), `<Name>_build.log`. Indeterminate progress bar. Offers cleanup after success.

Folder-loaded packs get **Save Changes to Pack** instead - saves in place, timestamped backup, purple accent while active.

## Loading

`plan.json` present → exact reload. Absent → offers best-effort reconstruction from the pack's own JSON files (unparseable bits skipped + reported, not silent).

## Limitations

Zips extract to `loaded_packs/` (not temp) for path stability. Missing wallpaper → build stops with a clear error. Video thumbnails are placeholder icons. No dangerous settings (fill/panic-disable) by design. webp black-square is a known Edgeware++ bug. Reconstruction is unverified against a real compiled pack.

## To test

Presets in-game feel, Hibernate/Mitosis behavior, reconstruction quality, Media Review removals sticking, any wrong tooltip or error dialog.

## Version History

- **v0.15 (current)** - Packs with no per-mood structure at all (pre-moods legacy Edgeware format - flat img/aud/vid, un-mood-tagged captions/prompt/web.json) now reconstruct into one "Everything" mood instead of loading empty; also fixed wallpapers being looked for in a wallpapers/ subfolder that doesn't actually exist in real compiled packs.
- **v0.14** - Create New Pack now steps up a folder level if the selected one has no subfolders, and redirects to Load Existing Pack if it looks like an already-compiled pack instead.
- **v0.13** - Page 1 relabeled for clarity: "Where is the folder of images?" → "Create New Pack", with a new "Load Existing Pack" header above the folder/zip buttons.
- **v0.12.2** - Fixed a crash when a mood's `web` entries were plain strings instead of dicts (now normalized); Page 3 also hardened so one mood's build failure can't break the whole page anymore.
- **v0.12.1** - Fixed reconstruction (packs with no `plan.json`) finding zero images for every mood - it only ever tried grouping media via `media.json`'s guessed/unverified shape; now uses `index.json`'s own per-mood media list instead.
- **v0.12** - Save Changes to Pack: in-place save for folder-loaded packs, timestamped backup, purple accent.
- **v0.11** - Fixed Pack Tool folder showing selected-but-blank after load. Audio section now collapsible.
- **v0.10.1** - Fixed crash from background loads finishing after page teardown. Versioning now `X.Y.Z`.
- **v0.10** - `config.json` baseline includes Corruption Level 1 values.
- **v0.9** - Fixed `capPopTimer` unit bug (ms not seconds). More resilient loading. `plan.json` strips local paths.
- **v0.8** - Added Media Review page; Wallpaper moved there.
- **v0.7** - Added Level Transition + Buttonless toggles; fixed unresponsive toggles.
- **v0.6** - Per-Mood redesigned with mood-tab sidebar + thumbnails; background loading.
- **v0.5** - New preset tiers, wider coverage; added Pack-Wide Settings panel.
- **v0.4** - Fixed corruption levels not triggering (values now rounded to int).
- **v0.3** - Fixed subliminal-text/hypno-overlay key mixup; added build log.
- **v0.2** - Fixed popup-count cycling typo; documented `corruptionFullPerm`; stale-file fix.
- **v0.1** - Initial release.
