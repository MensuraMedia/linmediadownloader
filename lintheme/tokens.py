"""
Design tokens: the single source for colour, type, space, size, shape and motion.

One theme, Graphite Night. Everything else in lintheme (the CSS for GTK 3 and
GTK 4, the components, the docs' tables, the contrast test) reads these values;
nothing else hard-codes a colour. Two kinds of colour are deliberately NOT
themed: ink-cartridge colours (INK) and the paper of a preview (PAPER), because
they stand for physical things.

Contrast (WCAG 2.2, checked by tests/test_tokens.py and tools/contrast.py):
text and muted text >= 4.5:1 on every surface they sit on; control borders,
focus ring and accent >= 3:1; status colours >= 4.5:1 on the surface.
"""

NAME = "Graphite Night"

COLOR = {
    "bg": "#1c1f23",  # window background
    "surface": "#262a30",  # cards, header bar, action bar
    "surface_hover": "#2f343b",  # hovered button on a surface
    "rail": "#17191d",  # navigation rail
    "border": "#3a4048",  # dividers and card edges (decorative)
    "border_strong": "#7d8590",  # control outlines (3:1 required)
    "text": "#eceff3",
    "text_muted": "#aab2bd",
    "accent": "#4c9dff",  # primary button, selection, links
    "accent_hover": "#6aaeff",  # hovered primary button
    "on_accent": "#0b1320",  # text on accent
    "accent_soft": "#1f3350",  # selected nav item, icon tiles
    "focus": "#ffd75e",  # focus ring
    "ok": "#5fd38d",
    "ok_bg": "#1d3a2a",
    "busy": "#7cb7ff",
    "busy_bg": "#1f3350",
    "attention": "#ffbf4d",
    "attention_bg": "#3d3220",
    "error": "#ff8a80",
    "error_bg": "#3f2422",
}

# Physical colours: never themed
INK = {"cyan": "#00a3e0", "magenta": "#e5007e", "yellow": "#ffd400", "black": "#16181a"}
PAPER = {"sheet": "#ffffff", "margin": "#e8ecea", "guide": "#9aa5a0", "edge": "#b9c2be", "ink": "#1b2420"}

FONT = {"family": "Ubuntu", "mono": "Ubuntu Mono", "fallback": "sans-serif"}

# name: (size px, line height px, weight)
TYPE = {
    "display": (28, 36, 500),
    "title": (20, 28, 500),
    "heading": (16, 24, 500),
    "body": (14, 21, 400),
    "caption": (12, 18, 400),
}

SPACE = (4, 8, 12, 16, 24, 32, 48)

RADIUS = {"control": 6, "card": 10, "dialog": 14, "pill": 999}

SIZE = {
    "target_min": 32,  # nothing interactive is smaller (WCAG 2.2 floor is 24)
    "control": 36,  # segmented choices, selects, inputs
    "frequent": 40,  # everyday buttons
    "primary": 48,  # the one main action per view (Print, Scan, Copy…)
    "header": 52,
    "rail": 88,
    "rail_compact": 72,
    "actionbar": 84,
    "icon": 20,
    "icon_nav": 24,
}

LAYOUT = {"min_width": 720, "min_height": 540, "two_pane": 960, "options_min": 380, "options_max": 476}

MOTION = {"state_ms": 120, "panel_ms": 200}  # 0 when the system turns animations off

# (foreground role, background role, minimum ratio): the pairs the UI actually uses
CONTRAST_PAIRS = (
    ("text", "bg", 4.5),
    ("text", "surface", 4.5),
    ("text_muted", "surface", 4.5),
    ("text_muted", "bg", 4.5),
    ("text", "rail", 4.5),
    ("text_muted", "rail", 4.5),
    ("on_accent", "accent", 4.5),
    ("on_accent", "accent_hover", 4.5),
    ("accent", "surface", 3.0),
    ("accent", "accent_soft", 3.0),
    ("text_muted", "accent_soft", 4.5),  # a disabled selected segment
    ("border_strong", "surface", 3.0),
    ("border_strong", "bg", 3.0),
    ("focus", "bg", 3.0),
    ("focus", "surface", 3.0),
    ("ok", "surface", 4.5),
    ("busy", "surface", 4.5),
    ("attention", "surface", 4.5),
    ("error", "surface", 4.5),
    ("text", "ok_bg", 4.5),
    ("text", "busy_bg", 4.5),
    ("text", "attention_bg", 4.5),
    ("text", "error_bg", 4.5),
)


def luminance(hex_color):
    """WCAG relative luminance of '#rrggbb'"""
    h = hex_color.lstrip("#")
    channels = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(fg, bg):
    """WCAG contrast ratio between two '#rrggbb' colours"""
    a, b = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def contrast_report():
    """[(fg role, bg role, ratio, minimum)] for every pair the UI uses"""
    return [(f, b, contrast(COLOR[f], COLOR[b]), need) for f, b, need in CONTRAST_PAIRS]
