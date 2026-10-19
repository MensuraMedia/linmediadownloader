#!/usr/bin/env python3
# tests/test_settings_backend.py
# What the Settings page stands on: the download folder (default ~/Music/LinMediaDownloads),
# partial saves, the long-file limit, the sign-in choice, and the diagnostics bundle.

import os
import zipfile

import pytest

from modules import tools
from modules.config import settings, user_settings
from modules.download import access


@pytest.fixture
def fresh_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(user_settings, "SETTINGS_FILE", str(tmp_path / "app_settings.json"))
    monkeypatch.setattr(user_settings, "_settings", None)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "home" / ".config"))
    yield tmp_path
    user_settings._settings = None


def test_default_download_folder_is_music_linmediadownloads(fresh_settings):
    home = fresh_settings / "home"
    assert settings.default_download_folder() == str(home / "Music" / "LinMediaDownloads")
    folder = settings.download_folder()
    assert folder == str(home / "Music" / "LinMediaDownloads") and os.path.isdir(folder)  # made when needed


def test_a_localised_music_folder_is_followed(fresh_settings):
    config = fresh_settings / "home" / ".config"
    config.mkdir(parents=True)
    (config / "user-dirs.dirs").write_text('XDG_MUSIC_DIR="$HOME/Musique"\n')
    assert settings.default_download_folder() == str(fresh_settings / "home" / "Musique" / "LinMediaDownloads")


def test_choosing_a_folder_moves_downloads_there(fresh_settings):
    chosen = fresh_settings / "elsewhere"
    user_settings.save_settings({"download_folder": str(chosen)})
    assert settings.download_folder() == str(chosen) and settings.default_download_path == str(chosen)
    user_settings.save_settings({"download_folder": ""})  # back to the default
    assert settings.default_download_path.endswith(os.path.join("Music", "LinMediaDownloads"))


def test_a_partial_save_keeps_the_other_settings(fresh_settings):
    user_settings.save_settings({"long_minutes": 12, "download_type": "video"})
    user_settings.save_settings({"filler_words": ["xyz"]})  # what the 1.x API sends
    saved = user_settings.get_settings()
    assert saved["long_minutes"] == 12 and saved["download_type"] == "video" and saved["filler_words"] == ["xyz"]


def test_invalid_values_are_refused(fresh_settings):
    user_settings.save_settings({"long_minutes": "lots", "video_quality": "4320", "download_type": "gif"})
    saved = user_settings.get_settings()
    assert (saved["long_minutes"], saved["video_quality"], saved["download_type"]) == (7, "1080", "audio")
    user_settings.save_settings({"long_minutes": 999})
    assert user_settings.get_settings()["long_minutes"] == 60  # clamped


def test_long_file_limit_follows_settings(fresh_settings):
    assert settings.long_seconds() == 420
    user_settings.save_settings({"long_minutes": 10})
    assert settings.long_seconds() == 600


def test_reset_restores_defaults(fresh_settings):
    user_settings.save_settings({"long_minutes": 20, "browser_access": "off"})
    user_settings.reset_settings(["long_minutes"])
    assert user_settings.get_settings()["long_minutes"] == 7
    assert user_settings.get_settings()["browser_access"] == "off"  # only the named key


def test_listeners_hear_saves(fresh_settings):
    heard = []
    user_settings.on_change(heard.append)
    try:
        user_settings.save_settings({"video_quality": "720"})
        assert heard and heard[-1]["video_quality"] == "720"
    finally:
        user_settings._listeners.remove(heard.append)


def test_sign_in_choice_off_and_specific(fresh_settings, monkeypatch):
    monkeypatch.delenv("LMD_BROWSER_ACCESS", raising=False)
    a = access.Profile("LibreWolf", "firefox", "/p/lw", "/p/lw/cookies.sqlite", True, True, 200.0)
    b = access.Profile("Brave", "brave", "/p/br", "/p/br/Cookies", True, True, 100.0)
    monkeypatch.setattr(access, "discover_profiles", lambda: [a, b])
    monkeypatch.setattr(access, "find_js_runtime", lambda home=None: None)
    user_settings.save_settings({"browser_access": "auto"})
    assert access.current(refresh=True).profile is a  # most recent use
    user_settings.save_settings({"browser_access": "/p/br"})
    assert access.current(refresh=True).profile is b  # the one picked in Settings
    user_settings.save_settings({"browser_access": "off"})
    assert access.current(refresh=True).profile is None
    user_settings.save_settings({"browser_access": "/p/gone"})
    assert access.current(refresh=True).profile is a  # a vanished choice falls back to auto
    access._cache.update(at=0.0, access=None)


def test_diagnostics_hold_logs_and_versions_never_cookies(fresh_settings, monkeypatch):
    logs = fresh_settings / "logs"
    logs.mkdir()
    (logs / "app.log").write_text("line\n")
    monkeypatch.setattr(tools.paths, "LOG_DIR", str(logs))
    monkeypatch.setattr(access, "current", lambda refresh=False: access.Access(None, None))
    target = tools.save_diagnostics(str(fresh_settings / "diag.zip"))
    names = zipfile.ZipFile(target).namelist()
    assert sorted(names) == ["environment.json", "logs/app.log"]
    assert "cookie" not in zipfile.ZipFile(target).read("environment.json").decode().lower()


def test_ytdlp_update_is_refused_outside_a_venv(monkeypatch):
    monkeypatch.setattr(tools.sys, "base_prefix", tools.sys.prefix)
    result = tools.update_ytdlp()
    assert result["ok"] is False and "package manager" in result["output"]


def test_ytdlp_update_is_refused_in_a_read_only_venv(monkeypatch):
    """The .deb's venv in /opt belongs to root: the app must not offer to pip-install there"""
    monkeypatch.setattr(tools.sys, "base_prefix", "/usr")
    monkeypatch.setattr(tools.sys, "prefix", "/opt/linmediadownloader/venv")
    monkeypatch.setattr(tools.os, "access", lambda path, mode: False)
    assert tools.can_update_ytdlp() is False
    assert "package manager" in tools.update_ytdlp()["output"]
