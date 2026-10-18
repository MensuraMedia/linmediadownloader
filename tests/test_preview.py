#!/usr/bin/env python3
# tests/test_preview.py
# Link preview (modules/download/preview.py) and per-track states, with yt-dlp mocked.

import pytest

from modules.config import settings
from modules.download import dedupe, media, preview

PLAYLIST = {
    '_type': 'playlist', 'title': 'AKIRA OST',
    'entries': [
        {'id': 'a1', 'title': 'Kaneda', 'duration': 222, 'url': 'https://y/a1'},
        {'id': 'a2', 'title': 'Battle Against Clown', 'duration': 221, 'url': 'https://y/a2'},
        {'id': 'a4', 'title': 'Tetsuo', 'duration': 620, 'url': 'https://y/a4'},
        None,  # yt-dlp yields None for entries it could not read
    ],
}


@pytest.fixture
def fake_extract(monkeypatch):
    calls = []

    def extract(url):
        calls.append(url)
        if 'playlist?list=' in url:
            return PLAYLIST
        if 'boom' in url:
            raise Exception('ERROR: [youtube] x: Sign in to confirm you’re not a bot.')
        return {'id': 'v1', 'title': 'Live at Montreux', 'duration': 3000}

    monkeypatch.setattr(preview, '_extract', extract)
    monkeypatch.setattr(dedupe, '_manifest', [])
    return calls


def test_playlist_entries_and_skip_reasons(fake_extract, monkeypatch):
    monkeypatch.setattr(dedupe, '_manifest', [{'id': 'a2', 'title': 'x', 'tokens': []}])
    p = preview.preview_link('https://www.youtube.com/playlist?list=PL1', skip_long=True, ignore_dupes=True)
    assert p['kind'] == 'playlist' and p['title'] == 'AKIRA OST' and p['error'] is None
    assert [(e['index'], e['title'], e['skip']) for e in p['entries']] == [
        (1, 'Kaneda', None), (2, 'Battle Against Clown', 'duplicate'), (3, 'Tetsuo', 'long')]
    assert preview.summarize(p) == {'count': 3, 'to_download': 1, 'skipped_long': 1,
                                    'skipped_duplicate': 1, 'seconds': 1063}


def test_options_off_skip_nothing(fake_extract):
    p = preview.preview_link('https://www.youtube.com/playlist?list=PL1')
    assert [e['skip'] for e in p['entries']] == [None, None, None]


def test_watch_link_with_list_reads_the_playlist(fake_extract):
    p = preview.preview_link('https://www.youtube.com/watch?v=v1&list=PL1')
    assert p['kind'] == 'playlist' and p['video_title'] == 'Live at Montreux'
    assert p['playlist_url'] == 'https://www.youtube.com/playlist?list=PL1'


def test_single_video(fake_extract):
    p = preview.preview_link('https://www.youtube.com/watch?v=v1', skip_long=True)
    assert p['kind'] == 'video' and len(p['entries']) == 1 and p['entries'][0]['skip'] == 'long'


def test_errors_are_classified(fake_extract):
    p = preview.preview_link('https://www.youtube.com/watch?v=boom')
    assert p['error']['kind'] == 'bot_check' and p['entries'] == []


@pytest.mark.parametrize('text,kind', [
    ('HTTP Error 429: Too Many Requests', 'rate_limited'),
    ('ERROR: Private video. Sign in if you\'ve been granted access', 'unavailable'),
    ('Unsupported URL: https://example.com', 'unsupported'),
    ('Unable to download webpage: <urlopen error [Errno -3] Temporary failure>', 'network'),
    ('something new', 'unknown'),
])
def test_classify_error(text, kind):
    assert preview.classify_error(text) == kind


def test_long_threshold_is_shared():
    from modules import playlists
    assert preview.LONG_SECONDS == media.LONG_SECONDS == playlists.LONG_SECONDS == settings.LONG_SECONDS == 420


def test_track_states_follow_the_progress_hook(monkeypatch):
    monkeypatch.setitem(settings.current_download, 'tracks', {})
    monkeypatch.setattr(dedupe, 'record_download', lambda info: None)
    hook = media.DownloadProgress(total_files=2).progress_hook
    info = {'id': 'a1', 'title': 'Kaneda'}
    hook({'status': 'downloading', 'filename': '/t/Kaneda.mp3', 'info_dict': info,
          'downloaded_bytes': 50, 'total_bytes': 100})
    assert settings.current_download['tracks']['a1'] == {'title': 'Kaneda', 'state': 'downloading', 'progress': 50}
    hook({'status': 'finished', 'filename': '/t/Kaneda.mp3', 'info_dict': info})
    assert settings.current_download['tracks']['a1']['state'] == 'done'
    media.set_track({'title': 'No id'}, 'skipped_long')
    assert settings.current_download['tracks']['No id']['state'] == 'skipped_long'
    media.set_track({}, 'done')  # nothing to key it by: ignored
    assert len(settings.current_download['tracks']) == 2


def test_apply_options_rechecks_without_network(fake_extract):
    p = preview.preview_link('https://www.youtube.com/playlist?list=PL1')
    calls = len(fake_extract)
    preview.apply_options(p, skip_long=True)
    assert [e['skip'] for e in p['entries']] == [None, None, 'long'] and len(fake_extract) == calls
    preview.apply_options(p, skip_long=False)
    assert [e['skip'] for e in p['entries']] == [None, None, None]


def test_480p_is_accepted():
    from modules.download import jobs
    assert jobs.normalize_options({'video_quality': '480'})['video_quality'] == '480'


@pytest.mark.parametrize('url,expected', [
    ('https://www.youtube.com/watch?v=oqvC0MLOMCU&list=RDoqvC0MLOMCU&start_radio=1',
     'https://www.youtube.com/watch?v=oqvC0MLOMCU'),
    ('https://www.youtube.com/watch?v=a1&list=PL123', 'https://www.youtube.com/watch?v=a1&list=PL123'),
    ('https://www.youtube.com/playlist?list=PL123', 'https://www.youtube.com/playlist?list=PL123'),
])
def test_mix_links_become_the_single_video(url, expected):
    assert preview.strip_mix(url) == expected
