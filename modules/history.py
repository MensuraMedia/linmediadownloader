#!/usr/bin/env python3
# modules/history.py
# One merged, GTK-free view of everything the user asked the app to download:
# `download_history` (finished downloads) plus `links_history` (every pasted
# link), newest first. The Activity page groups, filters and clears through
# these functions; nothing here imports Gtk, so tests run without a display.
#
# Both lists are mutated IN PLACE and saved through the settings savers (never
# rebound: other modules imported them by reference — see CLAUDE.md).

import logging
from datetime import date, datetime, timedelta

from modules.config import settings

logger = logging.getLogger("lmd.history")

# download/link status -> the result the UI shows a pill for
RESULTS = {
    "completed": "done",
    "completed_with_errors": "partial",
    "cancelled": "cancelled",
    "error": "failed",
}
PROBLEM_RESULTS = ("partial", "cancelled", "failed", "not_downloaded")


def _when(timestamp):
    """A datetime for an entry's ISO timestamp (unknown ones sort newest)"""
    if isinstance(timestamp, datetime):
        return timestamp
    try:
        return datetime.fromisoformat(timestamp)
    except (TypeError, ValueError):
        return datetime.now()


def merged_entries():
    """Downloads and not-downloaded links, newest first.

    A link whose url appears in download_history is covered by that download's
    row, so it is not repeated; the rest become 'not_downloaded' entries."""
    downloads = list(settings.download_history)
    known_urls = {d.get("url") for d in downloads if d.get("url")}
    entries = [
        _entry(f"d{index}", item, RESULTS.get(item.get("status"), "not_downloaded"))
        for index, item in enumerate(downloads)
    ]
    for index, item in enumerate(settings.links_history):
        url = item.get("url") or ""
        if url and url in known_urls:
            continue
        entries.append(_entry(f"l{index}", item, RESULTS.get(item.get("status"), "not_downloaded")))
    entries.sort(key=lambda entry: entry["when"], reverse=True)
    return entries


def _entry(entry_id, item, result):
    return {
        "id": entry_id,
        "title": item.get("title") or item.get("url") or "",
        "url": item.get("url") or "",
        "kind": "video" if item.get("download_type") == "video" else "audio",
        "is_playlist": bool(item.get("is_playlist")) or item.get("playlist_mode") == "playlist",
        "result": result,
        "folder": item.get("output_dir") or "",
        "timestamp": item.get("timestamp") or "",
        "when": _when(item.get("timestamp")),
    }


def group_by_day(entries, today=None):
    """[(label, entries)] in the given order: 'Today', 'Yesterday', then '12 Oct'
    (with the year when it is not this one)."""
    today = today or date.today()
    yesterday = today - timedelta(days=1)
    groups, index_of = [], {}
    for entry in entries:
        day = entry["when"].date()
        if day == today:
            label = "Today"
        elif day == yesterday:
            label = "Yesterday"
        elif day.year == today.year:
            label = day.strftime("%-d %b")
        else:
            label = day.strftime("%-d %b %Y")
        if label not in index_of:
            index_of[label] = len(groups)
            groups.append((label, []))
        groups[index_of[label]][1].append(entry)
    return groups


def matches(entry, query="", kind_filter="all"):
    """Search (titles and links) plus the All/Audio/Video/Problems filter"""
    query = (query or "").strip().lower()
    if query and query not in (entry["title"] or "").lower() and query not in (entry["url"] or "").lower():
        return False
    if kind_filter == "audio":
        return entry["kind"] == "audio"
    if kind_filter == "video":
        return entry["kind"] == "video"
    if kind_filter == "problems":
        return entry["result"] in PROBLEM_RESULTS
    return True


def remove_entry(entry_id):
    """Drop one merged entry ('d3' = download_history[3], 'l1' = links_history[1])."""
    if not entry_id or entry_id[0] not in ("d", "l") or not entry_id[1:].isdigit():
        return False
    index = int(entry_id[1:])
    if entry_id[0] == "d":
        if index >= len(settings.download_history):
            return False
        del settings.download_history[index]
        settings.save_download_history()
    else:
        if index >= len(settings.links_history):
            return False
        del settings.links_history[index]
        settings.save_links_history()
    return True


def _cutoff(days, today=None):
    """The datetime `days` whole days before the end of `today`"""
    days = max(0, int(days or 0))
    end_of_today = datetime.combine(today or date.today(), datetime.max.time())
    return end_of_today - timedelta(days=days)


def count_older_than(days, today=None):
    """How many entries clear_older_than(days) would remove (for the confirm)"""
    cutoff = _cutoff(days, today)
    return sum(1 for entry in merged_entries() if entry["when"] < cutoff)


def clear_older_than(days, today=None):
    """Remove entries older than `days` from both lists (in place, saved).
    Returns how many merged entries were removed."""
    before = len(merged_entries())
    cutoff = _cutoff(days, today)
    settings.download_history[:] = [
        d for d in settings.download_history if _when(d.get("timestamp")) >= cutoff
    ]
    settings.links_history[:] = [l for l in settings.links_history if _when(l.get("timestamp")) >= cutoff]
    settings.save_download_history()
    settings.save_links_history()
    return before - len(merged_entries())
