#!/usr/bin/env python3
# modules/download/access.py
# How yt-dlp gets past YouTube's "Sign in to confirm you're not a bot": by using the
# sign-in of a browser the user already uses, picked automatically.
#
# Every installed Firefox- or Chromium-family browser profile is checked for a
# current YouTube sign-in. Only cookie NAMES and timestamps are read here (never
# values); yt-dlp reads the chosen profile's cookies itself and sends them only to
# YouTube. The pick: signed-in profiles of running browsers first, then the profile
# that used YouTube most recently. Also finds a local JavaScript runtime, which
# yt-dlp needs to answer YouTube's player challenges (the solver scripts come from
# the local yt-dlp-ejs package, never downloaded at run time).
#
# Override with LMD_BROWSER_ACCESS=off (no browser sign-in) — Settings gains a switch later.

import atexit
import configparser
import glob
import logging
import os
import shutil
import sqlite3
import tempfile
import time
from dataclasses import dataclass

logger = logging.getLogger("lmd.access")

# Cookies that mean "signed in to a Google account on YouTube"
SIGN_IN_COOKIES = ("LOGIN_INFO", "SAPISID", "__Secure-3PSID", "__Secure-1PSID")

# (label, process names, profile roots relative to $HOME). Firefox family: roots hold
# profiles.ini. yt-dlp has no name for the forks, but its firefox reader takes a path.
FIREFOX_FAMILY = (
    ("LibreWolf", ("librewolf",), (".librewolf", ".var/app/io.gitlab.librewolf-community/.librewolf")),
    (
        "Firefox",
        ("firefox", "firefox-bin"),
        (
            ".mozilla/firefox",
            "snap/firefox/common/.mozilla/firefox",
            ".var/app/org.mozilla.firefox/.mozilla/firefox",
        ),
    ),
    ("Waterfox", ("waterfox",), (".waterfox",)),
    ("Floorp", ("floorp",), (".floorp", ".var/app/one.ablaze.floorp/.floorp")),
    ("Zen", ("zen", "zen-bin"), (".zen", ".var/app/app.zen_browser.zen/.zen")),
)
# (label, yt-dlp browser name, process names, user-data roots relative to $HOME)
CHROMIUM_FAMILY = (
    (
        "Brave",
        "brave",
        ("brave", "brave-browser"),
        (
            ".config/BraveSoftware/Brave-Browser",
            ".var/app/com.brave.Browser/config/BraveSoftware/Brave-Browser",
        ),
    ),
    (
        "Chrome",
        "chrome",
        ("chrome", "google-chrome"),
        (".config/google-chrome", ".var/app/com.google.Chrome/config/google-chrome"),
    ),
    (
        "Chromium",
        "chromium",
        ("chromium", "chromium-browser"),
        (
            ".config/chromium",
            "snap/chromium/common/chromium",
            ".var/app/org.chromium.Chromium/config/chromium",
        ),
    ),
    ("Vivaldi", "vivaldi", ("vivaldi", "vivaldi-bin"), (".config/vivaldi",)),
    ("Edge", "edge", ("msedge", "microsoft-edge"), (".config/microsoft-edge",)),
    ("Opera", "opera", ("opera",), (".config/opera",)),
)

# Seconds between 1601-01-01 (Chromium's epoch) and 1970-01-01
_WEBKIT_EPOCH = 11644473600


@dataclass
class Profile:
    browser: str  # what the user calls it ("LibreWolf")
    ytdlp_browser: str  # what yt-dlp calls its family ("firefox", "brave", …)
    path: str  # the profile folder yt-dlp reads
    cookie_db: str
    running: bool = False
    signed_in: bool = False
    last_used: float = 0.0  # last time a YouTube cookie was used (Unix seconds)

    def cookies_option(self):
        """yt-dlp's cookiesfrombrowser tuple: (browser, profile, keyring, container)"""
        return (self.ytdlp_browser, self.path, None, None)


def _home():
    return os.path.expanduser("~")


def running_processes():
    """Lower-case executable names of every process the user can see"""
    names = set()
    for cmdline in glob.glob("/proc/[0-9]*/cmdline"):
        try:
            with open(cmdline, "rb") as f:
                first = f.read().split(b"\0", 1)[0].decode(errors="ignore")
        except OSError:
            continue
        if first:
            names.add(os.path.basename(first).lower())
    return names


def _query(db, sql):
    """Read-only query of a cookie database a running browser may hold open"""
    con = sqlite3.connect(f"file:{db}?immutable=1", uri=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def _firefox_sign_in(db, now):
    rows = _query(db, "SELECT name, expiry, lastAccessed FROM moz_cookies WHERE host LIKE '%youtube.com'")
    names = set()
    last = 0.0
    for name, expiry, accessed in rows:
        # expiry is seconds (milliseconds in some versions); lastAccessed is microseconds
        exp = expiry / 1000 if expiry and expiry > 1e11 else (expiry or 0)
        if exp > now:
            names.add(name)
        last = max(last, (accessed or 0) / 1e6)
    return bool(names & set(SIGN_IN_COOKIES)), last


def _chromium_sign_in(db, now):
    rows = _query(
        db, "SELECT name, expires_utc, last_access_utc FROM cookies WHERE host_key LIKE '%youtube.com'"
    )
    names = set()
    last = 0.0
    for name, expires, accessed in rows:
        exp = expires / 1e6 - _WEBKIT_EPOCH if expires else 0  # 0 = session cookie
        if expires == 0 or exp > now:
            names.add(name)
        if accessed:
            last = max(last, accessed / 1e6 - _WEBKIT_EPOCH)
    return bool(names & set(SIGN_IN_COOKIES)), last


def _firefox_profiles(root):
    """Profile folders listed in profiles.ini (relative or absolute), else any with cookies"""
    ini = os.path.join(root, "profiles.ini")
    paths = []
    if os.path.isfile(ini):
        parser = configparser.ConfigParser()
        try:
            parser.read(ini)
        except configparser.Error:
            parser = None
        for section in (parser.sections() if parser else []):
            path = parser[section].get("Path") or parser[section].get("Default")
            if not path:
                continue
            relative = parser[section].get("IsRelative", "1") == "1" or section.startswith("Install")
            full = os.path.join(root, path) if relative and not os.path.isabs(path) else path
            if full not in paths:
                paths.append(full)
    for db in glob.glob(os.path.join(root, "*", "cookies.sqlite")):
        if os.path.dirname(db) not in paths:
            paths.append(os.path.dirname(db))
    return [p for p in paths if os.path.isfile(os.path.join(p, "cookies.sqlite"))]


def discover_profiles(home=None, processes=None):
    """Every browser profile with a cookie database, signed in to YouTube or not"""
    home = home or _home()
    processes = running_processes() if processes is None else processes
    now = time.time()
    found = []

    def add(profile, check):
        try:
            profile.signed_in, profile.last_used = check(profile.cookie_db, now)
        except Exception as e:  # locked, corrupt or a format we don't know: skip, say why
            logger.info("Could not read %s: %s", profile.cookie_db, e)
            return
        found.append(profile)

    for label, procs, roots in FIREFOX_FAMILY:
        running = any(p in processes for p in procs)
        for rel in roots:
            for path in _firefox_profiles(os.path.join(home, rel)):
                add(
                    Profile(label, "firefox", path, os.path.join(path, "cookies.sqlite"), running),
                    _firefox_sign_in,
                )
    for label, name, procs, roots in CHROMIUM_FAMILY:
        running = any(p in processes for p in procs)
        for rel in roots:
            root = os.path.join(home, rel)
            for profile_dir in sorted(
                glob.glob(os.path.join(root, "Default")) + glob.glob(os.path.join(root, "Profile *"))
            ):
                for db in (
                    os.path.join(profile_dir, "Network", "Cookies"),
                    os.path.join(profile_dir, "Cookies"),
                ):
                    if os.path.isfile(db):
                        add(Profile(label, name, profile_dir, db, running), _chromium_sign_in)
                        break
    return found


def choose_profile(profiles):
    """The signed-in profile to use: running browsers first, then the most recent YouTube use"""
    signed_in = [p for p in profiles if p.signed_in]
    if not signed_in:
        return None
    return max(signed_in, key=lambda p: (p.running, p.last_used))


def find_js_runtime(home=None):
    """{name: {'path': ...}} for the first local runtime yt-dlp supports, or None"""
    home = home or _home()
    candidates = {
        "deno": [shutil.which("deno"), os.path.join(home, ".deno", "bin", "deno")],
        "node": [shutil.which("node"), shutil.which("nodejs")]
        + sorted(glob.glob(os.path.join(home, ".nvm", "versions", "node", "*", "bin", "node")), reverse=True),
        "bun": [shutil.which("bun"), os.path.join(home, ".bun", "bin", "bun")],
        "quickjs": [shutil.which("qjs")],
    }
    for name, paths in candidates.items():
        for path in paths:
            if path and os.path.isfile(path) and os.access(path, os.X_OK):
                return {name: {"path": path}}
    return None


@dataclass
class Access:
    profile: Profile = None
    js_runtime: dict = None

    def ydl_options(self):
        """Options to merge into every yt-dlp call that talks to YouTube"""
        opts = {}
        if self.profile:
            if self.profile.ytdlp_browser == "firefox":
                # yt-dlp copies only cookies.sqlite; the newest cookies may still be in
                # cookies.sqlite-wal. Give it a merged copy, made fresh for each call.
                merged = merged_firefox_profile(self.profile.path)
                opts["cookiesfrombrowser"] = ("firefox", merged or self.profile.path, None, None)
            else:
                opts["cookiesfrombrowser"] = self.profile.cookies_option()
        if self.js_runtime:
            opts["js_runtimes"] = self.js_runtime
        return opts

    def describe(self):
        """For the UI and the log: which sign-in and runtime are in use"""
        return {
            "browser": self.profile.browser if self.profile else None,
            "js_runtime": next(iter(self.js_runtime)) if self.js_runtime else None,
        }


def _private_dir():
    """A folder only this user can read, in memory when possible (sign-in cookies go here)"""
    base = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    path = os.path.join(base, "linmediadownloader")
    os.makedirs(path, mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def merged_firefox_profile(profile_path):
    """A copy of a Firefox-family cookie database with its write-ahead log folded in.

    Firefox and LibreWolf write new cookies to cookies.sqlite-wal first and fold them
    into cookies.sqlite later. YouTube replaces its sign-in cookies from time to time;
    until the browser folds the log in, the main file still holds the replaced ones,
    and yt-dlp (which copies only the main file) gets "cookies are no longer valid"
    and the bot check. Returns the folder of the merged copy, or None on failure.
    """
    source = os.path.join(profile_path, "cookies.sqlite")
    folder = os.path.join(_private_dir(), "cookies")
    try:
        os.makedirs(folder, mode=0o700, exist_ok=True)
        for suffix in ("", "-wal", "-shm"):
            target = os.path.join(folder, "cookies.sqlite" + suffix)
            if os.path.exists(target):
                os.remove(target)
            if suffix != "-shm" and os.path.exists(source + suffix):
                shutil.copy2(source + suffix, target)
                os.chmod(target, 0o600)
        con = sqlite3.connect(os.path.join(folder, "cookies.sqlite"))
        try:
            con.execute("PRAGMA wal_checkpoint(TRUNCATE)")  # fold the log into the file
        finally:
            con.close()
        return folder
    except (OSError, sqlite3.Error) as e:
        logger.warning("Could not merge the cookie log of %s (%s); using the profile as is", profile_path, e)
        return None


@atexit.register
def _remove_private_copy():
    """Never leave a copy of sign-in cookies behind"""
    base = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    shutil.rmtree(os.path.join(base, "linmediadownloader", "cookies"), ignore_errors=True)


_cache = {"at": 0.0, "access": None}
_REFRESH_SECONDS = 300  # re-check every few minutes: the user may sign in or switch browsers


def current(refresh=False):
    """The Access to use now (cached for a few minutes)"""
    if not refresh and _cache["access"] is not None and time.time() - _cache["at"] < _REFRESH_SECONDS:
        return _cache["access"]
    profile = None
    if os.environ.get("LMD_BROWSER_ACCESS", "").lower() != "off":
        try:
            profile = choose_profile(discover_profiles())
        except Exception:
            logger.exception("Browser discovery failed; continuing without a sign-in")
    access = Access(profile, find_js_runtime())
    if profile:
        logger.info(
            "Using the YouTube sign-in of %s (%s, running=%s)", profile.browser, profile.path, profile.running
        )
    else:
        logger.info("No browser with a YouTube sign-in found; requests go out signed out")
    if not access.js_runtime:
        logger.warning(
            "No JavaScript runtime (deno, node, bun, quickjs) found; YouTube formats may be missing"
        )
    _cache.update(at=time.time(), access=access)
    return access


def ydl_options():
    """Shortcut: the sign-in and runtime options for a yt-dlp call"""
    return current().ydl_options()
