# Copyright (C) 2024 Araten & Marigold
#
# This file is part of Edgeware++.
#
# Edgeware++ is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Edgeware++ is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Edgeware++.  If not, see <https://www.gnu.org/licenses/>.

"""Optional full-screen spiral overlay, one persistent window per enabled
monitor, whose opacity scales linearly with the pack's own hypno/spiral
overlay chance (settings.hypno_chance - the same value that drives the
per-image hypno overlay in image_popup.py): 0% chance -> 0% opacity, 100%
chance -> 50% opacity, capped there deliberately so it can never fully
obscure whatever else is on screen.

This is a persistent ambient layer, not a one-shot popup like everything in
RollTarget - it's created once at startup (if enabled) and stays up for the
whole session, the same way wallpaper rotation is ambient rather than a
discrete roll. It re-lifts itself periodically for the same reason the
subliminal popup now does: any newer topmost popup would otherwise steal the
top of the stacking order and bury it.

hypno_chance is one of the settings corruption levels can escalate over the
course of a session (confirmed directly against a real pack's corruption.json
- 0% -> 25% -> 50% across three levels), so the target opacity this drives
is not fixed for the whole session. The same re-lift tick also re-reads
hypno_chance and eases the actual displayed opacity toward wherever it
currently points, a small step at a time, rather than jumping straight
there - a sudden jump would be a jarring, obvious "something just changed"
tell, working against corruption's own escalate-gradually design.
"""

import logging
from tkinter import TclError, Tk, Toplevel

import os_utils
import utils
from config.settings import Settings
from features.video_player import VideoPlayer
from pack import Pack
from paths import Assets
from screeninfo import Monitor

# Keys match the "spiralOverlayAsset" choices in config/items.py.
SPIRAL_ASSETS = {
    "Classic": Assets.SPIRAL_CLASSIC,
    "Two-Arm Taper": Assets.SPIRAL_TWO_ARM_TAPER,
    "One-Arm Taper": Assets.SPIRAL_ONE_ARM_TAPER,
}

RELIFT_INTERVAL_MS = 250
# Deliberately not user-configurable independent of hypno_chance - see the
# module docstring. 50% is the ceiling regardless of how high hypno_chance
# goes, so this can never fully hide what's underneath it.
MAX_OPACITY = 0.5
# Max opacity change per re-lift tick. At the 250ms tick rate above, this is
# a 4%-of-full-range change per second - a full 0%-to-50% swing takes about
# 12.5 seconds. Fast enough to feel responsive to a corruption level change,
# slow enough to read as a fade rather than a jump cut.
OPACITY_STEP_PER_TICK = 0.01


def spiral_overlay_opacity(settings: Settings) -> float:
    return (settings.hypno_chance / 100) * MAX_OPACITY


def resolve_spiral_asset(settings: Settings, pack: Pack) -> str:
    if settings.spiral_overlay_asset == "Pack's Own":
        return str(pack.random_hypno())  # Guaranteed non-empty - see Pack.random_hypno
    path = SPIRAL_ASSETS.get(settings.spiral_overlay_asset, Assets.SPIRAL_CLASSIC)
    return str(path)


class SpiralOverlay(Toplevel):
    def __init__(self, settings: Settings, monitor: Monitor, asset: str) -> None:
        super().__init__()
        self.settings = settings
        # Starts whatever hypno_chance already computes to right now (often
        # 0%, i.e. invisible, if corruption hasn't escalated yet) rather than
        # skipping window creation entirely at 0% - the window has to already
        # exist for the opacity to ease upward later as corruption raises
        # hypno_chance; there's no later moment this re-checks and decides to
        # create it after all.
        self.current_opacity = spiral_overlay_opacity(settings)

        os_utils.set_borderless(self)
        self.attributes("-topmost", True)
        self.attributes("-alpha", self.current_opacity)
        self.geometry(f"{monitor.width}x{monitor.height}+{monitor.x}+{monitor.y}")

        self.player = VideoPlayer(self, settings, monitor.width, monitor.height)
        # Same technique already used for the per-image hypno overlay in
        # image_popup.py: mpv normally letterboxes to preserve the source's
        # aspect ratio within the given window, which would leave black bars
        # on a square-ish spiral GIF inside a 16:9 (or any non-square)
        # monitor. These ratios are the multiplier needed to stretch past
        # that letterboxing and fill the window completely instead.
        self.player.properties["video-scale-x"] = max(monitor.width / monitor.height, 1)
        self.player.properties["video-scale-y"] = max(monitor.height / monitor.width, 1)
        # A source spiral this small stretched several times over would look
        # blocky with mpv's own fallback scaler - ewa_lanczossharp is what
        # keeps a simple, mostly-gradient pattern like this looking smooth at
        # a large blow-up instead of pixelated. Not applied anywhere else in
        # the codebase since nothing else stretches this far past its source
        # resolution.
        self.player.properties["scale"] = "ewa_lanczossharp"
        self.player.properties["dscale"] = "ewa_lanczossharp"
        self.player.play(asset)

        # Applied last, after geometry/player - deliberately mirroring
        # features/popup.py's Popup.try_clickthrough(), which does the same
        # thing for the exact same reason: setting this Windows-level "let
        # clicks pass through" flag before the window is actually mapped by
        # the OS can silently fail to take effect, leaving an ordinary
        # (click-blocking) topmost window instead - which, for a persistent
        # full-screen window like this one, would mean it eats every click
        # meant for a real popup underneath it. update_idletasks() forces
        # any pending geometry/mapping to process immediately, without
        # entering a nested event loop the way wait_visibility() does - that
        # was tried first, but confirmed directly (a real crash report) to
        # be able to throw if the window gets destroyed while still waiting,
        # and to leave the wider event queue in a bad state afterward even
        # when the exception itself was caught. This has the same practical
        # effect for this one-time-per-monitor call without that risk.
        self.update_idletasks()
        os_utils.set_clickthrough(self)

        self._tick()

    def _tick(self) -> None:
        try:
            self.attributes("-topmost", False)
            self.attributes("-topmost", True)
            self.lift()
            self._ease_opacity()
        except TclError:
            return  # Already destroyed
        self.after(RELIFT_INTERVAL_MS, self._tick)

    def _ease_opacity(self) -> None:
        target = spiral_overlay_opacity(self.settings)
        gap = target - self.current_opacity
        if abs(gap) <= OPACITY_STEP_PER_TICK:
            self.current_opacity = target  # Close enough - snap the rest of the way, avoids an endless tiny-step tail
        else:
            self.current_opacity += OPACITY_STEP_PER_TICK if gap > 0 else -OPACITY_STEP_PER_TICK
        self.attributes("-alpha", self.current_opacity)

    def close(self) -> None:
        try:
            self.player.close()
        except Exception:
            pass
        try:
            self.destroy()
        except TclError:
            pass


def handle_spiral_overlay(root: Tk, settings: Settings, pack: Pack) -> list[SpiralOverlay]:  # noqa: ARG001 - root kept for signature symmetry with the other safe_step-wrapped handlers in main_edgeware.py
    """Called once at startup, alongside the rest of start_main()'s
    independent feature setup - see the safe_step() wrapping in
    main_edgeware.py, so a failure here (e.g. no monitors detected, or a bad
    asset path) can't take anything else down. Returns the list of windows
    created (empty if disabled, or no enabled monitors exist) so the caller
    could tear them down later if this ever needs a "toggle off mid-session"
    control; nothing currently does, since every other Edgeware toggle is
    also "takes effect on next launch," not live-editable mid-session.
    """
    if not settings.spiral_overlay_enabled:
        return []

    asset = resolve_spiral_asset(settings, pack)
    monitors = utils.enabled_monitors(settings)
    if not monitors:
        logging.warning("Spiral overlay enabled, but no enabled monitors were found - skipping.")
        return []

    overlays = [SpiralOverlay(settings, monitor, asset) for monitor in monitors]
    logging.info(
        f'Spiral overlay started on {len(overlays)} monitor(s), starting at {spiral_overlay_opacity(settings):.0%} opacity (tracks hypno chance live as it changes), using "{settings.spiral_overlay_asset}".'
    )
    return overlays
