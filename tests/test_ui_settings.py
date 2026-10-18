#!/usr/bin/env python3
# tests/test_ui_settings.py
# The Settings page with faked tools, browser discovery and a throwaway settings
# file. Skips without a display; never the real browsers, the real settings
# file, the network or a real yt-dlp update.

import sys
import threading
import time

import pytest
from conftest import requires_display

pytestmark = requires_display

gi = pytest.importorskip("gi")
if "gi.repository.Gtk" in sys.modules:
    if sys.modules["gi.repository.Gtk"].get_major_version() != 4:
        pytest.skip("Gtk 3.0 already loaded in this process", allow_module_level=True)
gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

from modules import tools  # noqa: E402
from modules.config import user_settings  # noqa: E402
from modules.download import access  # noqa: E402
from ui import messages  # noqa: E402
from ui.pages import settings as settings_module  # noqa: E402
from ui.window import MainWindow  # noqa: E402

PROFILE_PATH = "/home/user/.librewolf/30nh4ac4.default-default"


class FakeFile:
    def __init__(self, path):
        self.path = path

    def get_path(self):
        return self.path


class FakeFolderDialog:
    """What Gtk.FileDialog.select_folder_finish returns, without a dialog"""

    def __init__(self, path):
        self.file = FakeFile(path)

    def select_folder_finish(self, _result):
        return self.file


def wait_until(condition, timeout=5.0):
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "condition never became true"
        GLib.MainContext.default().iteration(False)
        time.sleep(0.005)


@pytest.fixture(scope="module")
def app():
    Gtk.init()
    from ui.app import App

    application = App(
        application_id="org.mensuramedia.LinMediaDownloaderTests."
        + __name__.rsplit(".", 1)[-1].replace("_", "")
    )
    application.register(None)
    return application


@pytest.fixture(autouse=True)
def fake_backends(monkeypatch, tmp_path):
    """A throwaway settings file and instant, offline tools and discovery"""
    monkeypatch.setattr(user_settings, "SETTINGS_FILE", str(tmp_path / "app_settings.json"))
    user_settings._settings = user_settings._defaults()
    monkeypatch.setattr(tools, "ytdlp_version", lambda: "2026.09.01")
    monkeypatch.setattr(tools, "ffmpeg_version", lambda: ("6.1.1-static", "/usr/bin/ffmpeg"))
    monkeypatch.setattr(tools, "can_update_ytdlp", lambda: True)
    updates = []
    monkeypatch.setattr(
        tools,
        "update_ytdlp",
        lambda: updates.append(threading.get_ident())
        or {
            "ok": True,
            "before": "2026.09.01",
            "after": "2026.10.09",
            "output": "",
        },
    )
    diagnostics = []
    monkeypatch.setattr(
        tools,
        "save_diagnostics",
        lambda path: diagnostics.append(path) or path,
    )
    profile = access.Profile("LibreWolf", "firefox", PROFILE_PATH, "", running=True, signed_in=True)
    monkeypatch.setattr(access, "discover_profiles", lambda: [profile])
    in_use = access.Access(profile, {"deno": {"path": "/usr/bin/deno"}})
    monkeypatch.setattr(access, "current", lambda refresh=False: in_use)
    yield {
        "updates": updates,
        "diagnostics": diagnostics,
        "profile": profile,
    }
    user_settings._settings = user_settings._defaults()


@pytest.fixture()
def window(app):
    win = MainWindow(app)
    yield win
    win.destroy()


@pytest.fixture()
def page(window):
    return window.settings_page


def label_texts(container):
    out, stack = [], [container]
    while stack:
        widget = stack.pop()
        if isinstance(widget, Gtk.Label):
            out.append(widget.get_text())
        child = widget.get_first_child() if hasattr(widget, "get_first_child") else None
        while child:
            stack.append(child)
            child = child.get_next_sibling()
    return out


def test_folder_change_saves_and_the_download_page_follows(page, window, tmp_path):
    folder = tmp_path / "elsewhere"
    folder.mkdir()
    page._folder_chosen(FakeFolderDialog(str(folder)), None)
    assert user_settings.get_settings()["download_folder"] == str(folder)
    assert window.download_page.folder == str(folder)  # the defaults arrived
    assert page.folder_label.get_text().endswith("elsewhere")


def test_unwritable_folder_is_refused_with_the_reason(page, tmp_path, monkeypatch):
    before = user_settings.get_settings()["download_folder"]
    monkeypatch.setattr(page, "_folder_writable", staticmethod(lambda _path: False))
    page._folder_chosen(FakeFolderDialog("/no/such/place"), None)
    assert user_settings.get_settings()["download_folder"] == before
    assert messages.SET_FOLDER_DENIED in label_texts(page)


def test_use_default_clears_the_custom_folder(page, tmp_path):
    folder = tmp_path / "chosen"
    folder.mkdir()
    page._folder_chosen(FakeFolderDialog(str(folder)), None)
    assert page.use_default.get_visible() is True
    page._use_default()
    assert user_settings.get_settings()["download_folder"] == ""
    assert page.use_default.get_visible() is False


def test_format_quality_and_minutes_save_as_made(page):
    page._save_format("video")
    page._save_quality("480")
    page._save_minutes(12)
    values = user_settings.get_settings()
    assert values["download_type"] == "video"
    assert values["video_quality"] == "480"
    assert values["long_minutes"] == 12
    assert window_follows(page)  # the Download page picked the new defaults up


def window_follows(page):
    download = page.window.download_page
    return download.download_type == "video" and download.quality == "480"


def test_filler_word_add_and_remove(page):
    words = lambda: user_settings.get_settings()["filler_words"]  # noqa: E731
    page.word_entry.set_text("extraword")
    page._add_word()
    assert "extraword" in words()
    page._remove_word("extraword")
    assert "extraword" not in words()
    assert messages.SET_WORD_ADDED in label_texts(page)


def test_replacement_add_and_remove(page):
    rows = lambda: user_settings.get_settings()["char_replacements"]  # noqa: E731
    page.new_from.set_text("&")
    page.new_to.set_text("and")
    page._add_replacement()
    assert rows() == [{"from": "&", "to": "and"}]
    page._remove_replacement(0)
    assert rows() == []


def test_reset_asks_before_restoring_defaults(page, monkeypatch):
    user_settings.save_settings({"filler_words": ["a", "b"], "char_replacements": [{"from": "x", "to": "y"}]})
    asked = {}

    def fake_confirm(_parent, title, _body, _label, **kwargs):
        asked["title"] = title
        asked["yes"] = kwargs.get("on_answer")

    monkeypatch.setattr(settings_module.kit, "confirm", fake_confirm)
    page._confirm_reset()
    assert messages.SET_RESET_TITLE in asked["title"]
    asked["yes"](True)
    values = user_settings.get_settings()
    assert values["filler_words"] == sorted(user_settings.DEFAULT_FILLER_WORDS)
    assert values["char_replacements"] == []


def test_signin_dropdown_saves_auto_profile_and_off(page, fake_backends):
    page._refresh_signin_options([fake_backends["profile"]])
    page._save_signin("off")
    assert user_settings.get_settings()["browser_access"] == "off"
    wait_until(lambda: messages.SET_SIGNIN_OFF_NOW in label_texts(page))
    page._save_signin(PROFILE_PATH)
    assert user_settings.get_settings()["browser_access"] == PROFILE_PATH
    wait_until(lambda: "LibreWolf" in page.signin_now.get_text())


def test_update_runs_in_a_worker_thread_and_reports(page, fake_backends):
    main_thread = threading.get_ident()
    page._update_ytdlp()
    wait_until(lambda: fake_backends["updates"])
    assert fake_backends["updates"][0] != main_thread  # off the main loop
    wait_until(
        lambda: messages.SET_UPDATED.format(before="2026.09.01", after="2026.10.09") in label_texts(page)
    )


def test_diagnostics_saved_with_a_show_button(page, fake_backends, tmp_path):
    target = tmp_path / "diag.zip"
    page._diagnostics_target_chosen(_FakeSaveDialog(target), None)
    wait_until(lambda: fake_backends["diagnostics"] == [str(target)])
    wait_until(lambda: any(t.startswith("Saved to") for t in label_texts(page)))


class _FakeSaveDialog:
    def __init__(self, target):
        self.target = target

    def save_finish(self, _result):
        return FakeFile(str(self.target))


def test_tools_rows_paint_from_the_worker(page):
    page._read_tools_once()
    wait_until(lambda: "2026.09.01" in label_texts(page))
    assert any("ffmpeg" == text for text in label_texts(page))
    assert page.update_button.get_sensitive() is True


def test_page_fits_the_window_height(page, window):
    minimum, natural = window.measure(Gtk.Orientation.VERTICAL, -1)[:2]
    assert natural <= 800, f"window wants {natural} px tall"


def test_rebuilding_the_signin_list_never_overwrites_the_saved_choice(page, fake_backends):
    """The list is built before discovery finishes; selecting the saved value must not save"""
    user_settings.save_settings({"browser_access": "/profiles/lw"})
    saves = []
    real_save = user_settings.save_settings
    user_settings.save_settings = lambda values: saves.append(values) or real_save(values)
    try:
        page._refresh_signin_options([])  # discovery not back yet
        page._paint_signin_choice()
    finally:
        user_settings.save_settings = real_save
    assert saves == [] and user_settings.get_settings()["browser_access"] == "/profiles/lw"
    assert page.signin_choice.get_active_id() == "/profiles/lw"  # listed as the saved choice
