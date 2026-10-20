# tests/test_links.py
# Several links in one paste (modules/download/links.py).

from modules.download.links import is_playlist_link, links_in


def test_links_in_finds_each_link_once_in_order():
    text = "first https://youtu.be/a, then\nhttps://www.youtube.com/watch?v=b. and https://youtu.be/a again"
    assert links_in(text) == ["https://youtu.be/a", "https://www.youtube.com/watch?v=b"]
    assert links_in("no links here") == []
    assert links_in("") == []


def test_playlist_pages_are_playlists_and_watch_links_are_not():
    assert is_playlist_link("https://www.youtube.com/playlist?list=PL123")
    assert not is_playlist_link("https://www.youtube.com/watch?v=x&list=PL123")
    assert not is_playlist_link("https://youtu.be/x")
