#!/usr/bin/env python3
"""
Edgeware++ Advanced Pack Builder
----------------------------------
A single-program pack builder with a full Mood Settings system, hover
tooltips, and load/resume support.

Three pages:
  1. Source folder + mood scan + Pack Tool location (auto-detected next
     to this script if possible, otherwise remembered from last time via
     builder_settings.json) + Load an existing pack.
  2. Whole-experience settings: pack info, mood cycling, escalating
     spirals, pack-wide extras (hypno overlays, default wallpaper,
     loading splash image), build options.
  3. Per-mood settings: collapsible cards (captions, notifications,
     wallpaper trigger, audio files, which earlier moods to remove when
     this one starts, and an Advanced Settings panel of real Edgeware++
     config knobs). Every mood - including the first - gets its own
     corruption level; nothing relies on Edgeware's reserved "default"
     mood, since testing showed that mood's content doesn't reliably
     display even when nominally active.

Data entered anywhere is kept in a PackPlan the moment you navigate away
from a page (Back included), and every build also writes a plan.json
snapshot next to pack.yml. Loading that plan.json back is exact. Loading
a pack that has no plan.json (anything not built by this tool) falls
back to reconstructing settings from the compiled pack's own info.json/
index.json/media.json/corruption.json/config.json - best-effort, since
I haven't been able to verify the exact compiled JSON schema against a
real pack yet, flagged clearly in the UI when that path is used.

Build Pack runs the actual compile + zip on a background thread with an
indeterminate progress bar, since the Pack Tool compiler doesn't report
real progress and the UI would otherwise freeze for however long it
takes.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import threading
import zipfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
import tkinter as tk
from tkinter import StringVar, IntVar, BooleanVar, filedialog, messagebox
from tkinter import ttk

try:
    import yaml  # pyyaml
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False

SCRIPT_DIR = Path(__file__).resolve().parent
BANNER_PATH = SCRIPT_DIR / "banner.png"
SETTINGS_PATH = SCRIPT_DIR / "builder_settings.json"

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------

BG = "#1f1224"
PANEL_BG = "#2c1830"
ACCENT = "#a3123a"
ACCENT_ACTIVE = "#c81a49"
ENTRY_BG = "#3a2140"
TEXT_FG = "#ffffff"
MUTED_FG = "#d9b8c9"
WARN_BG = "#4a2f10"
WARN_FG = "#ffd9a0"


def apply_theme(root: tk.Tk):
    root.configure(bg=BG)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", background=BG, foreground=TEXT_FG, fieldbackground=ENTRY_BG,
                     bordercolor=ACCENT, lightcolor=BG, darkcolor=BG)
    style.configure("TFrame", background=BG)
    style.configure("Panel.TFrame", background=PANEL_BG)
    style.configure("TLabel", background=BG, foreground=TEXT_FG)
    style.configure("Muted.TLabel", background=BG, foreground=MUTED_FG)
    style.configure("Header.TLabel", background=BG, foreground=TEXT_FG, font=("Segoe UI", 14, "bold"))
    style.configure("Warn.TLabel", background=WARN_BG, foreground=WARN_FG)
    style.configure("TLabelframe", background=BG, foreground=TEXT_FG, bordercolor=ACCENT)
    style.configure("TLabelframe.Label", background=BG, foreground="#ffb6cd", font=("Segoe UI", 10, "bold"))
    style.configure("TButton", background=ACCENT, foreground=TEXT_FG, borderwidth=0,
                     focuscolor=ACCENT, padding=6)
    style.map("TButton", background=[("active", ACCENT_ACTIVE), ("disabled", "#5a3a4a")])
    style.configure("TCheckbutton", background=BG, foreground=TEXT_FG)
    style.map("TCheckbutton", background=[("active", BG)], foreground=[("active", TEXT_FG)])
    style.configure("TRadiobutton", background=BG, foreground=TEXT_FG)
    style.map("TRadiobutton", background=[("active", BG)], foreground=[("active", TEXT_FG)])
    style.configure("TEntry", fieldbackground=ENTRY_BG, foreground=TEXT_FG, insertcolor=TEXT_FG)
    style.configure("TSpinbox", fieldbackground=ENTRY_BG, foreground=TEXT_FG, arrowsize=12)
    style.configure("Vertical.TScrollbar", background=ACCENT, troughcolor=BG, arrowcolor=TEXT_FG,
                     bordercolor=BG)
    style.map("Vertical.TScrollbar", background=[("active", ACCENT_ACTIVE)])
    style.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=ENTRY_BG,
                     bordercolor=BG, lightcolor=ACCENT, darkcolor=ACCENT)


def style_text_widget(widget: tk.Text):
    widget.configure(bg=ENTRY_BG, fg=TEXT_FG, insertbackground=TEXT_FG,
                      relief="flat", highlightthickness=1,
                      highlightbackground=ACCENT, highlightcolor=ACCENT_ACTIVE)


# ---------------------------------------------------------------------------
# Persisted settings (remembers the Pack Tool folder across runs)
# ---------------------------------------------------------------------------

def load_settings() -> dict:
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(d: dict) -> None:
    try:
        SETTINGS_PATH.write_text(json.dumps(d, indent=2), encoding="utf-8")
    except Exception:
        pass  # best-effort - not worth bothering the user about


def find_pack_tool_dir() -> str:
    """Look for src/main.py next to this script, or one level up (covers
    both 'this script sits inside the Pack Tool folder' and 'this script
    sits in a subfolder of the Pack Tool folder')."""
    for candidate in (SCRIPT_DIR, SCRIPT_DIR.parent):
        if (candidate / "src" / "main.py").is_file():
            return str(candidate)
    return ""


# ---------------------------------------------------------------------------
# Tooltip helper
# ---------------------------------------------------------------------------

class Tooltip:
    """Attach a simple hover tooltip to any tkinter/ttk widget."""

    def __init__(self, widget, text, delay=450):
        self.widget = widget
        self.text = text
        self.delay = delay
        self._after_id = None
        self._tip_window = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, event=None):
        self._after_id = self.widget.after(self.delay, self._show)

    def _show(self):
        if self._tip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 15
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8

        self._tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        try:
            tw.attributes("-topmost", True)
        except tk.TclError:
            pass

        label = tk.Label(
            tw, text=self.text, justify="left",
            background=ENTRY_BG, foreground=TEXT_FG,
            relief="solid", borderwidth=1,
            wraplength=260, padx=8, pady=5,
            font=("Segoe UI", 9)
        )
        label.pack()

    def _hide(self, event=None):
        if self._after_id:
            self.widget.after_cancel(self._after_id)
            self._after_id = None
        if self._tip_window:
            self._tip_window.destroy()
            self._tip_window = None


def tip(widget, text):
    Tooltip(widget, text)
    return widget


TOOLTIPS = {
    "source_folder": "Pick the folder that has one folder inside it for each mood.",
    "pack_tool_folder": "Pick the folder on your computer where the Pack Tool lives (it has a 'src' folder inside it). This lets the Build button finish everything for you.",
    "load_pack": "Open a pack you've already built to keep editing it - either a folder or a .zip.",
    "pack_name": "The name people will see for this pack.",
    "pack_id": "A short one-word nickname for this pack, no spaces. Used behind the scenes.",
    "pack_creator": "Your name, or whatever name you want credit under.",
    "pack_version": "A version number, like 1.0. Bump it up if you make changes later.",
    "pack_description": "A sentence or two describing what this pack is.",
    "cycle_timer": "Switch to the next mood after a certain number of minutes go by.",
    "cycle_seconds": "How many seconds to wait before switching to the next mood.",
    "cycle_apply": "Spreads a cycle-length value evenly across all your moods and writes it into each mood's Advanced Settings on the next page, so early moods and late moods can last different amounts of time.",
    "spiral_apply": "Spreads the spiral chance evenly across all your moods and writes it into each mood's Advanced Settings on the next page, so you can see and fine-tune the exact number for each one.",
    "denial_start": "How often the 'not yet!' denial message shows up at the very start.",
    "denial_end": "How often the denial message shows up by the last mood.",
    "denial_apply": "Spreads the denial chance evenly across all your moods and writes it into each mood's Advanced Settings on the next page.",
    "preset_button": "Fills in Advanced Settings for every mood at once with a ready-made pacing curve, from mild to intense. You can still fine-tune individual moods afterward.",
    "cycle_popups": "Switch to the next mood after a certain number of popups have shown up, instead of waiting on a timer.",
    "popups_per_mood": "How many popups need to show up before switching to the next mood.",
    "escalate_spirals": "Turn this on to make spiral pictures show up more and more often as moods go on.",
    "spiral_start": "How often spirals show up at the very start (0 = never, 100 = almost always).",
    "spiral_end": "How often spirals show up by the last mood.",
    "audio_level": "How often a sound plays for any mood that has 'Audio' turned on.",
    "hypno_add": "Pick the spiral/hypno picture files you want available in this pack.",
    "hypno_clear": "Remove all the spiral/hypno pictures you picked.",
    "default_wallpaper": "Pick the background picture to use when the pack first starts, before anything changes.",
    "default_wallpaper_clear": "Remove the background picture you picked.",
    "loading_splash": "Pick the picture shown on the loading screen when the pack first starts up.",
    "loading_splash_clear": "Remove the loading screen picture you picked.",
    "compress_images": "Shrinks picture file sizes so the finished pack takes up less space.",
    "compress_videos": "Shrinks video file sizes so the finished pack takes up less space.",
    "rename_media": "Renames files so older versions of the program can understand which mood they belong to.",
    "captions_box": "Type little messages here. Press Enter to start a new one - each line becomes its own message.",
    "notif_box": "Type notification messages here, one per line, like a text message popping up.",
    "subliminal_box": "Short messages flashed briefly on screen, one per line - the classic 'subliminal message' effect.",
    "prompts_box": "Phrases the popup asks you to type back before it'll close, one per line.",
    "denial_box": "Messages shown on 'not yet!' denial overlays, one per line.",
    "web_box": "Websites this mood is allowed to open, one per line. Add extra words after a '|' (comma-separated) to have one picked at random and appended to the address.",
    "wallpaper_checkbox": "Turn this on to change the desktop background picture when this mood starts.",
    "wallpaper_choose": "Pick the picture to use as the background for this mood.",
    "wallpaper_clear": "Remove the background picture you picked for this mood.",
    "audio_checkbox": "Turn this on to let sounds play during this mood.",
    "audio_add": "Pick one or more sound files. If you pick more than one, it'll randomly choose between them.",
    "audio_clear": "Remove all the sound files you picked for this mood.",
    "advanced_toggle": "Click to show or hide extra, more detailed settings for this mood.",
    "advanced_note": "Leave any box below empty to just keep using whatever the last mood had - you don't have to fill in everything.",
    "remove_moods": "Check a mood here to turn its pictures off once this mood starts. Leave everything unchecked and this mood just adds its pictures on top of whatever's already showing.",
    "mood_card_toggle": "Click to show or hide this mood's settings.",
}

ADVANCED_FIELD_GROUPS = [
    ("Pacing", [
        ("delay", "Popup speed (ms)",
         "How fast pictures pop up. A small number means they pop up really fast! Leave empty to keep it the same as before."),
        ("popupMod", "Image chance (%)",
         "How likely a popup will be a picture. Leave empty to keep it the same as before."),
        ("vidMod", "Video chance (%)",
         "How likely a popup will be a little video. Leave empty to keep it the same as before."),
        ("webMod", "Website chance (%)",
         "How likely a popup will open a website. Leave empty to keep it the same as before."),
        ("promptMod", "Prompt chance (%)",
         "How likely a popup will ask you to type something. Leave empty to keep it the same as before."),
        ("corruptionTime", "Cycle length override (sec)",
         "How many seconds THIS mood lasts before switching to the next one. Only matters if 'time delay' cycling is picked on the previous page. Leave empty to use the pack's overall cycle length."),
        ("corruptionPopups", "Cycle length override (popups)",
         "How many popups need to show up before switching away from THIS mood. Only matters if 'N popups' cycling is picked on the previous page. Leave empty to use the pack's overall cycle length."),
    ]),
    ("Audio / Video", [
        ("maxAudio", "Max sounds at once",
         "The most sounds that can play at the exact same time. Leave empty to keep it the same as before."),
        ("audioVolume", "Audio volume (%)",
         "How loud the sounds are. Leave empty to keep it the same as before."),
        ("maxVideos", "Max videos at once",
         "The most videos that can play at the exact same time. Leave empty to keep it the same as before."),
        ("videoVolume", "Video volume (%)",
         "How loud the videos are. Leave empty to keep it the same as before."),
        ("audioMod", "Audio chance (%) - overrides checkbox",
         "How likely a popup plays a sound. Fill this in to fine-tune the simple Audio checkbox above. Leave empty to just use the checkbox."),
    ]),
    ("Effects", [
        ("subliminalsChance", "Spiral chance (%) - overrides ramp-up",
         "How often a spiral picture shows up. Fill this in to override the automatic ramp-up setting above. Leave empty to use the automatic ramp-up."),
        ("subliminalsAlpha", "Spiral strength (%)",
         "How easy it is to see the spiral picture through the popup. Higher means it stands out more. This is different from 'chance' - chance is how OFTEN, this is how STRONG. Leave empty to keep it the same as before."),
        ("denialChance", "Denial message chance (%)",
         "How often a special 'not yet!' message shows up. Leave empty to keep it the same as before."),
        ("movingChance", "Moving popup chance (%)",
         "How often a popup slides around the screen instead of staying still. Leave empty to keep it the same as before."),
        ("movingSpeed", "Moving speed",
         "How fast a popup slides around when it moves. Leave empty to keep it the same as before."),
    ]),
]
ALL_ADVANCED_KEYS = [key for _, fields in ADVANCED_FIELD_GROUPS for key, _, _ in fields]


# ---------------------------------------------------------------------------
# Scrollable frame helper
# ---------------------------------------------------------------------------

class ScrollableFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)

        self._window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas.bind("<Enter>", lambda e: self._bind_mousewheel())
        self.canvas.bind("<Leave>", lambda e: self._unbind_mousewheel())

    def _on_inner_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self._window_id, width=event.width)

    def _bind_mousewheel(self):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel_linux)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel_linux)

    def _unbind_mousewheel(self):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_mousewheel_linux(self, event):
        self.canvas.yview_scroll(-1 if event.num == 4 else 1, "units")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class MoodConfig:
    name: str
    captions: list = field(default_factory=list)
    notifications: list = field(default_factory=list)
    subliminal_messages: list = field(default_factory=list)
    prompts: list = field(default_factory=list)
    denial_captions: list = field(default_factory=list)
    web_entries: list = field(default_factory=list)  # [{"url": "...", "args": ["...", ...]}, ...]
    wallpaper_change: bool = False
    wallpaper_path: str = ""
    audio_enabled: bool = False
    audio_paths: list = field(default_factory=list)
    advanced: dict = field(default_factory=dict)
    remove_moods: list = field(default_factory=list)
    # Explicit file list, used when media isn't sitting in a clean
    # source_dir/<mood_name>/ folder (e.g. after reconstructing a pack
    # from its compiled, flat img/aud/vid layout). Empty = use the normal
    # source_dir/<mood_name>/ convention instead.
    media_files: list = field(default_factory=list)


@dataclass
class PackPlan:
    source_dir: str = ""
    moods: list = field(default_factory=list)

    pack_tool_dir: str = ""
    compress_images: bool = False
    compress_videos: bool = False
    rename_media: bool = False

    pack_name: str = "My Pack"
    pack_id: str = "MyPack"
    pack_creator: str = ""
    pack_version: str = "1.0"
    pack_description: str = ""

    cycle_mode: str = "timer"
    cycle_seconds: int = 300  # how long a mood lasts before advancing (Timed mode)
    popups_per_mood: int = 5

    escalate_spirals: bool = False
    spiral_start_pct: int = 0
    spiral_end_pct: int = 100

    audio_mod_when_on: int = 50

    hypno_paths: list = field(default_factory=list)
    default_wallpaper_path: str = ""
    loading_splash_path: str = ""

    mood_configs: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def scan_moods(root: Path) -> list:
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir())


# ---------------------------------------------------------------------------
# pack.yml generation
# ---------------------------------------------------------------------------

def _lerp(a: int, b: int, t: float) -> int:
    return round(a + (b - a) * t)


def _clean_num(x):
    """Round to 1 decimal place; collapse to a plain int when whole
    (e.g. 4.0 -> 4), so most fields still display as clean integers and
    only ones that actually need a fraction (like the toned-down
    movingSpeed presets) show one."""
    x = round(x, 1)
    return int(x) if float(x).is_integer() else x


def spread_values(n: int, start, end, curve: str = "linear") -> list:
    """Interpolate `n` values from start to end. curve="exp" accelerates
    (squares the progress fraction) rather than moving evenly."""
    if n <= 0:
        return []
    if n == 1:
        return [_clean_num(start)]
    result = []
    for i in range(n):
        t = i / (n - 1)
        if curve == "exp":
            t = t * t
        result.append(_clean_num(start + (end - start) * t))
    return result


# Each preset: knob key -> (start, end, curve). Applied across however many
# moods a pack has via _apply_spread_to_moods. corruptionTime is in seconds.
PRESETS = {
    "A Fun Distraction": {
        "corruptionTime": (450, 450, "linear"),
        "delay": (15000, 8000, "linear"),
        "vidMod": (5, 15, "linear"),
        "webMod": (0, 0, "linear"),
        "promptMod": (0, 5, "linear"),
        "maxAudio": (1, 1, "linear"),
        "maxVideos": (1, 2, "linear"),
        "audioVolume": (50, 60, "linear"),
        "videoVolume": (50, 60, "linear"),
        "movingChance": (0, 5, "linear"),
        "movingSpeed": (0.6, 0.8, "linear"),
        "subliminalsChance": (0, 15, "linear"),
        "subliminalsAlpha": (10, 20, "linear"),
        "denialChance": (0, 5, "linear"),
    },
    "A Slight Annoyance": {
        "corruptionTime": (300, 240, "linear"),
        "delay": (10000, 5000, "linear"),
        "vidMod": (10, 30, "linear"),
        "webMod": (0, 0, "linear"),
        "promptMod": (5, 15, "linear"),
        "maxAudio": (1, 2, "linear"),
        "maxVideos": (2, 4, "linear"),
        "audioVolume": (60, 80, "linear"),
        "videoVolume": (60, 80, "linear"),
        "movingChance": (5, 20, "linear"),
        "movingSpeed": (0.8, 1.2, "linear"),
        "subliminalsChance": (10, 35, "linear"),
        "subliminalsAlpha": (15, 35, "linear"),
        "denialChance": (5, 20, "linear"),
    },
    "A Real Addiction": {
        "corruptionTime": (240, 90, "exp"),
        "delay": (8000, 2500, "exp"),
        "vidMod": (20, 50, "linear"),
        "webMod": (5, 20, "linear"),
        "promptMod": (10, 30, "linear"),
        "maxAudio": (2, 4, "exp"),
        "maxVideos": (3, 7, "exp"),
        "audioVolume": (70, 100, "linear"),
        "videoVolume": (70, 100, "linear"),
        "movingChance": (10, 45, "exp"),
        "movingSpeed": (1.0, 1.8, "linear"),
        "subliminalsChance": (20, 65, "exp"),
        "subliminalsAlpha": (25, 55, "linear"),
        "denialChance": (10, 40, "exp"),
    },
    "Total Enslavement": {
        "corruptionTime": (150, 30, "exp"),
        "delay": (5000, 1000, "exp"),
        "vidMod": (30, 80, "linear"),
        "webMod": (10, 35, "linear"),
        "promptMod": (20, 60, "linear"),
        "maxAudio": (3, 8, "exp"),
        "maxVideos": (5, 15, "exp"),
        "audioVolume": (80, 100, "linear"),
        "videoVolume": (80, 100, "linear"),
        "movingChance": (20, 90, "exp"),
        "movingSpeed": (1.2, 2.4, "linear"),
        "subliminalsChance": (30, 95, "exp"),
        "subliminalsAlpha": (35, 80, "linear"),
        "denialChance": (20, 75, "exp"),
    },
}


def build_corruption_levels(plan: PackPlan) -> list:
    """
    Every mood - including the first one - gets its own explicit corruption
    level that adds it. Nothing is assumed active by default; this matches
    pack.yml's own documented example rather than relying on Edgeware's
    reserved "default" mood, which testing showed doesn't reliably display
    its content even when nominally active.

    Moods ACCUMULATE unless the user explicitly picked moods to remove via
    that mood's "Remove these moods" list.
    """
    n = len(plan.moods)
    levels = []
    for i in range(n):
        mood_name = plan.moods[i]
        mc = plan.mood_configs.get(mood_name, {})
        advanced = dict(mc.get("advanced", {}))

        level = {"add-moods": [mood_name]}
        remove_list = mc.get("remove_moods", [])
        if remove_list:
            level["remove-moods"] = list(remove_list)

        if mc.get("wallpaper_change") and mc.get("wallpaper_path"):
            level["wallpaper"] = Path(mc["wallpaper_path"]).name

        cfg = dict(advanced)

        if "subliminalsChance" not in cfg and plan.escalate_spirals and n > 1:
            t = i / (n - 1)
            cfg["subliminalsChance"] = _lerp(plan.spiral_start_pct, plan.spiral_end_pct, t)

        if "audioMod" not in cfg:
            cfg["audioMod"] = plan.audio_mod_when_on if mc.get("audio_enabled") else 0

        level["config"] = cfg
        levels.append(level)
    return levels


def build_pack_yml_dict(plan: PackPlan) -> dict:
    mood_entries = []
    for name in plan.moods:
        mc = plan.mood_configs.get(name, {})
        entry = {"mood": name}
        if mc.get("captions"):
            entry["captions"] = mc["captions"]
        if mc.get("notifications"):
            entry["notifications"] = mc["notifications"]
        if mc.get("subliminal_messages"):
            entry["subliminal-messages"] = mc["subliminal_messages"]
        if mc.get("prompts"):
            entry["prompts"] = mc["prompts"]
        if mc.get("denial_captions"):
            entry["denial"] = mc["denial_captions"]
        if mc.get("web_entries"):
            entry["web"] = mc["web_entries"]
        mood_entries.append(entry)

    base_raw = {
        "corruptionMode": True,
        "corruptionTrigger": "Timed" if plan.cycle_mode == "timer" else "Popups",
        # NOTE: assumed to be seconds, based on config.pyw offering a
        # seconds-based entry mode for this same setting. Not independently
        # verified beyond that - worth confirming actual cycle timing
        # in-game matches what's set here.
        "corruptionTime": plan.cycle_seconds,
        "corruptionPopups": plan.popups_per_mood,
        "corruptionFullPerm": True,
        "subliminalsChance": plan.spiral_start_pct if plan.escalate_spirals else 0,
        "audioMod": 0,
    }

    return {
        "info": {
            "generate": True,
            "name": plan.pack_name,
            "id": plan.pack_id,
            "creator": plan.pack_creator,
            "version": plan.pack_version,
            "description": plan.pack_description or plan.pack_name,
        },
        "discord": {
            "generate": False,
            "status": "",
        },
        "index": {
            "generate": True,
            "default": {},
            "moods": mood_entries,
        },
        "config": {
            "generate": True,
            "raw": base_raw,
        },
        "corruption": {
            "generate": True,
            "levels": build_corruption_levels(plan),
        },
    }


def _dump_yaml(doc: dict) -> str:
    if HAVE_YAML:
        return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)

    lines = []

    def _scalar(v):
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, str):
            return json.dumps(v)
        return str(v)

    def emit(obj, indent=0):
        pad = "  " * indent
        if isinstance(obj, dict):
            if not obj:
                lines.append(f"{pad}{{}}")
                return
            for k, v in obj.items():
                if isinstance(v, (dict, list)) and v:
                    lines.append(f"{pad}{k}:")
                    emit(v, indent + 1)
                elif isinstance(v, dict):
                    lines.append(f"{pad}{k}: {{}}")
                elif isinstance(v, list):
                    lines.append(f"{pad}{k}: []")
                else:
                    lines.append(f"{pad}{k}: {_scalar(v)}")
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict):
                    lines.append(f"{pad}-")
                    emit(item, indent + 1)
                else:
                    lines.append(f"{pad}- {_scalar(item)}")

    emit(doc)
    return "\n".join(lines) + "\n"


def _unique_copy(src: Path, dst_dir: Path):
    dst = dst_dir / src.name
    if dst.exists():
        stem, suffix = src.stem, src.suffix
        i = 1
        while dst.exists():
            dst = dst_dir / f"{stem}_{i}{suffix}"
            i += 1
    shutil.copy2(src, dst)


def write_pack_source(plan: PackPlan, output_dir: Path, status_cb=None) -> None:
    def status(msg):
        if status_cb:
            status_cb(msg)

    output_dir.mkdir(parents=True, exist_ok=True)
    source = Path(plan.source_dir) if plan.source_dir else None

    status("Copying media...")
    media_dir = output_dir / "media"
    media_dir.mkdir(exist_ok=True)
    for mood in plan.moods:
        mc = plan.mood_configs.get(mood, {})
        dst_mood_dir = media_dir / mood
        if dst_mood_dir.exists():
            shutil.rmtree(dst_mood_dir)
        dst_mood_dir.mkdir(parents=True)

        explicit_files = mc.get("media_files") or []
        if explicit_files:
            for fp in explicit_files:
                p = Path(fp)
                if p.is_file():
                    _unique_copy(p, dst_mood_dir)
        else:
            src_mood_dir = (source / mood) if source else None
            if src_mood_dir and src_mood_dir.is_dir():
                for item in src_mood_dir.iterdir():
                    if item.is_file():
                        _unique_copy(item, dst_mood_dir)
            else:
                raise FileNotFoundError(
                    f"No source media found for mood '{mood}' - expected a folder at "
                    f"'{src_mood_dir}' (or media files attached directly to this mood)."
                )

        for audio_path in mc.get("audio_paths", []):
            ap = Path(audio_path)
            if ap.is_file():
                _unique_copy(ap, dst_mood_dir)

    if plan.hypno_paths:
        status("Copying hypno overlays...")
        hypno_dir = output_dir / "hypno"
        hypno_dir.mkdir(exist_ok=True)
        for hp in plan.hypno_paths:
            hp_path = Path(hp)
            if hp_path.is_file():
                _unique_copy(hp_path, hypno_dir)

    wallpapers_dir = output_dir / "wallpapers"
    used_wallpapers = [
        (name, mc.get("wallpaper_path")) for name, mc in plan.mood_configs.items()
        if mc.get("wallpaper_change") and mc.get("wallpaper_path")
    ]
    missing_wallpapers = []
    if used_wallpapers or plan.default_wallpaper_path:
        status("Copying wallpapers...")
        wallpapers_dir.mkdir(exist_ok=True)
        for mood_name, wp in used_wallpapers:
            wp_path = Path(wp)
            if wp_path.is_file():
                shutil.copy2(wp_path, wallpapers_dir / wp_path.name)
            else:
                missing_wallpapers.append(f"'{mood_name}' -> {wp_path}")
        if plan.default_wallpaper_path:
            dwp = Path(plan.default_wallpaper_path)
            if dwp.is_file():
                shutil.copy2(dwp, wallpapers_dir / "wallpaper.png")
            else:
                missing_wallpapers.append(f"(default wallpaper) -> {dwp}")
    if missing_wallpapers:
        raise FileNotFoundError(
            "These wallpaper images couldn't be found and would have silently produced "
            "a broken (black) wallpaper in-game, so the build stopped instead:\n\n"
            + "\n".join(missing_wallpapers)
            + "\n\nRe-pick the wallpaper for the affected mood(s) on the Per-Mood page and try again."
        )

    if plan.loading_splash_path:
        status("Copying loading splash image...")
        lsp = Path(plan.loading_splash_path)
        if lsp.is_file():
            shutil.copy2(lsp, output_dir / f"loading_splash{lsp.suffix}")

    status("Writing pack.yml...")
    doc = build_pack_yml_dict(plan)
    (output_dir / "pack.yml").write_text(_dump_yaml(doc), encoding="utf-8")
    (output_dir / "plan.json").write_text(plan.to_json(), encoding="utf-8")


def zip_directory(src_dir: Path, dest_zip: Path, status_cb=None) -> None:
    if status_cb:
        status_cb("Zipping finished pack...")
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(Path(src_dir).rglob("*")):
            if file_path.is_file():
                zf.write(file_path, file_path.relative_to(src_dir))


# ---------------------------------------------------------------------------
# Invoking the existing Pack Tool compiler
# ---------------------------------------------------------------------------

def find_python_launcher() -> str:
    for candidate in ("py", "python", "python3"):
        if shutil.which(candidate):
            return candidate
    return sys.executable


def compile_with_pack_tool(pack_tool_dir: Path, source_pack_dir: Path, build_dir: Path,
                            compress_images: bool, compress_videos: bool, rename_media: bool,
                            status_cb=None):
    main_py = pack_tool_dir / "src" / "main.py"
    if not main_py.is_file():
        raise FileNotFoundError(f"Couldn't find src/main.py inside '{pack_tool_dir}'.")

    if status_cb:
        status_cb("Compiling with Pack Tool (this can take a while)...")

    py_cmd = find_python_launcher()
    args = [py_cmd, "src/main.py"]
    if compress_images:
        args.append("-i")
    if compress_videos:
        args.append("-v")
    if rename_media:
        args.append("-r")
    args += [str(source_pack_dir), "-o", str(build_dir)]

    result = subprocess.run(args, cwd=str(pack_tool_dir), capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Pack Tool compiler exited with an error.\n\n"
            f"Command: {' '.join(args)}\n\n"
            f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
        )
    if not build_dir.exists() or not any(build_dir.iterdir()):
        raise RuntimeError(
            f"Compiler reported success but '{build_dir}' is empty.\n\n"
            f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
        )
    return build_dir, result.stdout, result.stderr


# ---------------------------------------------------------------------------
# Load / reconstruct
# ---------------------------------------------------------------------------

def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def find_plan_json(folder: Path) -> Path:
    """Looks in `folder` and one level down (in case a zip wrapped
    everything in a subfolder) for a plan.json."""
    direct = folder / "plan.json"
    if direct.is_file():
        return direct
    if folder.is_dir():
        for child in folder.iterdir():
            if child.is_dir():
                candidate = child / "plan.json"
                if candidate.is_file():
                    return candidate
    return None


def load_plan_json(path: Path) -> PackPlan:
    data = json.loads(path.read_text(encoding="utf-8"))
    known_fields = {f for f in PackPlan.__dataclass_fields__}
    filtered = {k: v for k, v in data.items() if k in known_fields}
    return PackPlan(**filtered)


def reconstruct_plan_from_compiled_pack(folder: Path) -> tuple:
    """
    Best-effort reconstruction from a compiled pack's own files, for packs
    with no plan.json (i.e. not built by this tool, or a plan.json that
    got lost). This is NOT verified against a real compiled pack's exact
    JSON layout - it's built from pack.yml's documented structure (which
    the compiler is described as generating these files FROM) and the
    config.json shape confirmed from real Edgeware log output. If a field
    doesn't parse as expected, reconstruction skips it and keeps going
    rather than failing outright, and every skip is reported back so nothing
    fails silently.

    Returns (PackPlan or None, list_of_warnings).
    """
    warnings = []

    # A compiled pack might be nested one level down (zip wrapped it in a
    # subfolder) - use whichever level actually has info.json.
    root = folder
    if not (root / "info.json").is_file():
        for child in folder.iterdir() if folder.is_dir() else []:
            if child.is_dir() and (child / "info.json").is_file():
                root = child
                break

    info = _read_json(root / "info.json") or {}
    index = _read_json(root / "index.json") or {}
    media = _read_json(root / "media.json")
    corruption = _read_json(root / "corruption.json") or {}
    config = _read_json(root / "config.json") or {}

    if not info and not index:
        return None, ["This doesn't look like a compiled Edgeware++ pack - "
                       "no readable info.json or index.json found."]

    plan = PackPlan()
    plan.pack_name = info.get("name", plan.pack_name)
    plan.pack_id = info.get("id", plan.pack_id)
    plan.pack_creator = info.get("creator", plan.pack_creator)
    plan.pack_version = info.get("version", plan.pack_version)
    plan.pack_description = info.get("description", plan.pack_description)

    plan.cycle_mode = "timer" if config.get("corruptionTrigger", "Timed") == "Timed" else "popups"
    plan.cycle_seconds = config.get("corruptionTime", plan.cycle_seconds)
    plan.popups_per_mood = config.get("corruptionPopups", plan.popups_per_mood)
    plan.audio_mod_when_on = config.get("audioMod") or plan.audio_mod_when_on

    moods_list = index.get("moods", [])
    if not moods_list:
        warnings.append("index.json didn't have the mood list I expected - moods will be empty.")

    mood_names = []
    mood_configs = {}
    for entry in moods_list:
        name = entry.get("mood")
        if not name:
            continue
        mood_names.append(name)
        mood_configs[name] = asdict(MoodConfig(
            name=name,
            captions=entry.get("captions", []),
            notifications=entry.get("notifications", []),
            subliminal_messages=entry.get("subliminal-messages", []),
            prompts=entry.get("prompts", []),
            denial_captions=entry.get("denial", []),
            web_entries=entry.get("web", []),
        ))
    plan.moods = mood_names

    # Overlay corruption levels: wallpaper triggers, audio/advanced knobs,
    # and which moods get removed when each one activates.
    levels = corruption.get("levels", [])
    if levels and not mood_names:
        warnings.append("Found corruption levels but no mood list to match them against.")
    for level in levels:
        added = level.get("add-moods", [])
        if not added:
            continue
        target = added[0]
        if target not in mood_configs:
            warnings.append(f"Corruption level references mood '{target}' that wasn't in index.json - skipped.")
            continue
        mc = mood_configs[target]
        cfg = level.get("config", {}) or {}

        if "audioMod" in cfg:
            mc["audio_enabled"] = bool(cfg.get("audioMod"))
        advanced = {k: v for k, v in cfg.items() if k in ALL_ADVANCED_KEYS}
        if advanced:
            mc["advanced"] = advanced

        wallpaper_name = level.get("wallpaper")
        if wallpaper_name:
            candidate = root / "wallpapers" / wallpaper_name
            mc["wallpaper_change"] = True
            mc["wallpaper_path"] = str(candidate) if candidate.is_file() else ""
            if not candidate.is_file():
                warnings.append(f"'{target}' references wallpaper '{wallpaper_name}' - file not found, you'll need to re-pick it.")

        remove_list = level.get("remove-moods", [])
        if remove_list:
            mc["remove_moods"] = [m for m in remove_list if m in mood_configs]

    # Try to regroup flat media files back into per-mood buckets using
    # media.json's own mood tags, if the shape is one we recognize.
    grouped_any = False
    if isinstance(media, dict):
        entries = media.items() if all(isinstance(v, dict) for v in media.values()) else []
        for filename, meta in entries:
            file_moods = meta.get("moods") or meta.get("mood") or []
            if isinstance(file_moods, str):
                file_moods = [file_moods]
            file_path = None
            for subfolder in ("img", "aud", "vid"):
                candidate = root / subfolder / filename
                if candidate.is_file():
                    file_path = candidate
                    break
            if not file_path:
                continue
            for m in file_moods:
                if m in mood_configs:
                    mood_configs[m].setdefault("media_files", [])
                    mood_configs[m]["media_files"].append(str(file_path))
                    grouped_any = True
    elif isinstance(media, list):
        for entry in media:
            filename = entry.get("file") or entry.get("path")
            file_moods = entry.get("moods") or entry.get("mood") or []
            if isinstance(file_moods, str):
                file_moods = [file_moods]
            if not filename:
                continue
            file_path = None
            for subfolder in ("img", "aud", "vid"):
                candidate = root / subfolder / Path(filename).name
                if candidate.is_file():
                    file_path = candidate
                    break
            if not file_path:
                continue
            for m in file_moods:
                if m in mood_configs:
                    mood_configs[m].setdefault("media_files", [])
                    mood_configs[m]["media_files"].append(str(file_path))
                    grouped_any = True

    if not grouped_any:
        warnings.append(
            "Couldn't confidently regroup media files by mood from media.json - "
            "you'll need to point each mood at its images again before rebuilding "
            "(everything else - captions, corruption levels, settings - carried over)."
        )

    plan.mood_configs = mood_configs

    hypno_dir = root / "hypno"
    if hypno_dir.is_dir():
        plan.hypno_paths = [str(p) for p in hypno_dir.iterdir() if p.is_file()]

    default_wp = root / "wallpapers" / "wallpaper.png"
    if default_wp.is_file():
        plan.default_wallpaper_path = str(default_wp)

    for ext in (".png", ".gif", ".jpg", ".jpeg", ".bmp"):
        splash = root / f"loading_splash{ext}"
        if splash.is_file():
            plan.loading_splash_path = str(splash)
            break

    return plan, warnings


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class PackBuilderApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Edgeware++ Advanced Pack Builder")
        self.root.geometry("820x800")
        apply_theme(self.root)

        self.plan = PackPlan()
        self.settings = load_settings()
        self.reconstructed_warnings = []

        self.source_var = StringVar(value="No folder selected")
        self.pack_tool_var = StringVar(value="Not set (you'll compile manually)")
        self.pack_tool_note_var = StringVar(value="")
        self.mood_count_var = StringVar(value="")

        self.name_var = StringVar(value=self.plan.pack_name)
        self.id_var = StringVar(value=self.plan.pack_id)
        self.creator_var = StringVar(value=self.plan.pack_creator)
        self.version_var = StringVar(value=self.plan.pack_version)
        self.desc_var = StringVar(value=self.plan.pack_description)

        self.cycle_mode_var = StringVar(value=self.plan.cycle_mode)
        self.cycle_seconds_var = IntVar(value=self.plan.cycle_seconds)
        self.cycle_apply_start_var = IntVar(value=self.plan.cycle_seconds)
        self.cycle_apply_end_var = IntVar(value=self.plan.cycle_seconds)
        self.denial_start_var = IntVar(value=0)
        self.denial_end_var = IntVar(value=0)
        self.popups_var = IntVar(value=self.plan.popups_per_mood)
        self.escalate_var = BooleanVar(value=self.plan.escalate_spirals)
        self.spiral_start_var = IntVar(value=self.plan.spiral_start_pct)
        self.spiral_end_var = IntVar(value=self.plan.spiral_end_pct)
        self.audio_level_var = IntVar(value=self.plan.audio_mod_when_on)

        self.compress_images_var = BooleanVar(value=False)
        self.compress_videos_var = BooleanVar(value=False)
        self.rename_media_var = BooleanVar(value=False)

        self.hypno_paths: list = []
        self.hypno_label_var = StringVar(value="No files selected")
        self.default_wallpaper_path = ""
        self.default_wallpaper_label_var = StringVar(value="No image selected")
        self.loading_splash_path = ""
        self.loading_splash_label_var = StringVar(value="No image selected")

        self.mood_names: list = []
        self.mood_widgets: dict = {}
        self._banner_img = None

        self.progress_var = None
        self._build_result = {}
        self._build_thread = None

        # Auto-detect / remember the Pack Tool folder
        auto = find_pack_tool_dir()
        if auto:
            self.plan.pack_tool_dir = auto
            self.pack_tool_var.set(auto)
            self.pack_tool_note_var.set("(auto-detected)")
        elif self.settings.get("pack_tool_dir") and (Path(self.settings["pack_tool_dir"]) / "src" / "main.py").is_file():
            self.plan.pack_tool_dir = self.settings["pack_tool_dir"]
            self.pack_tool_var.set(self.plan.pack_tool_dir)
            self.pack_tool_note_var.set("(remembered from last time)")

        self._build_step1()

    # -- Step 1 -----------------------------------------------------------------

    def _build_step1(self):
        for w in self.root.winfo_children():
            w.destroy()

        scroller = ScrollableFrame(self.root)
        scroller.pack(fill="both", expand=True)
        frm = ttk.Frame(scroller.inner, padding=20)
        frm.pack(fill="both", expand=True)

        if BANNER_PATH.is_file():
            try:
                img = tk.PhotoImage(file=str(BANNER_PATH))
                factor = max(1, img.width() // 260)
                if factor > 1:
                    img = img.subsample(factor, factor)
                self._banner_img = img
                ttk.Label(frm, image=self._banner_img).pack(pady=(0, 10))
            except tk.TclError:
                pass

        ttk.Label(frm, text="Edgeware++ Advanced Pack Builder", style="Header.TLabel").pack(anchor="w")

        if self.reconstructed_warnings:
            warn_frame = tk.Frame(frm, bg=WARN_BG, padx=10, pady=8)
            warn_frame.pack(fill="x", pady=(10, 0))
            tk.Label(warn_frame, text="Reconstructed pack (approximate) - review before rebuilding:",
                     bg=WARN_BG, fg=WARN_FG, font=("Segoe UI", 9, "bold"), justify="left").pack(anchor="w")
            for w in self.reconstructed_warnings:
                tk.Label(warn_frame, text=f"- {w}", bg=WARN_BG, fg=WARN_FG,
                         wraplength=700, justify="left").pack(anchor="w")

        load_row = ttk.Frame(frm)
        load_row.pack(fill="x", pady=(14, 0))
        load_folder_btn = ttk.Button(load_row, text="Load Existing Pack (Folder)...", command=self._load_from_folder)
        load_folder_btn.pack(side="left")
        tip(load_folder_btn, TOOLTIPS["load_pack"])
        load_zip_btn = ttk.Button(load_row, text="Load Existing Pack (ZIP)...", command=self._load_from_zip)
        load_zip_btn.pack(side="left", padx=(8, 0))
        tip(load_zip_btn, TOOLTIPS["load_pack"])

        ttk.Label(frm, text="Where is the folder of images?", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(18, 0))
        ttk.Label(frm, text="(One subfolder per mood. The first one becomes the pack's starting mood.)",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 10))

        row = ttk.Frame(frm)
        row.pack(fill="x", pady=5)
        src_entry = ttk.Entry(row, textvariable=self.source_var, state="readonly")
        src_entry.pack(side="left", fill="x", expand=True)
        tip(src_entry, TOOLTIPS["source_folder"])
        browse_btn = ttk.Button(row, text="Browse...", command=self._pick_folder)
        browse_btn.pack(side="left", padx=(8, 0))
        tip(browse_btn, TOOLTIPS["source_folder"])

        ttk.Label(frm, textvariable=self.mood_count_var, font=("Segoe UI", 10, "italic")).pack(anchor="w", pady=(10, 0))

        self.mood_list_frame = ttk.Frame(frm)
        self.mood_list_frame.pack(fill="x", pady=10)
        if self.mood_names:
            self._render_mood_list()

        pt_frame = ttk.LabelFrame(frm, text="Pack Tool location (optional, enables one-click build)", padding=10)
        pt_frame.pack(fill="x", pady=(15, 5))
        ttk.Label(pt_frame, text="Folder containing src/main.py:", style="Muted.TLabel").pack(anchor="w")
        pt_row = ttk.Frame(pt_frame)
        pt_row.pack(fill="x", pady=(4, 0))
        pt_entry = ttk.Entry(pt_row, textvariable=self.pack_tool_var, state="readonly")
        pt_entry.pack(side="left", fill="x", expand=True)
        tip(pt_entry, TOOLTIPS["pack_tool_folder"])
        pt_browse = ttk.Button(pt_row, text="Browse...", command=self._pick_pack_tool)
        pt_browse.pack(side="left", padx=(8, 0))
        tip(pt_browse, TOOLTIPS["pack_tool_folder"])
        ttk.Label(pt_frame, textvariable=self.pack_tool_note_var, style="Muted.TLabel").pack(anchor="w", pady=(4, 0))
        ttk.Label(
            pt_frame,
            text="If set, Build Pack compiles straight to a finished .zip. If left unset, "
                 "you'll get a pack.yml + media folder to compile yourself.",
            style="Muted.TLabel", wraplength=650, justify="left"
        ).pack(anchor="w", pady=(6, 0))

        self.next_btn = ttk.Button(frm, text="Next: Whole-Experience Settings", command=self._go_step2,
                                    state="normal" if self.mood_names else "disabled")
        self.next_btn.pack(anchor="e", pady=(15, 0))

    def _render_mood_list(self):
        for w in self.mood_list_frame.winfo_children():
            w.destroy()
        self.mood_count_var.set(
            f"You have {len(self.mood_names)} moods ready "
            f"('{self.mood_names[0]}' is the starting mood):"
        )
        for i, name in enumerate(self.mood_names, start=1):
            tag = " (starting)" if i == 1 else ""
            ttk.Label(self.mood_list_frame, text=f"  {i}. {name}{tag}").pack(anchor="w")

    def _pick_folder(self):
        chosen = filedialog.askdirectory(title="Select folder of mood subfolders")
        if not chosen:
            return
        self.source_var.set(chosen)
        self.plan.source_dir = chosen
        self.mood_names = scan_moods(Path(chosen))
        self.plan.moods = self.mood_names

        if not self.mood_names:
            self.mood_count_var.set("No subfolders found - this folder needs one subfolder per mood.")
            for w in self.mood_list_frame.winfo_children():
                w.destroy()
            self.next_btn.config(state="disabled")
            return

        self._render_mood_list()
        self.next_btn.config(state="normal")

    def _pick_pack_tool(self):
        chosen = filedialog.askdirectory(title="Select the Pack Tool folder (contains src/main.py)")
        if not chosen:
            return
        if not (Path(chosen) / "src" / "main.py").is_file():
            messagebox.showwarning(
                "src/main.py not found",
                f"'{chosen}' doesn't have a src/main.py inside it - double check you picked "
                f"the Pack Tool folder itself (the one PackToolScript.bat lives in)."
            )
        self.plan.pack_tool_dir = chosen
        self.pack_tool_var.set(chosen)
        self.pack_tool_note_var.set("")
        self.settings["pack_tool_dir"] = chosen
        save_settings(self.settings)

    # -- Load ---------------------------------------------------------------

    def _load_from_folder(self):
        chosen = filedialog.askdirectory(title="Select a pack folder to load")
        if chosen:
            self._load_pack(Path(chosen))

    def _load_from_zip(self):
        chosen = filedialog.askopenfilename(title="Select a pack .zip to load", filetypes=[("Zip files", "*.zip")])
        if not chosen:
            return
        try:
            # Extract somewhere STABLE rather than the OS temp folder - a
            # loaded pack's file paths (wallpapers, media, etc.) get referenced
            # later at build time, potentially much later, and OS temp dirs
            # aren't guaranteed to still be there by then.
            loaded_root = SCRIPT_DIR / "loaded_packs"
            loaded_root.mkdir(exist_ok=True)
            stem = "".join(c if (c.isalnum() or c in " -_") else "_" for c in Path(chosen).stem).strip() or "pack"
            extract_dir = loaded_root / stem
            i = 1
            while extract_dir.exists():
                extract_dir = loaded_root / f"{stem}_{i}"
                i += 1
            extract_dir.mkdir(parents=True)
            with zipfile.ZipFile(chosen) as zf:
                zf.extractall(extract_dir)
        except Exception as e:
            messagebox.showerror("Couldn't open zip", str(e))
            return
        self._load_pack(extract_dir)

    def _load_pack(self, folder: Path):
        plan_json_path = find_plan_json(folder)
        self.reconstructed_warnings = []

        if plan_json_path:
            try:
                self.plan = load_plan_json(plan_json_path)
            except Exception as e:
                messagebox.showerror("Couldn't load plan.json", str(e))
                return
        else:
            proceed = messagebox.askyesno(
                "plan.json not found",
                "plan.json not available for this pack. Want to try reconstructing "
                "settings from the pack's own files instead? This will be an "
                "approximation, not an exact match."
            )
            if not proceed:
                return
            plan, warnings = reconstruct_plan_from_compiled_pack(folder)
            if plan is None:
                messagebox.showerror("Couldn't reconstruct", "\n".join(warnings) if warnings else "Unknown error.")
                return
            self.plan = plan
            self.reconstructed_warnings = warnings

        self._apply_loaded_plan()
        messagebox.showinfo(
            "Pack loaded",
            f"Loaded '{self.plan.pack_name}' - {len(self.plan.moods)} mood(s)."
            + ("\n\nThis was reconstructed (approximate) - see the notes on the front page."
               if self.reconstructed_warnings else "")
        )
        self._build_step1()

    def _apply_loaded_plan(self):
        """Push a freshly loaded/reconstructed PackPlan into every widget var."""
        self.mood_names = list(self.plan.moods)
        self.source_var.set(self.plan.source_dir or "No folder selected")

        self.name_var.set(self.plan.pack_name)
        self.id_var.set(self.plan.pack_id)
        self.creator_var.set(self.plan.pack_creator)
        self.version_var.set(self.plan.pack_version)
        self.desc_var.set(self.plan.pack_description)

        self.cycle_mode_var.set(self.plan.cycle_mode)
        self.cycle_seconds_var.set(self.plan.cycle_seconds)
        self.popups_var.set(self.plan.popups_per_mood)
        self.escalate_var.set(self.plan.escalate_spirals)
        self.spiral_start_var.set(self.plan.spiral_start_pct)
        self.spiral_end_var.set(self.plan.spiral_end_pct)
        self.audio_level_var.set(self.plan.audio_mod_when_on)

        self.compress_images_var.set(self.plan.compress_images)
        self.compress_videos_var.set(self.plan.compress_videos)
        self.rename_media_var.set(self.plan.rename_media)

        self.hypno_paths = list(self.plan.hypno_paths)
        self.hypno_label_var.set(
            f"{len(self.hypno_paths)} file(s): " + ", ".join(Path(p).name for p in self.hypno_paths)
            if self.hypno_paths else "No files selected"
        )
        self.default_wallpaper_path = self.plan.default_wallpaper_path
        self.default_wallpaper_label_var.set(Path(self.default_wallpaper_path).name if self.default_wallpaper_path else "No image selected")
        self.loading_splash_path = self.plan.loading_splash_path
        self.loading_splash_label_var.set(Path(self.loading_splash_path).name if self.loading_splash_path else "No image selected")

        if self.plan.pack_tool_dir:
            self.pack_tool_var.set(self.plan.pack_tool_dir)

    # -- Step 2: whole-experience settings ---------------------------------

    def _go_step2(self):
        self._build_step2()

    def _build_step2(self):
        for w in self.root.winfo_children():
            w.destroy()

        scroller = ScrollableFrame(self.root)
        scroller.pack(fill="both", expand=True)
        frm = ttk.Frame(scroller.inner, padding=20)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Whole-Experience Settings", style="Header.TLabel").pack(anchor="w", pady=(0, 10))

        preset_frame = ttk.LabelFrame(frm, text="Presets", padding=10)
        preset_frame.pack(fill="x", pady=5)
        ttk.Label(preset_frame, text="Fill in Advanced Settings for every mood at once with a ready-made pacing curve.",
                  style="Muted.TLabel", wraplength=650, justify="left").pack(anchor="w", pady=(0, 6))
        preset_btn_row = ttk.Frame(preset_frame)
        preset_btn_row.pack(fill="x")
        for preset_name in PRESETS:
            b = ttk.Button(preset_btn_row, text=preset_name,
                            command=lambda n=preset_name: self._apply_preset(n))
            b.pack(side="left", padx=(0, 8))
            tip(b, TOOLTIPS["preset_button"])

        info_frame = ttk.LabelFrame(frm, text="Pack Info", padding=10)
        info_frame.pack(fill="x", pady=5)
        self._labeled_entry(info_frame, "Pack name:", self.name_var, TOOLTIPS["pack_name"])
        self._labeled_entry(info_frame, "Pack ID:", self.id_var, TOOLTIPS["pack_id"])
        self._labeled_entry(info_frame, "Creator:", self.creator_var, TOOLTIPS["pack_creator"])
        self._labeled_entry(info_frame, "Version:", self.version_var, TOOLTIPS["pack_version"])
        self._labeled_entry(info_frame, "Description:", self.desc_var, TOOLTIPS["pack_description"])

        cycle_frame = ttk.LabelFrame(frm, text="Mood Cycling", padding=10)
        cycle_frame.pack(fill="x", pady=5)
        r1 = ttk.Radiobutton(cycle_frame, text="Cycle to next mood after a time delay",
                              variable=self.cycle_mode_var, value="timer")
        r1.pack(anchor="w")
        tip(r1, TOOLTIPS["cycle_timer"])
        timer_row = ttk.Frame(cycle_frame)
        timer_row.pack(anchor="w", padx=20, pady=(2, 6))
        ttk.Label(timer_row, text="Cycle length (seconds):").pack(side="left")
        m_spin = ttk.Spinbox(timer_row, from_=5, to=7200, textvariable=self.cycle_seconds_var, width=7)
        m_spin.pack(side="left", padx=6)
        tip(m_spin, TOOLTIPS["cycle_seconds"])

        r2 = ttk.Radiobutton(cycle_frame, text="Cycle to next mood after N popups appear",
                              variable=self.cycle_mode_var, value="popups")
        r2.pack(anchor="w")
        tip(r2, TOOLTIPS["cycle_popups"])
        popups_row = ttk.Frame(cycle_frame)
        popups_row.pack(anchor="w", padx=20, pady=(2, 0))
        ttk.Label(popups_row, text="Popups per mood:").pack(side="left")
        p_spin = ttk.Spinbox(popups_row, from_=1, to=500, textvariable=self.popups_var, width=6)
        p_spin.pack(side="left", padx=6)
        tip(p_spin, TOOLTIPS["popups_per_mood"])

        ttk.Label(cycle_frame, text="Ramp cycle length across moods (optional):",
                  style="Muted.TLabel").pack(anchor="w", pady=(8, 0))
        cyc_apply_row = ttk.Frame(cycle_frame)
        cyc_apply_row.pack(anchor="w", padx=20, pady=(2, 0))
        ttk.Label(cyc_apply_row, text="Start:").pack(side="left")
        ca_s = ttk.Spinbox(cyc_apply_row, from_=1, to=7200, textvariable=self.cycle_apply_start_var, width=7)
        ca_s.pack(side="left", padx=(4, 12))
        tip(ca_s, TOOLTIPS["cycle_apply"])
        ttk.Label(cyc_apply_row, text="End:").pack(side="left")
        ca_e = ttk.Spinbox(cyc_apply_row, from_=1, to=7200, textvariable=self.cycle_apply_end_var, width=7)
        ca_e.pack(side="left", padx=4)
        tip(ca_e, TOOLTIPS["cycle_apply"])
        ca_btn = ttk.Button(cyc_apply_row, text="Apply", command=self._apply_cycle_length)
        ca_btn.pack(side="left", padx=(12, 0))
        tip(ca_btn, TOOLTIPS["cycle_apply"])
        ttk.Label(cycle_frame,
                  text="(Writes seconds into each mood's 'Cycle length override' if Timed is selected above, "
                       "or popup-count if 'N popups' is selected - matches whichever mode is picked when you click Apply.)",
                  style="Muted.TLabel", wraplength=650, justify="left").pack(anchor="w", padx=20, pady=(2, 0))

        spiral_frame = ttk.LabelFrame(frm, text="Escalating Spirals (subliminal overlay chance)", padding=10)
        spiral_frame.pack(fill="x", pady=5)
        esc_check = ttk.Checkbutton(spiral_frame, text="Spiral overlay chance increases as moods progress",
                                     variable=self.escalate_var)
        esc_check.pack(anchor="w")
        tip(esc_check, TOOLTIPS["escalate_spirals"])
        pct_row = ttk.Frame(spiral_frame)
        pct_row.pack(anchor="w", padx=20, pady=(2, 0))
        ttk.Label(pct_row, text="Start %:").pack(side="left")
        s_spin = ttk.Spinbox(pct_row, from_=0, to=100, textvariable=self.spiral_start_var, width=5)
        s_spin.pack(side="left", padx=(4, 12))
        tip(s_spin, TOOLTIPS["spiral_start"])
        ttk.Label(pct_row, text="End %:").pack(side="left")
        e_spin = ttk.Spinbox(pct_row, from_=0, to=100, textvariable=self.spiral_end_var, width=5)
        e_spin.pack(side="left", padx=4)
        tip(e_spin, TOOLTIPS["spiral_end"])
        sp_apply_btn = ttk.Button(pct_row, text="Apply", command=self._apply_spiral)
        sp_apply_btn.pack(side="left", padx=(12, 0))
        tip(sp_apply_btn, TOOLTIPS["spiral_apply"])
        ttk.Label(spiral_frame,
                  text="(The checkbox alone auto-ramps this at build time without showing per-mood numbers. "
                       "Apply writes the actual number into each mood's Advanced Settings so you can see and adjust it.)",
                  style="Muted.TLabel", wraplength=650, justify="left").pack(anchor="w", pady=(4, 0))

        denial_frame = ttk.LabelFrame(frm, text="Escalating Denial ('not yet!' message chance)", padding=10)
        denial_frame.pack(fill="x", pady=5)
        denial_row = ttk.Frame(denial_frame)
        denial_row.pack(anchor="w")
        ttk.Label(denial_row, text="Start %:").pack(side="left")
        d_s = ttk.Spinbox(denial_row, from_=0, to=100, textvariable=self.denial_start_var, width=5)
        d_s.pack(side="left", padx=(4, 12))
        tip(d_s, TOOLTIPS["denial_start"])
        ttk.Label(denial_row, text="End %:").pack(side="left")
        d_e = ttk.Spinbox(denial_row, from_=0, to=100, textvariable=self.denial_end_var, width=5)
        d_e.pack(side="left", padx=4)
        tip(d_e, TOOLTIPS["denial_end"])
        d_apply_btn = ttk.Button(denial_row, text="Apply", command=self._apply_denial)
        d_apply_btn.pack(side="left", padx=(12, 0))
        tip(d_apply_btn, TOOLTIPS["denial_apply"])
        ttk.Label(denial_frame, text="Writes into each mood's Advanced Settings on the next page, spread evenly.",
                  style="Muted.TLabel", wraplength=650, justify="left").pack(anchor="w", pady=(4, 0))

        audio_lvl_frame = ttk.LabelFrame(frm, text="Audio Chance When Enabled", padding=10)
        audio_lvl_frame.pack(fill="x", pady=5)
        al_row = ttk.Frame(audio_lvl_frame)
        al_row.pack(anchor="w")
        ttk.Label(al_row, text="Audio popup chance (%) for moods with audio ON:").pack(side="left")
        al_spin = ttk.Spinbox(al_row, from_=0, to=100, textvariable=self.audio_level_var, width=5)
        al_spin.pack(side="left", padx=6)
        tip(al_spin, TOOLTIPS["audio_level"])

        extras_frame = ttk.LabelFrame(frm, text="Pack-Wide Extras", padding=10)
        extras_frame.pack(fill="x", pady=5)

        hypno_row = ttk.Frame(extras_frame)
        hypno_row.pack(fill="x", pady=2)
        ttk.Label(hypno_row, text="Hypno/spiral overlays:", width=20).pack(side="left")
        hypno_btn = ttk.Button(hypno_row, text="Add Images...", command=self._add_hypno)
        hypno_btn.pack(side="left", padx=(0, 8))
        tip(hypno_btn, TOOLTIPS["hypno_add"])
        ttk.Label(hypno_row, textvariable=self.hypno_label_var, style="Muted.TLabel",
                  wraplength=420, justify="left").pack(side="left")
        hypno_clear = ttk.Button(hypno_row, text="Clear", command=self._clear_hypno)
        hypno_clear.pack(side="left", padx=(8, 0))
        tip(hypno_clear, TOOLTIPS["hypno_clear"])

        wp_row = ttk.Frame(extras_frame)
        wp_row.pack(fill="x", pady=2)
        ttk.Label(wp_row, text="Default wallpaper:", width=20).pack(side="left")
        dwp_btn = ttk.Button(wp_row, text="Choose PNG...", command=self._pick_default_wallpaper)
        dwp_btn.pack(side="left", padx=(0, 8))
        tip(dwp_btn, TOOLTIPS["default_wallpaper"])
        ttk.Label(wp_row, textvariable=self.default_wallpaper_label_var, style="Muted.TLabel").pack(side="left")
        dwp_clear = ttk.Button(wp_row, text="Clear", command=self._clear_default_wallpaper)
        dwp_clear.pack(side="left", padx=(8, 0))
        tip(dwp_clear, TOOLTIPS["default_wallpaper_clear"])

        splash_row = ttk.Frame(extras_frame)
        splash_row.pack(fill="x", pady=2)
        ttk.Label(splash_row, text="Loading screen image:", width=20).pack(side="left")
        splash_btn = ttk.Button(splash_row, text="Choose Image...", command=self._pick_loading_splash)
        splash_btn.pack(side="left", padx=(0, 8))
        tip(splash_btn, TOOLTIPS["loading_splash"])
        ttk.Label(splash_row, textvariable=self.loading_splash_label_var, style="Muted.TLabel").pack(side="left")
        splash_clear = ttk.Button(splash_row, text="Clear", command=self._clear_loading_splash)
        splash_clear.pack(side="left", padx=(8, 0))
        tip(splash_clear, TOOLTIPS["loading_splash_clear"])

        if self.plan.pack_tool_dir:
            build_opts = ttk.LabelFrame(frm, text="Build Options (Pack Tool compiler)", padding=10)
            build_opts.pack(fill="x", pady=5)
            ci = ttk.Checkbutton(build_opts, text="Compress images", variable=self.compress_images_var)
            ci.pack(anchor="w")
            tip(ci, TOOLTIPS["compress_images"])
            cv = ttk.Checkbutton(build_opts, text="Compress videos", variable=self.compress_videos_var)
            cv.pack(anchor="w")
            tip(cv, TOOLTIPS["compress_videos"])
            rm = ttk.Checkbutton(build_opts, text="Rename media files for mood-specific captions",
                                  variable=self.rename_media_var)
            rm.pack(anchor="w")
            tip(rm, TOOLTIPS["rename_media"])

        btn_row = ttk.Frame(frm)
        btn_row.pack(fill="x", pady=(15, 25))
        ttk.Button(btn_row, text="Back", command=self._build_step1).pack(side="left")
        ttk.Button(btn_row, text="Next: Per-Mood Settings", command=self._go_step3).pack(side="right")

    def _labeled_entry(self, parent, label, var, tooltip_text=None):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=14).pack(side="left")
        entry = ttk.Entry(row, textvariable=var)
        entry.pack(side="left", fill="x", expand=True)
        if tooltip_text:
            tip(entry, tooltip_text)

    def _add_hypno(self):
        chosen = filedialog.askopenfilenames(
            title="Add hypno/subliminal overlay images",
            filetypes=[("Images", "*.gif *.png *.jpg *.jpeg *.webp")]
        )
        if chosen:
            self.hypno_paths.extend(chosen)
            names = [Path(p).name for p in self.hypno_paths]
            self.hypno_label_var.set(f"{len(names)} file(s): " + ", ".join(names))

    def _clear_hypno(self):
        self.hypno_paths = []
        self.hypno_label_var.set("No files selected")

    def _pick_default_wallpaper(self):
        chosen = filedialog.askopenfilename(
            title="Choose default wallpaper (must be PNG)",
            filetypes=[("PNG image", "*.png")]
        )
        if chosen:
            self.default_wallpaper_path = chosen
            self.default_wallpaper_label_var.set(Path(chosen).name)

    def _clear_default_wallpaper(self):
        self.default_wallpaper_path = ""
        self.default_wallpaper_label_var.set("No image selected")

    def _pick_loading_splash(self):
        chosen = filedialog.askopenfilename(
            title="Choose loading screen image",
            filetypes=[("Images", "*.png *.gif *.jpg *.jpeg *.bmp")]
        )
        if chosen:
            self.loading_splash_path = chosen
            self.loading_splash_label_var.set(Path(chosen).name)

    def _clear_loading_splash(self):
        self.loading_splash_path = ""
        self.loading_splash_label_var.set("No image selected")

    def _sync_step2_into_plan(self):
        self.plan.pack_name = self.name_var.get()
        self.plan.pack_id = self.id_var.get()
        self.plan.pack_creator = self.creator_var.get()
        self.plan.pack_version = self.version_var.get()
        self.plan.pack_description = self.desc_var.get()

        self.plan.cycle_mode = self.cycle_mode_var.get()
        self.plan.cycle_seconds = self.cycle_seconds_var.get()
        self.plan.popups_per_mood = self.popups_var.get()
        self.plan.escalate_spirals = self.escalate_var.get()
        self.plan.spiral_start_pct = self.spiral_start_var.get()
        self.plan.spiral_end_pct = self.spiral_end_var.get()
        self.plan.audio_mod_when_on = self.audio_level_var.get()

        self.plan.compress_images = self.compress_images_var.get()
        self.plan.compress_videos = self.compress_videos_var.get()
        self.plan.rename_media = self.rename_media_var.get()

        self.plan.hypno_paths = list(self.hypno_paths)
        self.plan.default_wallpaper_path = self.default_wallpaper_path
        self.plan.loading_splash_path = self.loading_splash_path

    # -- Spread-across-moods helpers (presets + Apply buttons) ----------------

    def _apply_spread_to_moods(self, key: str, start, end, curve: str = "linear"):
        n = len(self.mood_names)
        if n == 0:
            return
        values = spread_values(n, start, end, curve)
        for name, val in zip(self.mood_names, values):
            mc = self.plan.mood_configs.get(name) or asdict(MoodConfig(name=name))
            mc.setdefault("advanced", {})
            mc["advanced"][key] = val
            self.plan.mood_configs[name] = mc

    def _apply_cycle_length(self):
        if not self.mood_names:
            messagebox.showinfo("No moods yet", "Pick a source folder with mood subfolders first.")
            return
        key = "corruptionTime" if self.cycle_mode_var.get() == "timer" else "corruptionPopups"
        self._apply_spread_to_moods(key, self.cycle_apply_start_var.get(), self.cycle_apply_end_var.get(), "linear")
        messagebox.showinfo("Applied", f"Cycle length spread across {len(self.mood_names)} mood(s). "
                                        f"Check Advanced Settings on the next page to fine-tune.")

    def _apply_spiral(self):
        if not self.mood_names:
            messagebox.showinfo("No moods yet", "Pick a source folder with mood subfolders first.")
            return
        self._apply_spread_to_moods("subliminalsChance", self.spiral_start_var.get(), self.spiral_end_var.get(), "linear")
        messagebox.showinfo("Applied", f"Spiral chance spread across {len(self.mood_names)} mood(s). "
                                        f"Check Advanced Settings on the next page to fine-tune.")

    def _apply_denial(self):
        if not self.mood_names:
            messagebox.showinfo("No moods yet", "Pick a source folder with mood subfolders first.")
            return
        self._apply_spread_to_moods("denialChance", self.denial_start_var.get(), self.denial_end_var.get(), "linear")
        messagebox.showinfo("Applied", f"Denial chance spread across {len(self.mood_names)} mood(s). "
                                        f"Check Advanced Settings on the next page to fine-tune.")

    def _apply_preset(self, preset_name: str):
        n = len(self.mood_names)
        if n == 0:
            messagebox.showinfo("No moods yet", "Pick a source folder with mood subfolders first.")
            return
        if not messagebox.askyesno(
            "Apply preset?",
            f"This will overwrite Advanced Settings (pacing/effects) for all {n} moods "
            f"with the '{preset_name}' preset. Continue?"
        ):
            return
        for key, (start, end, curve) in PRESETS[preset_name].items():
            self._apply_spread_to_moods(key, start, end, curve)
        messagebox.showinfo(
            "Preset applied",
            f"'{preset_name}' applied to all {n} moods. Check Advanced Settings on the "
            f"next page to fine-tune individual moods."
        )

    def _go_step3(self):
        self._sync_step2_into_plan()
        self._build_step3()

    # -- Step 3: per-mood settings -------------------------------------------

    def _build_step3(self):
        for w in self.root.winfo_children():
            w.destroy()

        scroller = ScrollableFrame(self.root)
        scroller.pack(fill="both", expand=True)
        frm = ttk.Frame(scroller.inner, padding=20)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Per-Mood Configuration", style="Header.TLabel").pack(anchor="w", pady=(0, 10))
        ttk.Label(frm, text="Click a mood's name to expand its settings.", style="Muted.TLabel").pack(anchor="w", pady=(0, 8))

        self.mood_widgets = {}
        for i, name in enumerate(self.mood_names):
            self._build_mood_card(frm, name, mood_index=i)

        self.status_var = StringVar(value="")
        self.progress = ttk.Progressbar(frm, mode="indeterminate")
        self.status_label = ttk.Label(frm, textvariable=self.status_var, style="Muted.TLabel")

        btn_row = ttk.Frame(frm)
        btn_row.pack(fill="x", pady=(15, 25))
        ttk.Button(btn_row, text="Back", command=self._go_back_to_step2).pack(side="left")
        self.build_btn = ttk.Button(btn_row, text="Build Pack", command=self._collect_and_build)
        self.build_btn.pack(side="right")

    def _go_back_to_step2(self):
        self._sync_moods_into_plan(strict=False)
        self._build_step2()

    def _build_mood_card(self, parent, mood_name, mood_index):
        existing = self.plan.mood_configs.get(mood_name, {})

        outer = ttk.Frame(parent)
        outer.pack(fill="x", pady=4)

        state = {"expanded": False}
        toggle_btn = ttk.Button(outer, text=f"\u25b8 {mood_name}" + (" (starting mood)" if mood_index == 0 else ""))
        toggle_btn.pack(fill="x")
        tip(toggle_btn, TOOLTIPS["mood_card_toggle"])

        card = ttk.LabelFrame(outer, padding=10)
        # not packed - starts collapsed

        def toggle():
            if state["expanded"]:
                card.pack_forget()
                toggle_btn.config(text=f"\u25b8 {mood_name}" + (" (starting mood)" if mood_index == 0 else ""))
            else:
                card.pack(fill="x", pady=(2, 0))
                toggle_btn.config(text=f"\u25be {mood_name}" + (" (starting mood)" if mood_index == 0 else ""))
            state["expanded"] = not state["expanded"]

        toggle_btn.config(command=toggle)

        ttk.Label(card, text="Add captions here for this mood. Use linebreaks (Enter) to start the next caption.",
                  style="Muted.TLabel", wraplength=650, justify="left").pack(anchor="w")
        captions_text = tk.Text(card, height=4, wrap="word")
        style_text_widget(captions_text)
        captions_text.pack(fill="x", pady=(2, 8))
        tip(captions_text, TOOLTIPS["captions_box"])
        if existing.get("captions"):
            captions_text.insert("1.0", "\n".join(existing["captions"]))

        ttk.Label(card, text="Add notifications here for this mood (one per line).",
                  style="Muted.TLabel", wraplength=650, justify="left").pack(anchor="w")
        notif_text = tk.Text(card, height=2, wrap="word")
        style_text_widget(notif_text)
        notif_text.pack(fill="x", pady=(2, 8))
        tip(notif_text, TOOLTIPS["notif_box"])
        if existing.get("notifications"):
            notif_text.insert("1.0", "\n".join(existing["notifications"]))

        ttk.Label(card, text="Subliminal messages for this mood (one per line) - flashed briefly on screen.",
                  style="Muted.TLabel", wraplength=650, justify="left").pack(anchor="w")
        subliminal_text = tk.Text(card, height=2, wrap="word")
        style_text_widget(subliminal_text)
        subliminal_text.pack(fill="x", pady=(2, 8))
        tip(subliminal_text, TOOLTIPS["subliminal_box"])
        if existing.get("subliminal_messages"):
            subliminal_text.insert("1.0", "\n".join(existing["subliminal_messages"]))

        ttk.Label(card, text="Prompts for this mood (one per line) - 'type this to continue' commands.",
                  style="Muted.TLabel", wraplength=650, justify="left").pack(anchor="w")
        prompts_text = tk.Text(card, height=2, wrap="word")
        style_text_widget(prompts_text)
        prompts_text.pack(fill="x", pady=(2, 8))
        tip(prompts_text, TOOLTIPS["prompts_box"])
        if existing.get("prompts"):
            prompts_text.insert("1.0", "\n".join(existing["prompts"]))

        ttk.Label(card, text="Denial captions for this mood (one per line) - shown on 'not yet!' overlays.",
                  style="Muted.TLabel", wraplength=650, justify="left").pack(anchor="w")
        denial_text = tk.Text(card, height=2, wrap="word")
        style_text_widget(denial_text)
        denial_text.pack(fill="x", pady=(2, 8))
        tip(denial_text, TOOLTIPS["denial_box"])
        if existing.get("denial_captions"):
            denial_text.insert("1.0", "\n".join(existing["denial_captions"]))

        ttk.Label(card, text="Websites this mood can open (one per line). Optional extra words after a "
                              "'|' get randomly appended to the address, separated by commas - "
                              "e.g. https://example.com/search?q= | kittens, puppies",
                  style="Muted.TLabel", wraplength=650, justify="left").pack(anchor="w")
        web_text = tk.Text(card, height=2, wrap="word")
        style_text_widget(web_text)
        web_text.pack(fill="x", pady=(2, 8))
        tip(web_text, TOOLTIPS["web_box"])
        if existing.get("web_entries"):
            web_lines = []
            for w in existing["web_entries"]:
                line = w.get("url", "")
                if w.get("args"):
                    line += " | " + ", ".join(w["args"])
                web_lines.append(line)
            web_text.insert("1.0", "\n".join(web_lines))

        widgets = {"captions_text": captions_text, "notif_text": notif_text,
                   "subliminal_text": subliminal_text, "prompts_text": prompts_text,
                   "denial_text": denial_text, "web_text": web_text,
                   "wallpaper_var": None, "wallpaper_path": existing.get("wallpaper_path", ""),
                   "audio_var": None, "audio_paths": list(existing.get("audio_paths", [])),
                   "advanced_vars": {}, "remove_vars": {},
                   "media_files": list(existing.get("media_files", []))}

        wp_row = ttk.Frame(card)
        wp_row.pack(fill="x", pady=2)
        wp_var = BooleanVar(value=existing.get("wallpaper_change", False))
        wp_check = ttk.Checkbutton(wp_row, text="Wallpaper", variable=wp_var, width=12)
        wp_check.pack(side="left")
        tip(wp_check, TOOLTIPS["wallpaper_checkbox"])
        wp_name_label = ttk.Label(
            wp_row, text=(Path(widgets["wallpaper_path"]).name if widgets["wallpaper_path"] else "No image selected"),
            style="Muted.TLabel"
        )

        def choose_wp(w=widgets, lbl=wp_name_label):
            chosen = filedialog.askopenfilename(
                title=f"Choose wallpaper for mood '{mood_name}'",
                filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif")]
            )
            if chosen:
                w["wallpaper_path"] = chosen
                lbl.config(text=Path(chosen).name)

        wp_choose_btn = ttk.Button(wp_row, text="Choose Image...", command=choose_wp)
        wp_choose_btn.pack(side="left", padx=(8, 8))
        tip(wp_choose_btn, TOOLTIPS["wallpaper_choose"])
        wp_name_label.pack(side="left")

        def clear_wp(w=widgets, lbl=wp_name_label):
            w["wallpaper_path"] = ""
            lbl.config(text="No image selected")

        wp_clear_btn = ttk.Button(wp_row, text="Clear", command=clear_wp)
        wp_clear_btn.pack(side="left", padx=(8, 0))
        tip(wp_clear_btn, TOOLTIPS["wallpaper_clear"])
        widgets["wallpaper_var"] = wp_var

        # Only moods BEFORE this one can be removed when this one starts.
        earlier_moods = self.mood_names[:mood_index]
        if earlier_moods:
            rm_frame = ttk.Frame(card)
            rm_frame.pack(fill="x", pady=(4, 2))
            rm_label = ttk.Label(rm_frame, text="Remove these moods when this one starts:")
            rm_label.pack(anchor="w")
            tip(rm_label, TOOLTIPS["remove_moods"])
            rm_checks_row = ttk.Frame(card)
            rm_checks_row.pack(fill="x", padx=(10, 0), pady=(0, 4))
            saved_remove = set(existing.get("remove_moods", []))
            for name in earlier_moods:
                rv = BooleanVar(value=(name in saved_remove))
                rc = ttk.Checkbutton(rm_checks_row, text=name, variable=rv)
                rc.pack(side="left", padx=(0, 12))
                tip(rc, TOOLTIPS["remove_moods"])
                widgets["remove_vars"][name] = rv

        audio_row = ttk.Frame(card)
        audio_row.pack(fill="x", pady=2)
        audio_var = BooleanVar(value=existing.get("audio_enabled", False))
        audio_check = ttk.Checkbutton(audio_row, text="Audio", variable=audio_var, width=12)
        audio_check.pack(side="left")
        tip(audio_check, TOOLTIPS["audio_checkbox"])
        audio_names = [Path(p).name for p in widgets["audio_paths"]]
        audio_files_label = ttk.Label(
            audio_row, text=(f"{len(audio_names)} file(s): " + ", ".join(audio_names)) if audio_names else "No files selected",
            style="Muted.TLabel", wraplength=420, justify="left"
        )

        def add_audio(w=widgets, lbl=audio_files_label):
            chosen = filedialog.askopenfilenames(
                title=f"Add audio files for mood '{mood_name}' (multi-select allowed)",
                filetypes=[("Audio", "*.mp3 *.wav *.ogg *.flac")]
            )
            if chosen:
                w["audio_paths"].extend(chosen)
                names = [Path(p).name for p in w["audio_paths"]]
                lbl.config(text=f"{len(names)} file(s): " + ", ".join(names))

        audio_add_btn = ttk.Button(audio_row, text="Add Audio Files...", command=add_audio)
        audio_add_btn.pack(side="left", padx=(8, 8))
        tip(audio_add_btn, TOOLTIPS["audio_add"])
        audio_files_label.pack(side="left")

        def clear_audio(w=widgets, lbl=audio_files_label):
            w["audio_paths"] = []
            lbl.config(text="No files selected")

        audio_clear_btn = ttk.Button(audio_row, text="Clear", command=clear_audio)
        audio_clear_btn.pack(side="left", padx=(8, 0))
        tip(audio_clear_btn, TOOLTIPS["audio_clear"])
        widgets["audio_var"] = audio_var

        self._build_advanced_section(card, mood_name, widgets, existing.get("advanced", {}))

        self.mood_widgets[mood_name] = widgets

    def _build_advanced_section(self, card, mood_name, widgets, existing_advanced):
        state = {"expanded": False}

        toggle_btn = ttk.Button(card, text="\u25b8 Advanced Settings (optional)")
        toggle_btn.pack(anchor="w", pady=(6, 0))
        tip(toggle_btn, TOOLTIPS["advanced_toggle"])

        adv_frame = ttk.Frame(card)

        def toggle():
            if state["expanded"]:
                adv_frame.pack_forget()
                toggle_btn.config(text="\u25b8 Advanced Settings (optional)")
            else:
                adv_frame.pack(fill="x", pady=(6, 0), padx=(10, 0))
                toggle_btn.config(text="\u25be Advanced Settings (optional)")
            state["expanded"] = not state["expanded"]

        toggle_btn.config(command=toggle)

        ttk.Label(adv_frame, text=TOOLTIPS["advanced_note"], style="Muted.TLabel",
                  wraplength=600, justify="left").pack(anchor="w", pady=(0, 6))

        for group_name, fields in ADVANCED_FIELD_GROUPS:
            group = ttk.LabelFrame(adv_frame, text=group_name, padding=8)
            group.pack(fill="x", pady=4)
            for key, label, tooltip_text in fields:
                row = ttk.Frame(group)
                row.pack(fill="x", pady=1)
                ttk.Label(row, text=label, width=32).pack(side="left")
                initial = existing_advanced.get(key, "")
                var = StringVar(value=str(initial) if initial != "" else "")
                entry = ttk.Entry(row, textvariable=var, width=10)
                entry.pack(side="left")
                tip(entry, tooltip_text)
                widgets["advanced_vars"][key] = var

    # -- Sync + build ---------------------------------------------------------

    @staticmethod
    def _lines(text_widget: tk.Text) -> list:
        raw = text_widget.get("1.0", "end")
        return [line.strip() for line in raw.splitlines() if line.strip()]

    @staticmethod
    def _parse_advanced(advanced_vars: dict, mood_name: str, errors: list, strict: bool) -> dict:
        result = {}
        for key, var in advanced_vars.items():
            raw = var.get().strip()
            if not raw:
                continue
            try:
                val = float(raw)
                result[key] = int(val) if val.is_integer() else val
            except ValueError:
                if strict:
                    errors.append(f"'{mood_name}' -> {key}: '{raw}' isn't a number")
        return result

    @staticmethod
    def _parse_web_lines(text_widget: tk.Text) -> list:
        entries = []
        for line in PackBuilderApp._lines(text_widget):
            if "|" in line:
                url, args_part = line.split("|", 1)
                args = [a.strip() for a in args_part.split(",") if a.strip()]
                entries.append({"url": url.strip(), "args": args} if args else {"url": url.strip()})
            else:
                entries.append({"url": line.strip()})
        return entries

    def _sync_moods_into_plan(self, strict: bool) -> list:
        parse_errors = []
        mood_configs = {}
        for name, w in self.mood_widgets.items():
            advanced = self._parse_advanced(w["advanced_vars"], name, parse_errors, strict)
            remove_moods = [n for n, var in w["remove_vars"].items() if var.get()]
            mc = asdict(MoodConfig(
                name=name,
                captions=self._lines(w["captions_text"]),
                notifications=self._lines(w["notif_text"]),
                subliminal_messages=self._lines(w["subliminal_text"]),
                prompts=self._lines(w["prompts_text"]),
                denial_captions=self._lines(w["denial_text"]),
                web_entries=self._parse_web_lines(w["web_text"]),
                wallpaper_change=bool(w["wallpaper_var"].get()) if w["wallpaper_var"] else False,
                wallpaper_path=w["wallpaper_path"],
                audio_enabled=bool(w["audio_var"].get()),
                audio_paths=list(w["audio_paths"]),
                advanced=advanced,
                remove_moods=remove_moods,
                media_files=list(w.get("media_files", [])),
            ))
            mood_configs[name] = mc
        self.plan.mood_configs = mood_configs
        return parse_errors

    def _set_status(self, msg):
        # Called from the worker thread - only touch the StringVar (thread-
        # safe enough for this simple polling setup) rather than any widget.
        self.status_var.set(msg)

    def _collect_and_build(self):
        self._sync_step2_into_plan()
        parse_errors = self._sync_moods_into_plan(strict=True)

        if parse_errors:
            messagebox.showwarning(
                "Some Advanced Settings values aren't numbers",
                "Please fix these (or clear them):\n\n" + "\n".join(parse_errors)
            )
            return

        missing = [n for n, mc in self.plan.mood_configs.items() if mc["wallpaper_change"] and not mc["wallpaper_path"]]
        if missing:
            messagebox.showwarning(
                "Missing wallpaper image",
                f"These moods have 'Wallpaper' checked but no image chosen: {', '.join(missing)}\n"
                f"Pick an image or uncheck them before building."
            )
            return

        project_dir = filedialog.askdirectory(title="Choose (or create) ONE folder to build this pack in")
        if not project_dir:
            return
        project_dir = Path(project_dir)

        out_dir = project_dir / "pack_source"
        build_dir = project_dir / "pack_build"
        safe_name = "".join(c if (c.isalnum() or c in " -_") else "_" for c in self.plan.pack_name).strip() or "pack"
        zip_path = project_dir / f"{safe_name}.zip"

        self.build_btn.config(state="disabled")
        self.progress.pack(fill="x", pady=(4, 2))
        self.status_label.pack(anchor="w", pady=(0, 8))
        self.progress.start(12)
        self.status_var.set("Starting...")

        self._build_result = {"done": False, "error": None, "zip_path": None, "no_compiler": False,
                               "out_dir": out_dir, "warn_stdout": ""}

        def worker():
            try:
                write_pack_source(self.plan, out_dir, status_cb=self._set_status)

                if not self.plan.pack_tool_dir:
                    self._build_result["no_compiler"] = True
                    self._build_result["done"] = True
                    return

                _, stdout, stderr = compile_with_pack_tool(
                    Path(self.plan.pack_tool_dir), out_dir, build_dir,
                    self.plan.compress_images, self.plan.compress_videos, self.plan.rename_media,
                    status_cb=self._set_status
                )
                self._build_result["warn_stdout"] = stdout or ""

                # The compiler only writes the raw pack files - it doesn't know
                # about plan.json, so copy it in ourselves before zipping. This
                # is what lets anyone who downloads the finished .zip load it
                # back into this editor with an exact (not reconstructed) match.
                plan_json_src = out_dir / "plan.json"
                if plan_json_src.is_file():
                    shutil.copy2(plan_json_src, build_dir / "plan.json")

                zip_directory(build_dir, zip_path, status_cb=self._set_status)
                self._build_result["zip_path"] = zip_path
            except Exception as e:
                self._build_result["error"] = str(e)
            finally:
                self._build_result["done"] = True

        self._build_thread = threading.Thread(target=worker, daemon=True)
        self._build_thread.start()
        self.root.after(150, self._poll_build, out_dir)

    def _poll_build(self, out_dir):
        if not self._build_result.get("done"):
            self.root.after(150, self._poll_build, out_dir)
            return

        self.progress.stop()
        self.progress.pack_forget()
        self.status_label.pack_forget()
        self.build_btn.config(state="normal")

        err = self._build_result.get("error")
        if err:
            messagebox.showerror("Build failed", err)
            return

        if self._build_result.get("no_compiler"):
            messagebox.showinfo(
                "Pack source ready",
                f"Wrote pack.yml + arranged media/ to:\n{out_dir}\n\n"
                f"No Pack Tool folder was set, so you'll need to compile it yourself "
                f"(PackToolScript.bat -> option 3, pointed at that folder)."
            )
            return

        zip_path = self._build_result.get("zip_path")
        stdout = self._build_result.get("warn_stdout", "")
        warn_note = ""
        if stdout and ("WARNING" in stdout or "ERROR" in stdout):
            warn_note = "\n\nNote: the compiler logged some warnings - worth a skim if anything looks off in-game."
        yaml_note = "" if HAVE_YAML else "\n\n(PyYAML wasn't installed - pack.yml was written with a minimal fallback writer.)"
        messagebox.showinfo(
            "Pack built!",
            f"Finished pack:\n{zip_path}\n\n"
            f"(pack_source/ and pack_build/ inside that same folder are working files - "
            f"safe to delete once you've confirmed the zip works.){warn_note}{yaml_note}"
        )


def main():
    root = tk.Tk()
    PackBuilderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
