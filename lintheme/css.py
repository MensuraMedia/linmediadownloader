"""
CSS for GTK 3 or GTK 4, generated from tokens.py.

Every class starts with `lt-` so an app's own CSS never collides with the kit's.
The two toolkits read almost the same CSS; the differences that matter, found
by rendering the mockups in both (docs/04-CSS.md), are:

| What | GTK 3.24 | GTK 4.14 |
|---|---|---|
| Keyboard focus ring | `:focus` + outline longhands | `:focus-visible` + `outline` shorthand |
| Theme gradients on buttons | must be cleared: `background-image: none` | same (harmless) |
| Text shadows from the theme | must be cleared: `text-shadow: none` | none by default |
| Symbolic icons follow `color` | `-gtk-icon-style: symbolic` | default |
| CSS custom properties (`var()`) | not supported | only from 4.16 (Mint 22 has 4.14) |

So values are substituted here, in Python, rather than with CSS variables.
"""

import re

from lintheme import tokens

C = tokens.COLOR
R = tokens.RADIUS
S = tokens.SIZE
T = tokens.TYPE


def _type(name):
    size, line, weight = T[name]
    return f"font-size: {size}px; font-weight: {weight};"


def _common():
    """Rules both toolkits read the same way"""
    f = tokens.FONT
    return f"""
/* ---- base ---- */
.lt-root, .lt-root window, window.lt-root {{
  background-color: {C['bg']}; color: {C['text']};
  font-family: "{f['family']}", {f['fallback']}; font-size: {T['body'][0]}px;
}}
.lt-display {{ {_type('display')} }}
.lt-title {{ {_type('title')} }}
.lt-heading {{ {_type('heading')} }}
.lt-muted {{ color: {C['text_muted']}; font-size: 13px; }}
.lt-caption {{ color: {C['text_muted']}; {_type('caption')} }}
.lt-mono {{ font-family: "{f['mono']}", monospace; font-size: 13px; color: {C['text_muted']}; }}
.lt-strong {{ font-weight: 500; }}
.lt-ok-text {{ color: {C['ok']}; font-weight: 500; }}
.lt-busy-text {{ color: {C['busy']}; font-weight: 500; }}
.lt-attention-text {{ color: {C['attention']}; font-weight: 500; }}
.lt-error-text {{ color: {C['error']}; font-weight: 500; }}

/* ---- shell: header, rail, pages, action bar ---- */
.lt-header {{
  background-image: none; background-color: {C['surface']}; color: {C['text']};
  border-bottom: 1px solid {C['border']}; min-height: {S['header']}px; padding: 0 12px; box-shadow: none;
}}
.lt-brand {{ {_type('heading')} }}
.lt-brand-icon {{ color: {C['accent']}; }}
.lt-crumb {{ color: {C['text_muted']}; font-size: 16px; }}
.lt-rail {{ background-color: {C['rail']}; border-right: 1px solid {C['border']}; padding: 10px 8px; }}
.lt-rail-item {{
  background-image: none; background-color: transparent; border: none; border-radius: {R['card']}px;
  min-height: 68px; min-width: {S['rail'] - 16}px; color: {C['text_muted']}; box-shadow: none; padding: 4px;
}}
.lt-rail-item:hover {{ background-color: {C['surface']}; color: {C['text']}; }}
.lt-rail-item.lt-active {{ background-color: {C['accent_soft']}; color: {C['accent']}; box-shadow: inset 0 0 0 2px {C['accent']}; }}
.lt-rail-item label {{ font-size: 12px; font-weight: 500; }}
.lt-rail.lt-compact .lt-rail-item {{ min-width: {S['rail_compact'] - 16}px; min-height: 60px; }}
.lt-header button.titlebutton {{ background-image: none; background-color: transparent; border: none; box-shadow: none; color: {C['text_muted']}; }}
.lt-header button.titlebutton:hover {{ background-color: {C['surface_hover']}; color: {C['text']}; }}
.lt-rail-item .lt-badge, .lt-badge {{
  background-color: {C['busy']}; color: {C['bg']}; border-radius: 9px; min-width: 18px; min-height: 18px;
  font-size: 11px; font-weight: 700; padding: 0 4px;
}}
.lt-page {{ padding: 22px 28px; }}
.lt-pane {{ padding: 18px 20px; }}
.lt-pane-divider {{ border-left: 1px solid {C['border']}; }}
.lt-actionbar {{
  background-color: {C['surface']}; border-top: 1px solid {C['border']}; padding: 0 24px; min-height: {S['actionbar']}px;
}}

/* ---- containers ---- */
.lt-card {{ background-color: {C['surface']}; border: 1px solid {C['border']}; border-radius: {R['card']}px; padding: 14px 16px; }}
.lt-card.lt-large {{ padding: 20px 24px; }}
.lt-hero {{ background-color: {C['surface']}; border: 1px solid {C['border']}; border-radius: {R['dialog']}px; padding: 20px 24px; }}
.lt-hero.lt-error {{ background-color: {C['error_bg']}; border-color: {C['error']}; }}
.lt-hero.lt-attention {{ background-color: {C['attention_bg']}; border-color: {C['attention']}; }}
.lt-hero-icon {{ border-radius: 30px; min-width: 60px; min-height: 60px; border: 2px solid {C['ok']}; background-color: {C['ok_bg']}; color: {C['ok']}; }}
.lt-hero-icon.lt-error {{ border-color: {C['error']}; background-color: {C['surface']}; color: {C['error']}; }}
.lt-hero-icon.lt-attention {{ border-color: {C['attention']}; background-color: {C['surface']}; color: {C['attention']}; }}
.lt-hero-icon.lt-busy {{ border-color: {C['busy']}; background-color: {C['surface']}; color: {C['busy']}; }}
.lt-icon-tile {{ background-color: {C['accent_soft']}; color: {C['accent']}; border-radius: {R['card']}px; min-width: 44px; min-height: 44px; }}
.lt-empty-icon {{ background-color: {C['accent_soft']}; color: {C['accent']}; border-radius: 36px; min-width: 72px; min-height: 72px; }}
flowboxchild {{ padding: 0; }}
.lt-divider {{ background-color: {C['border']}; min-height: 1px; }}
.lt-field-label {{ color: {C['text_muted']}; min-width: 84px; }}
.lt-dropzone {{ border: 2px dashed {C['border_strong']}; border-radius: {R['card']}px; padding: 18px; }}

/* ---- buttons ---- */
.lt-btn {{
  background-image: none; background-color: {C['surface']}; color: {C['text']};
  border: 1px solid {C['border_strong']}; border-radius: {R['control']}px;
  min-height: {S['frequent'] - 2}px; padding: 0 14px; box-shadow: none;
}}
.lt-btn:hover {{ background-color: {C['surface_hover']}; }}
.lt-btn.lt-small {{ min-height: {S['target_min'] - 2}px; padding: 0 12px; font-size: 13px; }}
.lt-btn.lt-primary {{ background-color: {C['accent']}; border-color: {C['accent']}; color: {C['on_accent']}; font-weight: 500; }}
.lt-btn.lt-primary:hover {{ background-color: {C['accent_hover']}; }}
.lt-btn.lt-big {{ min-height: {S['primary'] - 2}px; min-width: 160px; padding: 0 24px; font-size: 16px; }}
.lt-btn.lt-danger {{ color: {C['error']}; border-color: {C['error']}; font-weight: 500; }}
.lt-btn.lt-danger.lt-filled {{ background-color: {C['error']}; color: {C['bg']}; }}
.lt-btn:disabled {{ background-color: transparent; color: {C['text_muted']}; border-style: dashed; border-color: {C['border_strong']}; }}
.lt-link {{ background-image: none; background-color: transparent; border: none; box-shadow: none; color: {C['accent']}; font-weight: 500; padding: 0 6px; min-height: {S['target_min']}px; }}
.lt-link label {{ text-decoration-line: underline; }}
.lt-icon-btn {{ background-image: none; background-color: transparent; border: 1px solid transparent; box-shadow: none; color: {C['text']}; min-width: {S['frequent']}px; min-height: {S['frequent']}px; border-radius: {R['control']}px; }}
.lt-icon-btn:hover {{ background-color: {C['surface_hover']}; }}
.lt-list-btn {{ background-image: none; background-color: {C['surface']}; border: 1px solid {C['border']}; border-radius: {R['control']}px; padding: 6px 12px; box-shadow: none; color: {C['text']}; min-height: 46px; }}
.lt-list-btn:hover {{ border-color: {C['border_strong']}; }}

/* ---- status chip ---- */
.lt-chip {{
  background-image: none; border-radius: 18px; min-height: 34px; padding: 0 14px; color: {C['text']};
  font-weight: 500; box-shadow: none; border: 1px solid {C['border_strong']}; background-color: {C['surface']};
}}
.lt-chip.lt-ok {{ background-color: {C['ok_bg']}; border-color: {C['ok']}; }}
.lt-chip.lt-busy {{ background-color: {C['busy_bg']}; border-color: {C['busy']}; }}
.lt-chip.lt-attention {{ background-color: {C['attention_bg']}; border-color: {C['attention']}; }}
.lt-chip.lt-error {{ background-color: {C['error_bg']}; border-color: {C['error']}; }}

/* ---- choices ---- */
/* separate buttons, never joined: each has its own border and corners (the user's rule, 2026-10-10) */
.lt-seg {{ border: none; background: none; }}
.lt-seg button {{
  background-image: none; background-color: {C['surface']}; color: {C['text']};
  border: 1px solid {C['border_strong']}; border-radius: {R['control']}px;
  min-height: {S['control'] - 2}px; padding: 0 14px; box-shadow: none;
}}
.lt-seg button:hover {{ background-color: {C['surface_hover']}; }}
.lt-seg button:checked {{
  background-color: {C['accent']}; border-color: {C['accent']}; color: {C['on_accent']}; font-weight: 500;
}}
.lt-seg button:disabled {{ color: {C['text_muted']}; }}
.lt-seg button:checked:disabled {{ background-color: {C['accent_soft']}; color: {C['text_muted']}; }}
.lt-seg label.lt-value {{ min-width: 44px; }}
.lt-select button, button.lt-select {{
  background-image: none; background-color: {C['surface']}; color: {C['text']};
  border: 1px solid {C['border_strong']}; border-radius: {R['control']}px; min-height: {S['control'] - 2}px; box-shadow: none;
}}
.lt-select button:disabled, button.lt-select:disabled {{ color: {C['text_muted']}; border-style: dashed; }}
.lt-entry:disabled, entry.lt-entry:disabled {{ color: {C['text_muted']}; border-style: dashed; }}
.lt-entry, entry.lt-entry {{
  background-image: none; background-color: {C['surface']}; color: {C['text']};
  border: 1px solid {C['border_strong']}; border-radius: {R['control']}px; min-height: {S['control'] - 2}px; padding: 0 10px;
}}
.lt-entry.lt-invalid, entry.lt-invalid {{ border: 2px solid {C['error']}; }}
switch {{ background-image: none; background-color: {C['bg']}; border: 1px solid {C['border_strong']}; border-radius: 12px; }}
switch slider {{ background-image: none; background-color: {C['border_strong']}; border: none; border-radius: 9px; min-width: 18px; min-height: 18px; box-shadow: none; }}
switch:checked {{ background-color: {C['accent']}; border-color: {C['accent']}; }}
switch:checked slider {{ background-color: {C['on_accent']}; }}

/* ---- feedback ---- */
.lt-banner {{ border-radius: 8px; padding: 10px 12px; border: 1px solid {C['border_strong']}; background-color: {C['surface']}; }}
.lt-banner.lt-ok {{ background-color: {C['ok_bg']}; border-color: {C['ok']}; }}
.lt-banner.lt-busy {{ background-color: {C['busy_bg']}; border-color: {C['busy']}; }}
.lt-banner.lt-attention {{ background-color: {C['attention_bg']}; border-color: {C['attention']}; }}
.lt-banner.lt-error {{ background-color: {C['error_bg']}; border-color: {C['error']}; }}
.lt-pill {{ border-radius: 12px; padding: 2px 10px; font-size: 12.5px; border: 1px solid {C['border_strong']}; }}
.lt-pill.lt-ok {{ background-color: {C['ok_bg']}; border-color: {C['ok']}; }}
.lt-pill.lt-error {{ background-color: {C['error_bg']}; border-color: {C['error']}; }}
.lt-pill.lt-attention {{ background-color: {C['attention_bg']}; border-color: {C['attention']}; }}
.lt-pill.lt-busy {{ background-color: {C['busy_bg']}; border-color: {C['busy']}; }}
.lt-ok-icon {{ color: {C['ok']}; }}
.lt-busy-icon {{ color: {C['busy']}; }}
.lt-attention-icon {{ color: {C['attention']}; }}
.lt-error-icon {{ color: {C['error']}; }}
.lt-done-mark {{ border-radius: 22px; min-width: 44px; min-height: 44px; border: 2px solid {C['ok']}; background-color: {C['ok_bg']}; color: {C['ok']}; }}
progressbar trough {{ background-image: none; background-color: {C['border']}; border: none; border-radius: 4px; min-height: 8px; }}
progressbar progress {{ background-image: none; background-color: {C['busy']}; border: none; border-radius: 4px; min-height: 8px; }}

/* ---- steps (guided troubleshooting) ---- */
.lt-step {{ border-radius: 20px; padding: 0 12px; min-height: 40px; border: 1px solid {C['border']}; font-size: 13px; }}
.lt-step.lt-now {{ background-color: {C['accent_soft']}; border-color: {C['accent']}; font-weight: 500; }}
.lt-step.lt-next {{ color: {C['text_muted']}; }}
.lt-step-num {{ border-radius: 11px; min-width: 22px; min-height: 22px; font-size: 12px; background-color: {C['accent']}; color: {C['on_accent']}; }}
.lt-step.lt-next .lt-step-num {{ background-color: transparent; color: {C['text_muted']}; border: 1px solid {C['border_strong']}; }}

/* ---- lists and keys ---- */
.lt-row {{ border-bottom: 1px solid {C['border']}; min-height: 52px; }}
.lt-thead {{ border-bottom: 1px solid {C['border']}; color: {C['text_muted']}; font-size: 12.5px; }}
.lt-kbd {{ font-family: "{f['mono']}", monospace; font-size: 12px; border: 1px solid currentColor; border-radius: 4px; padding: 0 5px; }}
.lt-thumb {{ background-image: none; background-color: {tokens.PAPER['sheet']}; color: {tokens.PAPER['ink']}; border: 1px solid {C['border_strong']}; border-radius: 3px; min-width: 50px; min-height: 66px; box-shadow: none; padding: 0; }}
.lt-thumb.lt-active {{ box-shadow: 0 0 0 3px {C['bg']}, 0 0 0 5px {C['accent']}; font-weight: 700; }}
.lt-dialog {{ background-color: {C['surface']}; color: {C['text']}; }}
"""


def _gtk3():
    return f"""
/* ---- GTK 3 specifics ---- */
* {{ -gtk-icon-style: symbolic; }}
.lt-root button {{ text-shadow: none; -gtk-icon-shadow: none; }}
.lt-root button:focus, .lt-root switch:focus, .lt-root entry:focus {{
  outline-color: {C['focus']}; outline-style: solid; outline-width: 2px; outline-offset: 2px;
}}
"""


def _gtk4():
    return f"""
/* ---- GTK 4 specifics ---- */
.lt-root button:focus-visible, .lt-root switch:focus-visible, .lt-root entry:focus-within {{
  outline: 2px solid {C['focus']}; outline-offset: 2px;
}}
/* Gtk.DropDown as lt-select: its inner toggle is a `button`, so the shared .lt-select rules
   style it; the focusable outer `dropdown` node needs the ring, the padding and the
   disabled colour itself (there is no Gtk.ComboBox in GTK 4) */
.lt-root dropdown:focus-visible {{
  outline: 2px solid {C['focus']}; outline-offset: 2px;
}}
dropdown.lt-select > button {{ padding: 0 14px; }}
dropdown.lt-select:disabled {{ color: {C['text_muted']}; }}
"""


def build_css(toolkit=3):
    """The whole stylesheet for GTK `toolkit` (3 or 4)"""
    if toolkit not in (3, 4):
        raise ValueError("toolkit must be 3 or 4")
    return _common() + (_gtk3() if toolkit == 3 else _gtk4())


CLASSES = sorted(set(re.findall(r"\.(lt-[a-z0-9-]+)", _common())))  # every class the kit styles
