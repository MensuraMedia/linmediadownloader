#!/usr/bin/env python3
# tests/test_access.py
# Automatic browser sign-in (modules/download/access.py) on a fake home folder with
# fake cookie databases: never the user's real browsers.

import os
import sqlite3
import time

import pytest

from modules.download import access

NOW = time.time()
WEBKIT = 11644473600


def firefox_profile(home, root, name, cookies, default=True):
    """A Firefox-family profile folder listed in profiles.ini, with these youtube cookies"""
    base = home / root
    profile = base / name
    profile.mkdir(parents=True)
    (base / "profiles.ini").write_text(
        f"[Install1]\nDefault={name}\n\n[Profile0]\nPath={name}\nIsRelative=1\n" if default else ""
    )
    con = sqlite3.connect(profile / "cookies.sqlite")
    con.execute("CREATE TABLE moz_cookies (host TEXT, name TEXT, expiry INTEGER, lastAccessed INTEGER)")
    for cookie_name, expiry, last in cookies:
        con.execute(
            "INSERT INTO moz_cookies VALUES ('.youtube.com', ?, ?, ?)",
            (cookie_name, int(expiry), int(last * 1e6)),
        )
    con.commit()
    con.close()
    return str(profile)


def chromium_profile(home, root, cookies):
    profile = home / root / "Default"
    (profile / "Network").mkdir(parents=True)
    con = sqlite3.connect(profile / "Network" / "Cookies")
    con.execute(
        "CREATE TABLE cookies (host_key TEXT, name TEXT, expires_utc INTEGER, last_access_utc INTEGER)"
    )
    for cookie_name, expiry, last in cookies:
        con.execute(
            "INSERT INTO cookies VALUES ('.youtube.com', ?, ?, ?)",
            (cookie_name, int((expiry + WEBKIT) * 1e6), int((last + WEBKIT) * 1e6)),
        )
    con.commit()
    con.close()
    return str(profile)


SIGNED_IN = [("LOGIN_INFO", NOW + 86400, NOW - 60), ("SAPISID", NOW + 86400, NOW - 60)]


def test_finds_flatpak_librewolf_and_reports_sign_in(tmp_path):
    path = firefox_profile(
        tmp_path, ".var/app/io.gitlab.librewolf-community/.librewolf", "abc.default", SIGNED_IN
    )
    [p] = access.discover_profiles(home=str(tmp_path), processes={"librewolf"})
    assert (p.browser, p.ytdlp_browser, p.path, p.running, p.signed_in) == (
        "LibreWolf",
        "firefox",
        path,
        True,
        True,
    )
    assert p.cookies_option() == ("firefox", path, None, None)
    assert abs(p.last_used - (NOW - 60)) < 2


def test_expired_or_tracking_only_cookies_are_not_a_sign_in(tmp_path):
    firefox_profile(
        tmp_path,
        ".mozilla/firefox",
        "x.default",
        [("LOGIN_INFO", NOW - 10, NOW), ("VISITOR_INFO1_LIVE", NOW + 1e6, NOW)],
    )
    [p] = access.discover_profiles(home=str(tmp_path), processes=set())
    assert not p.signed_in
    assert access.choose_profile([p]) is None


def test_running_browser_wins_then_most_recent_use(tmp_path):
    firefox_profile(tmp_path, ".mozilla/firefox", "ff", [("LOGIN_INFO", NOW + 1e6, NOW - 5)])  # newest use
    chromium_profile(tmp_path, ".config/BraveSoftware/Brave-Browser", [("SAPISID", NOW + 1e6, NOW - 3600)])
    lw = firefox_profile(tmp_path, ".librewolf", "lw", [("LOGIN_INFO", NOW + 1e6, NOW - 600)])
    profiles = access.discover_profiles(home=str(tmp_path), processes={"librewolf", "brave"})
    assert {p.browser for p in profiles} == {"Firefox", "Brave", "LibreWolf"}
    chosen = access.choose_profile(profiles)
    assert chosen.browser == "LibreWolf" and chosen.path == lw  # running, used after Brave
    # nothing running: the most recent YouTube use decides
    chosen = access.choose_profile(access.discover_profiles(home=str(tmp_path), processes=set()))
    assert chosen.browser == "Firefox"


def test_chromium_profile_maps_to_its_ytdlp_name(tmp_path):
    path = chromium_profile(tmp_path, ".config/BraveSoftware/Brave-Browser", SIGNED_IN)
    [p] = access.discover_profiles(home=str(tmp_path), processes={"brave"})
    assert p.cookies_option() == ("brave", path, None, None) and p.signed_in


def test_unreadable_database_is_skipped(tmp_path):
    profile = tmp_path / ".mozilla/firefox/broken"
    profile.mkdir(parents=True)
    (profile / "cookies.sqlite").write_text("not a database")
    assert access.discover_profiles(home=str(tmp_path), processes=set()) == []


def test_js_runtime_found_in_nvm(tmp_path, monkeypatch):
    monkeypatch.setattr(access.shutil, "which", lambda name: None)
    monkeypatch.setattr(access, "VENV_BIN", str(tmp_path / "venv-bin"))
    node = tmp_path / ".nvm/versions/node/v24.0.0/bin/node"
    node.parent.mkdir(parents=True)
    node.write_text("#!/bin/sh\n")
    node.chmod(0o755)
    assert access.find_js_runtime(home=str(tmp_path)) == {"node": {"path": str(node)}}
    node.chmod(0o644)
    assert access.find_js_runtime(home=str(tmp_path)) is None


def test_ydl_options_and_off_switch(tmp_path, monkeypatch):
    monkeypatch.delenv("LMD_BROWSER_ACCESS", raising=False)  # conftest turns discovery off
    path = firefox_profile(tmp_path, ".librewolf", "lw", SIGNED_IN)
    monkeypatch.setattr(access, "_home", lambda: str(tmp_path))
    monkeypatch.setattr(access, "running_processes", lambda: set())
    monkeypatch.setattr(access, "find_js_runtime", lambda home=None: {"node": {"path": "/x/node"}})
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))  # never the real /run/user
    opts = access.current(refresh=True).ydl_options()
    browser, merged, keyring, container = opts["cookiesfrombrowser"]
    session = str(tmp_path / "run" / "linmediadownloader" / f"session-{os.getpid()}")
    assert browser == "firefox" and merged.startswith(session + os.sep)  # a merged copy, this process's own
    assert opts["js_runtimes"] == {"node": {"path": "/x/node"}}
    assert os.path.isfile(os.path.join(merged, "cookies.sqlite")) and path != merged
    assert access.current().describe() == {"browser": "LibreWolf", "js_runtime": "node"}
    monkeypatch.setenv("LMD_BROWSER_ACCESS", "off")
    assert "cookiesfrombrowser" not in access.current(refresh=True).ydl_options()
    access._cache.update(at=0.0, access=None)


@pytest.fixture(autouse=True)
def fresh_cache():
    access._cache.update(at=0.0, access=None)
    yield
    access._cache.update(at=0.0, access=None)


def test_filename_postprocessor_returns_files_then_info(tmp_path, monkeypatch):
    """1.x returned ([info], None), so yt-dlp tried to delete a dict after every download"""
    import yt_dlp

    from modules.download import media

    seen = {}
    real_pp = yt_dlp.YoutubeDL.add_post_processor

    def capture(self, pp, when="post_process"):
        seen["pp"] = pp
        return real_pp(self, pp, when)

    monkeypatch.setattr(yt_dlp.YoutubeDL, "add_post_processor", capture)
    monkeypatch.setattr(yt_dlp.YoutubeDL, "download", lambda self, urls: 0)
    monkeypatch.setattr(media, "get_video_info", lambda url: {"is_playlist": False, "title": "T", "url": url})
    media.download_media("https://example.invalid/v", str(tmp_path))
    f = tmp_path / "A b.mp3"
    f.write_bytes(b"x")
    files, info = seen["pp"].run({"filepath": str(f)})
    assert files == [] and info["filepath"].endswith("A_b.mp3") and os.path.exists(info["filepath"])


def test_merged_copy_includes_cookies_still_in_the_wal(tmp_path, monkeypatch):
    """Firefox keeps fresh cookies in cookies.sqlite-wal; yt-dlp copies only the main file"""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    profile = tmp_path / "profile"
    profile.mkdir()
    db = profile / "cookies.sqlite"
    con = sqlite3.connect(db)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA wal_autocheckpoint=0")  # keep new rows in the -wal, like a running browser
    con.execute("CREATE TABLE moz_cookies (host TEXT, name TEXT, expiry INTEGER, lastAccessed INTEGER)")
    con.execute("INSERT INTO moz_cookies VALUES ('.youtube.com', 'LOGIN_INFO', 1, 1)")
    con.commit()
    assert (profile / "cookies.sqlite-wal").stat().st_size > 0  # the rows live in the log
    snapshot = tmp_path / "main-only.sqlite"
    snapshot.write_bytes(db.read_bytes())  # what copying only the main file gives
    assert sqlite3.connect(snapshot).execute("SELECT count(*) FROM sqlite_master").fetchone()[0] == 0
    merged = access.merged_firefox_profile(str(profile))
    rows = sqlite3.connect(os.path.join(merged, "cookies.sqlite")).execute("SELECT name FROM moz_cookies").fetchall()
    assert rows == [("LOGIN_INFO",)]
    assert oct(os.stat(merged).st_mode & 0o777) == "0o700"
    con.close()


def test_each_call_gets_its_own_copy_and_dead_sessions_are_cleaned(tmp_path, monkeypatch):
    """A live download's copy must survive other calls and other processes ending"""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    profile = tmp_path / "profile"
    profile.mkdir()
    sqlite3.connect(profile / "cookies.sqlite").execute("CREATE TABLE moz_cookies (name TEXT)").connection.commit()
    base = tmp_path / "run" / "linmediadownloader"
    dead = base / "session-999999999" / "cookies-x"  # a process that has ended
    dead.mkdir(parents=True)
    first = access.merged_firefox_profile(str(profile))
    second = access.merged_firefox_profile(str(profile))
    assert first != second and os.path.isdir(first) and os.path.isdir(second)
    assert not dead.exists()  # leftovers of finished processes go
    access._remove_private_copy()  # this process exits: only its own folder is removed
    assert not os.path.exists(first) and base.exists()


def _fake_runtime(path, version_line=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\necho '{version_line}'\n")
    path.chmod(0o755)
    return path


def test_the_venv_deno_comes_first(tmp_path, monkeypatch):
    """The installers put Deno in the app's venv: a menu launch finds it without PATH"""
    monkeypatch.setattr(access, "VENV_BIN", str(tmp_path / "venv" / "bin"))
    deno = _fake_runtime(tmp_path / "venv" / "bin" / "deno")
    node = _fake_runtime(tmp_path / "usr" / "node", "v24.1.0")
    monkeypatch.setattr(access.shutil, "which", lambda name: str(node) if name == "node" else None)
    assert access.find_js_runtime(home=str(tmp_path)) == {"deno": {"path": str(deno)}}


def test_a_node_older_than_22_is_skipped(tmp_path, monkeypatch):
    """Mint's apt nodejs is 18: yt-dlp refuses it, so look further (nvm)"""
    monkeypatch.setattr(access, "VENV_BIN", str(tmp_path / "none"))
    old = _fake_runtime(tmp_path / "usr" / "node", "v18.19.1")
    monkeypatch.setattr(access.shutil, "which", lambda name: str(old) if name == "node" else None)
    new = _fake_runtime(tmp_path / ".nvm/versions/node/v24.0.0/bin/node", "v24.0.0")
    assert access.find_js_runtime(home=str(tmp_path)) == {"node": {"path": str(new)}}
