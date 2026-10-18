"""CSS: generated for both toolkits, parses with zero errors in real GTK 3 and GTK 4"""

import os
import subprocess
import sys

import pytest
from conftest import ROOT, requires_display

from lintheme import css, tokens

KEY_CLASSES = (
    "lt-chip",
    "lt-rail-item",
    "lt-card",
    "lt-seg",
    "lt-banner",
    "lt-actionbar",
    "lt-btn",
    "lt-step",
)


@pytest.mark.parametrize("toolkit", [3, 4])
def test_css_has_every_key_class_and_no_css_variables(toolkit):
    text = css.build_css(toolkit)
    for cls in KEY_CLASSES:
        assert "." + cls in text
    assert "var(" not in text  # GTK 4.14 (Mint 22) has no CSS variables; values are substituted
    assert tokens.COLOR["accent"] in text


def test_focus_rules_differ_by_toolkit():
    assert ":focus-visible" in css.build_css(4) and ":focus-visible" not in css.build_css(3)
    assert "outline-style" in css.build_css(3)


def test_unknown_toolkit_is_refused():
    with pytest.raises(ValueError):
        css.build_css(5)


@requires_display
@pytest.mark.parametrize("toolkit", [3, 4])
def test_css_parses_without_errors_in_real_gtk(toolkit):
    """GTK 3 and GTK 4 can't share a process, so each runs in its own"""
    code = (
        f"import sys; sys.path.insert(0, {ROOT!r}); import gi; gi.require_version('Gtk', '{toolkit}.0');"
        "from gi.repository import Gtk;"
        + ("Gtk.init();" if toolkit == 4 else "")
        + "from lintheme import apply; errs = []; apply.install(None, errs); print(len(errs)); print(errs[:5])"
    )
    env = dict(os.environ, GSK_RENDERER="cairo")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines()[0] == "0", r.stdout
