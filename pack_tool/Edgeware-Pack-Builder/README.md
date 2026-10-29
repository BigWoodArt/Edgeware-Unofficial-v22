# Edgeware++ Advanced Pack Builder

GUI for building Edgeware++ packs from a folder of mood subfolders - no hand-written JSON/YAML.

## Setup

Python 3.10+ (Windows, "Add to PATH" checked). Double-click `run.bat` - installs what's needed on first run, then launches the app. Launching `edgeware_pack_builder_gui.pyw` directly works too; it offers to install anything missing. The Pack Tool is bundled in `pack_tool/` and used automatically - keep that folder next to the program. `banner.png` must stay next to the script.

## Pages

**1 - Source & Pack Tool:** folder of mood subfolders (first = starting mood) (the bundled Pack Tool is used automatically for one-click `.zip` builds). **Load Existing Pack** (folder/zip) reopens one for editing.

**2 - Whole-Experience:** 4 **Presets** (Slight Annoyance → Life-Ending Slavery) spread full intensity curves across all moods, editable after; also set hypno overlay chance/strength (max 20%) and popup opacity (100%). Pack info. **Mood Cycling** (seconds or popup-count) + optional per-mood ramp. **Pack-Wide Settings** (Corruption/Hibernate/Mitosis mode, Level Transition, Buttonless, button text). **Escalating Spirals/Denial** with Apply. Hypno/wallpaper/splash/Discord-status extras.

**3 - Media Review:** per-mood Images/Videos/Audio (add/remove, non-destructive) + Wallpaper picker. Unopened moods use source folder as-is.

**4 - Per-Mood:** Captions/Notifications/Subliminal/Prompts/Denial/Website text (one per line; website supports `| arg1, arg2`). "Remove these moods" (earlier moods only). **Advanced Settings**: speed, popup-type odds, volume/concurrency, hypno & subliminal-text chance/strength, notifications, denial, movement, cycle override - blank/"(inherit)" = keep previous mood's value.

⚠️ **Hypno overlay** (`subliminalsChance/Alpha`) ≠ **subliminal text** (`capPopChance/Opacity/Timer`) - names are swapped from what you'd expect.

⚠️ **`capPopTimer`** (subliminal text duration) is raw **milliseconds**, not seconds.

⚠️ **`corruptionFullPerm`** must be enabled in Edgeware's own config, or escalation stays flat regardless of what the pack sets.

Hover for tooltips. Back never loses data.

## Building

One folder → `pack_source/`, `pack_build/`, `<Name>.zip` (includes `plan.json`), `<Name>_build.log`. Indeterminate progress bar. Offers cleanup after success.

Folder-loaded packs get **Save Changes to Pack** instead - saves in place, timestamped backup, purple accent while active.

## Loading

`plan.json` present → exact reload. Absent → offers best-effort reconstruction from the pack's own JSON files (unparseable bits skipped + reported, not silent).

## Updating

When a newer version exists, the app offers **Update now**: it downloads the latest files, keeps your loaded packs, and restarts. Git checkouts update with `git pull` instead. If an update fails, nothing is changed.

## Limitations

Video compression uses `pyffmpeg`, which may download ffmpeg on first use (needs internet). If the build fails with it on, turn it off - everything else still works. Zips extract to `loaded_packs/` (not temp) for path stability. Missing wallpaper → build stops with a clear error. Video thumbnails are placeholder icons. No dangerous settings (fill/panic-disable) by design. webp black-square is a known Edgeware++ bug. Reconstruction is unverified against a real compiled pack.

## To test

Presets in-game feel, Hibernate/Mitosis behavior, reconstruction quality, Media Review removals sticking, any wrong tooltip or error dialog.

## Version History

One short line per entry.

- **v1.0.8 (current)** - Removed the Pack Tool Browse button; the bundled tool is always used.
- **v1.0.7** - Old projects with a stale Pack Tool path now use the bundled one; harmless compiler warnings hidden.
- **v1.0.6** - One-click update from inside the app; settings kept, old files backed up to `_update_backup/`.
- **v1.0.5** - App offers to install missing packages itself on startup.
- **v1.0.4** - Pack Tool bundled; `run.bat` installs all dependencies on first run.
- **v1.0.3** - Settings saved to untracked `user_settings.json` (old file migrates); dependency minimums; zip attached to releases.
- **v1.0.2** - Added MIT license; fixed `.gitignore` filename.
- **v1.0.1** - Pack Tool search now looks up to 3 folders up/down from your selection.
- **v1.0.0** - Cleanup release: removed dead code and comment bloat. Presets now set hypno overlay chance/strength (max 20%) and popup opacity (100%).
- **v0.17.2** - Taskbar icon fix (own AppUserModelID); script renamed `.pyw`; `crash_log.txt` for startup errors.
- **v0.17.1** - Real multi-resolution `.ico`; `run.bat` runs windowless.
- **v0.17** - M4A misdetected as video is auto-moved; harmless compiler warning suppressed; settings-only load prompt; custom icon.
- **v0.16** - Fixed garbled quotes (pack.yml written as ASCII); post-build media check; Discord status and button text; File menu; update check.
- **v0.15** - Pre-mood legacy packs reconstruct into one "Everything" mood; wallpaper path fix.
- **v0.14** - Create New Pack steps up a folder if needed; redirects compiled packs to Load.
- **v0.13** - Page 1 relabeled.
- **v0.12.2** - Fixed crash on plain-string `web` entries; Page 3 hardened.
- **v0.12.1** - Fixed reconstruction finding no images.
- **v0.12** - Save Changes to Pack (in place, backup, purple accent).
- **v0.11** - Pack Tool folder display fix; collapsible audio.
- **v0.10.1** - Fixed crash on late background loads; `X.Y.Z` versioning.
- **v0.10** - `config.json` baseline includes Corruption Level 1.
- **v0.9** - Fixed `capPopTimer` units (ms); sturdier loading; `plan.json` strips local paths.
- **v0.8** - Media Review page; Wallpaper moved there.
- **v0.7** - Level Transition + Buttonless toggles.
- **v0.6** - Per-Mood mood-tab sidebar, thumbnails, background loading.
- **v0.5** - New preset tiers; Pack-Wide Settings.
- **v0.4** - Fixed corruption levels not triggering (int rounding).
- **v0.3** - Fixed subliminal-text/hypno-overlay key mixup; build log.
- **v0.2** - Fixed popup-count cycling typo; documented `corruptionFullPerm`.
- **v0.1** - Initial release.

## License

MIT - see `LICENSE`. The bundled `pack_tool/` is unmodified Edgeware++ code under GPLv3 - see `pack_tool/COPYING`.
