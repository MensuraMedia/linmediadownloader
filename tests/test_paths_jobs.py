#!/usr/bin/env python3
# tests/test_paths_jobs.py
# Phase 0 of the 2.0 upgrade: data lives in one fixed directory (with a one-time,
# copy-only migration of 1.x files) and download commands live outside Flask.

import os
import json
import time

import pytest

import modules.config.settings as settings
from modules.config import paths, user_settings
from modules.download import dedupe, jobs
from modules import playlists as pl
from modules.config import logging_config


# ── Data directory ───────────────────────────────────────────────────────────

def test_every_data_file_lives_in_the_data_dir():
    for path in (settings.HISTORY_FILE, settings.LINKS_HISTORY_FILE, user_settings.SETTINGS_FILE,
                 dedupe.MANIFEST_FILE, pl.COLORS_FILE, pl.SEQ_FILE, logging_config.LOG_FILE):
        assert os.path.commonpath([path, paths.DATA_DIR]) == paths.DATA_DIR, path


def test_data_dir_does_not_follow_the_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert paths.data_file('download_history.json') == settings.HISTORY_FILE
    assert not (tmp_path / 'data').exists()


def test_xdg_data_home_is_used_without_override(tmp_path, monkeypatch):
    monkeypatch.delenv('LMD_DATA_DIR', raising=False)
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path))
    assert paths._data_home() == str(tmp_path / 'linmediadownloader')


# ── 1.x migration ────────────────────────────────────────────────────────────

@pytest.fixture
def migration(tmp_path, monkeypatch):
    """A fresh data dir and two 1.x roots; returns (data_dir, old_a, old_b)."""
    data = tmp_path / 'new'
    data.mkdir()
    old_a, old_b = tmp_path / 'old_a', tmp_path / 'old_b'
    for root in (old_a, old_b):
        (root / 'data').mkdir(parents=True)
    monkeypatch.setattr(paths, 'DATA_DIR', str(data))
    monkeypatch.setattr(paths, 'MIGRATION_MARKER', str(data / 'migrated-from-1.x.json'))
    monkeypatch.setattr(paths, 'legacy_roots', lambda: [str(old_a), str(old_b)])
    monkeypatch.delenv('LMD_NO_MIGRATE', raising=False)
    return data, old_a, old_b


def _write(path, obj, age=0):
    path.write_text(json.dumps(obj))
    t = time.time() - age
    os.utime(path, (t, t))


def test_migration_copies_the_newest_copy_and_keeps_originals(migration):
    data, old_a, old_b = migration
    _write(old_a / 'data' / 'download_history.json', [{'title': 'old'}], age=3600)
    _write(old_b / 'data' / 'download_history.json', [{'title': 'newer'}])
    copied = paths.migrate_legacy_data()
    assert copied == {'download_history.json': str(old_b / 'data' / 'download_history.json')}
    assert json.loads((data / 'download_history.json').read_text()) == [{'title': 'newer'}]
    assert (old_a / 'data' / 'download_history.json').exists()
    assert (old_b / 'data' / 'download_history.json').exists()


def test_migration_never_overwrites_and_runs_once(migration):
    data, old_a, _ = migration
    _write(data / 'links_history.json', [{'url': 'mine'}])
    _write(old_a / 'data' / 'links_history.json', [{'url': 'legacy'}])
    assert paths.migrate_legacy_data() == {}
    assert json.loads((data / 'links_history.json').read_text()) == [{'url': 'mine'}]
    _write(old_a / 'data' / 'playlist_seq.json', {'x': 1})
    assert paths.migrate_legacy_data() == {}  # marker written: never runs again
    assert not (data / 'playlist_seq.json').exists()


def test_migration_skips_corrupt_files(migration):
    data, old_a, _ = migration
    (old_a / 'data' / 'app_settings.json').write_text('{not json')
    assert paths.migrate_legacy_data() == {}
    assert not (data / 'app_settings.json').exists()


def test_migration_can_be_switched_off(migration, monkeypatch):
    data, old_a, _ = migration
    _write(old_a / 'data' / 'download_manifest.json', [])
    monkeypatch.setenv('LMD_NO_MIGRATE', '1')
    assert paths.migrate_legacy_data() == {}
    assert not os.path.exists(paths.MIGRATION_MARKER)


def test_library_still_scans_legacy_download_folders(tmp_path, monkeypatch):
    legacy = tmp_path / 'old' / 'downloads'
    (legacy / 'mix_playlist').mkdir(parents=True)
    for name in ('a.mp3', 'b.mp3'):
        (legacy / 'mix_playlist' / name).write_bytes(b'x')
    monkeypatch.setattr(settings, 'default_download_path', str(tmp_path / 'nowhere'))
    monkeypatch.setattr(settings, 'download_history', [])
    monkeypatch.setattr(paths, 'legacy_download_dirs', lambda: [str(legacy)])
    assert str(legacy) in pl._scan_dirs()


# ── Links history keeps its identity ─────────────────────────────────────────

def test_links_history_is_loaded_in_place(tmp_path, monkeypatch):
    f = tmp_path / 'links.json'
    f.write_text(json.dumps([{'url': 'u'}]))
    monkeypatch.setattr(settings, 'LINKS_HISTORY_FILE', str(f))
    ref = settings.links_history
    settings.load_links_history()
    assert settings.links_history is ref and ref == [{'url': 'u'}]
    ref.clear()


# ── Jobs (front-end-neutral commands) ────────────────────────────────────────

def test_normalize_options_validates_input():
    opts = jobs.normalize_options({'video_quality': '4320', 'limit': 'ten', 'skip_long': 1, 'output_dir': ''})
    assert opts['video_quality'] == jobs.DEFAULT_VIDEO_QUALITY
    assert opts['limit'] == 0
    assert opts['skip_long'] is True
    assert opts['output_dir'] == settings.default_download_path
    assert jobs.normalize_options(None)['download_type'] == 'audio'


@pytest.fixture
def fake_queue(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'LINKS_HISTORY_FILE', str(tmp_path / 'links.json'))
    queue = []

    def enqueue(url, output_dir, *args, **kwargs):
        job = {'id': len(queue) + 1, 'url': url, 'status': 'active' if not queue else 'queued'}
        queue.append(job)
        return job

    monkeypatch.setattr(jobs, 'enqueue_download', enqueue)
    monkeypatch.setattr(jobs, 'download_queue', queue)
    yield queue
    settings.links_history.clear()


def test_submit_starts_then_queues(fake_queue):
    assert jobs.submit_download('https://a') == {'status': 'started', 'job_id': 1}
    assert jobs.submit_download('https://b') == {'status': 'queued', 'job_id': 2, 'position': 1}
    assert jobs.submit_download('https://c')['position'] == 2
    assert [e['url'] for e in settings.links_history] == ['https://a', 'https://b', 'https://c']


def test_queue_snapshot_and_clear_finished(fake_queue):
    fake_queue.extend([{'id': 1, 'status': 'completed'}, {'id': 2, 'status': 'active'},
                       {'id': 3, 'status': 'queued'}, {'id': 4, 'status': 'error'}])
    snap = jobs.queue_snapshot()
    assert [j['id'] for j in snap] == [1, 2, 3, 4] and set(snap[0]) == set(jobs._QUEUE_FIELDS)
    assert jobs.clear_finished_jobs() == 2
    assert [j['id'] for j in fake_queue] == [2, 3]


def test_cancel_records_partial_download(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'HISTORY_FILE', str(tmp_path / 'h.json'))
    monkeypatch.setattr(settings, 'download_history', [])
    monkeypatch.setitem(settings.current_download, 'playlist_title', 'AKIRA OST')
    settings.reset_cancel()
    jobs.cancel_active_download()
    assert settings.is_cancel_requested()
    assert settings.current_download['status'] == 'cancelled'
    assert settings.download_history[-1]['title'] == 'AKIRA OST'
    assert settings.download_history[-1]['status'] == 'completed_with_errors'
    settings.reset_cancel()
    settings.current_download['status'] = None
