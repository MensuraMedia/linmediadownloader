"""Status vocabulary and the message pattern"""

import pytest

from lintheme import icons, status


def test_four_states_plus_none_each_with_word_and_icon():
    assert [status.status(k).word for k in ("ok", "busy", "attention", "error")] == [
        "Ready",
        "Busy",
        "Needs you",
        "Can't reach",
    ]
    bundled = set(icons.names())
    for st in status.STATUSES.values():
        assert st.icon in bundled, st.icon
        assert st.css.startswith("lt-")


def test_chip_text():
    assert status.chip_text("Canon TR150", "ok") == "Canon TR150 · Ready"
    assert status.chip_text("", "error") == "Can't reach"


def test_message_pattern():
    msg = status.message(
        "The printer keeps dropping off USB", "14 errors on port 3-3", "Try another USB cable first"
    )
    assert msg == "The printer keeps dropping off USB. 14 errors on port 3-3. Try another USB cable first."


def test_problems_catch_dark_patterns_and_raw_codes():
    assert status.problems("Load paper in the rear tray, then press Print.") == []
    assert any("urgency" in p for p in status.problems("Act now: ink critical!"))
    assert status.problems("USB error -71 EPROTO")
    assert status.problems("FAILED")


def test_cable_first_advice_names_the_cable():
    assert "cable" in status.CABLE_FIRST and "No driver" in status.CABLE_FIRST


def test_app_icon_dirs_extend_the_kit(tmp_path):
    (tmp_path / "app-only.svg").write_text(open(icons._path("check")).read())
    with pytest.raises(FileNotFoundError):
        icons._path("app-only")
    icons.add_icon_dir(str(tmp_path))
    try:
        assert "app-only" in icons.names() and "check" in icons.names()
        assert icons._path("check").startswith(icons.ICON_DIR)  # the kit's own icons win
        assert icons.pixbuf("app-only", 20).get_width() == 20
    finally:
        icons._dirs.remove(str(tmp_path))
        icons.pixbuf.cache_clear()
