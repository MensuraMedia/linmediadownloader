"""Tokens: every colour pair the UI uses meets WCAG 2.2 AA; sizes respect the accessibility floor"""

import re

from lintheme import tokens


def test_every_pair_meets_its_minimum():
    failures = [(f, b, round(r, 2), n) for f, b, r, n in tokens.contrast_report() if r < n]
    assert failures == []


def test_colours_are_hex():
    for name, value in {**tokens.COLOR, **tokens.INK, **tokens.PAPER}.items():
        assert re.fullmatch(r"#[0-9a-f]{6}", value), name


def test_contrast_function_known_values():
    assert round(tokens.contrast("#000000", "#ffffff"), 1) == 21.0
    assert tokens.contrast("#123456", "#123456") == 1.0


def test_text_never_below_12_px_and_targets_never_below_wcag():
    assert min(size for size, _line, _w in tokens.TYPE.values()) >= 12
    assert tokens.SIZE["target_min"] >= 24  # WCAG 2.2 SC 2.5.8 floor
    assert (
        tokens.SIZE["primary"] > tokens.SIZE["frequent"] > tokens.SIZE["control"] >= tokens.SIZE["target_min"]
    )


def test_one_theme_only():
    assert tokens.NAME == "Graphite Night"
