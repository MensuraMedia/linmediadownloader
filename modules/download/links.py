# modules/download/links.py
"""Links in pasted text: several at once become several queued downloads (user,
2026-10-19: "paste in different links so music downloads are queued for continuous
downloading")."""

import re
from urllib.parse import parse_qs, urlsplit

_URL = re.compile(r'https?://[^\s<>"\']+')
_TRAILING = '.,;:!?)]}>'


def links_in(text):
    """Every http(s) link in the text, in order, each once"""
    found = []
    for match in _URL.finditer(text or ''):
        url = match.group(0).rstrip(_TRAILING)
        if url not in found:
            found.append(url)
    return found


def is_playlist_link(url):
    """A link to a whole playlist page (…/playlist?list=…). A watch?v=…&list=… link
    names one video first, so a queued one downloads that video, as a single link
    pasted without reading its preview would."""
    parts = urlsplit(url or '')
    query = parse_qs(parts.query)
    return bool(query.get('list')) and not query.get('v') and parts.path.rstrip('/').endswith('/playlist')
