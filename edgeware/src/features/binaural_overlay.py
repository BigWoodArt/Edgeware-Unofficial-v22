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

"""Optional ambient binaural beat layer, paired with the full-screen spiral
overlay (features/spiral_overlay.py) - same idea applied to sound instead of
sight, and deliberately riding the same spiralOverlayEnabled toggle rather
than a second on/off switch: this was asked for as an addition *to* the
spiral overlay, not a separate feature to manage.

Reacts to the same kind of session state as the spiral overlay, blended into
a single 0-1 "intensity" score from three signals:
  - hypno_chance (settings.hypno_chance) - same value driving spiral opacity
  - subliminal message frequency (settings.subliminal_chance)
  - popup speed (settings.delay, inverted - a shorter delay is a more intense
    session)
Intensity then maps to two things, both deliberately narrow-ranged:
  - beat frequency: 12Hz down to 4Hz as intensity rises (calm -> deep)
  - volume: 15%-35% of pyglet's 0-1 range, regardless of the user's own
    audioVolume setting - a hard ceiling, not just a default, specifically so
    this can never be loud even if someone's overall audio volume is maxed.
No live synthesis (see the design discussion this came out of): instead, 10
pre-generated loops spanning that frequency range live in
assets/binaural/, and playback crossfades from whichever is currently
playing to the nearest match as the target frequency drifts, reusing the
same "ease, don't jump" philosophy as the spiral overlay's opacity.
"""

import logging
from tkinter import Tk

import pyglet
from config.settings import Settings
from pack import Pack
from paths import Assets

CHECK_INTERVAL_MS = 2000  # Audio drift doesn't need anywhere near the spiral overlay's 250ms responsiveness - a crossfade takes several seconds anyway.
VOLUME_STEP_PER_CHECK = 0.01  # Eased the same way spiral opacity is - a full swing across the whole 0.15-0.35 range takes about 40 seconds, gentle rather than noticeable.
CROSSFADE_MS = 4000

MIN_BEAT_HZ = 4.0
MAX_BEAT_HZ = 12.0
MIN_VOLUME = 0.15
MAX_VOLUME = 0.35  # Hard ceiling - see module docstring. Never touches settings.audio_volume.

# Popup delay (ms) considered "calm" and "as fast as this scales to" for the
# speed component of intensity - matches the default config's own delay
# (calm end) and the kind of fast pace seen in a real pack's high corruption
# level config (BiConvertWare's level 3: 700ms) at the intense end.
DELAY_CALM_MS = 5000
DELAY_INTENSE_MS = 500


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def compute_intensity(settings: Settings) -> float:
    hypno_component = settings.hypno_chance / 100
    subliminal_component = settings.subliminal_chance / 100
    speed_component = _clamp01((DELAY_CALM_MS - settings.delay) / (DELAY_CALM_MS - DELAY_INTENSE_MS))
    intensity = 0.4 * hypno_component + 0.3 * subliminal_component + 0.3 * speed_component
    return _clamp01(intensity)


def target_beat_hz(intensity: float) -> float:
    return MAX_BEAT_HZ - intensity * (MAX_BEAT_HZ - MIN_BEAT_HZ)


def target_volume(intensity: float) -> float:
    return MIN_VOLUME + intensity * (MAX_VOLUME - MIN_VOLUME)


def nearest_variation_index(beat_hz: float) -> int:
    # Assets.BINAURAL_VARIATIONS is ordered ascending by beat frequency
    # (index 0 = 4.0Hz/deep, last index = 12.0Hz/calm) - matches how the
    # generation grid actually built the files, so this maps directly with
    # no inversion.
    n = len(Assets.BINAURAL_VARIATIONS)
    frac = _clamp01((beat_hz - MIN_BEAT_HZ) / (MAX_BEAT_HZ - MIN_BEAT_HZ))
    return round(frac * (n - 1))


class BinauralOverlay:
    def __init__(self, root: Tk, settings: Settings) -> None:
        self.root = root
        self.settings = settings
        self.current_volume = 0.0
        self.current_index: int | None = None
        self.player: pyglet.media.Player | None = None
        self._tick()

    def _play_variation(self, index: int) -> None:
        old_player = self.player
        new_player = pyglet.media.Player()
        new_player.queue(pyglet.media.load(str(Assets.BINAURAL_VARIATIONS[index]), streaming=True))
        new_player.loop = True
        new_player.volume = 0
        new_player.play()
        self.player = new_player
        self.current_index = index

        self._fade(new_player, self.current_volume, CROSSFADE_MS)
        if old_player:
            self._fade(old_player, 0, CROSSFADE_MS, then=old_player.pause)

    def _fade(self, player: pyglet.media.Player, target: float, duration_ms: int, then=None) -> None:
        # Deliberately separate from features/audio.py's fade_in/fade_out -
        # those fade toward settings.audio_volume (the user's own volume
        # slider), which would blow straight past this feature's hard
        # 15%-35% comfort ceiling if reused as-is. This always fades toward
        # a caller-given target instead.
        steps = max(1, duration_ms // 50)
        delta = (target - player.volume) / steps

        def step(remaining: int) -> None:
            try:
                player.volume = target if remaining <= 1 else player.volume + delta
            except Exception:
                return  # Player already gone
            if remaining <= 1:
                if then:
                    then()
                return
            self.root.after(50, lambda: step(remaining - 1))

        step(steps)

    def _tick(self) -> None:
        intensity = compute_intensity(self.settings)
        beat_hz = target_beat_hz(intensity)
        wanted_index = nearest_variation_index(beat_hz)
        wanted_volume = target_volume(intensity)

        if self.current_index is None:
            self._play_variation(wanted_index)
        elif wanted_index != self.current_index:
            self._play_variation(wanted_index)

        gap = wanted_volume - self.current_volume
        if abs(gap) <= VOLUME_STEP_PER_CHECK:
            self.current_volume = wanted_volume
        else:
            self.current_volume += VOLUME_STEP_PER_CHECK if gap > 0 else -VOLUME_STEP_PER_CHECK
        if self.player and self.current_index == wanted_index:
            # Only drive volume directly here once the crossfade for a
            # variation change has had time to finish - otherwise this would
            # fight with the crossfade's own fade-in for the same player.
            self.player.volume = self.current_volume

        self.root.after(CHECK_INTERVAL_MS, self._tick)

    def close(self) -> None:
        if self.player:
            try:
                self.player.pause()
            except Exception:
                pass


def handle_binaural_overlay(root: Tk, settings: Settings, pack: Pack) -> BinauralOverlay | None:
    """Called once at startup alongside handle_spiral_overlay - see that
    function and the safe_step() wrapping in main_edgeware.py. Shares
    spiralOverlayEnabled rather than having its own toggle; see this
    module's docstring for why.
    """
    if not settings.spiral_overlay_enabled:
        return None
    overlay = BinauralOverlay(root, settings)
    logging.info("Binaural overlay started, tracking hypno chance/subliminal frequency/popup speed live.")
    return overlay
