#!/usr/bin/env python3
# tests/test_history.py
# The merged history view (modules/history.py), GTK-free: merging downloads with
# links, day grouping, the search and kind filters, removal and clearing.

from datetime import date, datetime, timedelta

import pytest

from modules import history
from modules.config import settings


def entry(timestamp, **fields):
    base = {"timestamp": timestamp.isoformat(timespec="seconds")}
    base.update(fields)
    return base


@pytest.fixture(autouse=True)
def empty_histories():
    settings.download_history[:] = []
    settings.links_history[:] = []
    yield
    settings.download_history[:] = []
    settings.links_history[:] = []


@pytest.fixture
def filled(empty_histories):
    today = date.today()
    settings.download_history[:] = [
        entry(
            datetime.combine(today, datetime.min.time()) + timedelta(hours=9, minutes=58),
            url="https://y/neo",
            title="Neo-Tokyo Ambience",
            status="completed",
            download_type="audio",
            is_playlist=True,
            output_dir="/music/neo",
        ),
        entry(
            datetime.combine(today, datetime.min.time()) + timedelta(hours=8, minutes=52),
            url="https://y/bot",
            title="bot check link",
            status="error",
            download_type="video",
            is_playlist=False,
        ),
        entry(
            datetime.combine(today - timedelta(days=1), datetime.min.time())
            + timedelta(hours=21, minutes=14),
            url="https://y/synth",
            title="Synth Repair Basics",
            status="completed",
            download_type="video",
            is_playlist=False,
            output_dir="/videos",
        ),
    ]
    settings.links_history[:] = [
        entry(
            datetime.combine(today, datetime.min.time()) + timedelta(hours=18),
            url="https://y/never",
            title="Never downloaded mix",
            status="started",
            download_type="audio",
            playlist_mode="playlist",
        ),
        entry(
            datetime.combine(today, datetime.min.time()) + timedelta(hours=7),
            url="https://y/neo",
            title="Neo-Tokyo Ambience",
            status="completed",
            download_type="audio",
        ),
    ]
    return today


def test_merging_dedupes_covered_links_and_sorts_newest_first(filled):
    entries = history.merged_entries()
    assert [e["title"] for e in entries] == [
        "Never downloaded mix",  # 18:00 today
        "Neo-Tokyo Ambience",  # 09:58 today (its 07:00 link row is covered)
        "bot check link",  # 08:52 today
        "Synth Repair Basics",  # yesterday
    ]
    never = entries[0]
    assert never["result"] == "not_downloaded" and never["kind"] == "audio"
    assert never["is_playlist"] is True and never["id"].startswith("l")
    assert entries[1]["result"] == "done" and entries[1]["folder"] == "/music/neo"
    assert entries[2]["result"] == "failed"


def test_group_by_day_labels(filled):
    entries = history.merged_entries()
    groups = history.group_by_day(entries, today=filled)
    assert [label for label, _group in groups] == ["Today", "Yesterday"]
    assert len(groups[0][1]) == 3 and len(groups[1][1]) == 1
    old_date = filled - timedelta(days=400)
    entries.append({"when": datetime.combine(old_date, datetime.min.time()), "title": "old"})
    labels = [label for label, _group in history.group_by_day(entries, today=filled)]
    assert labels[-1] == old_date.strftime("%-d %b %Y")


def test_matches_filters_by_query_and_kind(filled):
    entries = history.merged_entries()
    by_title = [e for e in entries if history.matches(e, "synth", "all")]
    assert [e["title"] for e in by_title] == ["Synth Repair Basics"]
    by_url = [e for e in entries if history.matches(e, "y/never", "all")]
    assert len(by_url) == 1
    audio = [e for e in entries if history.matches(e, "", "audio")]
    assert {e["title"] for e in audio} == {"Never downloaded mix", "Neo-Tokyo Ambience"}
    problems = [e for e in entries if history.matches(e, "", "problems")]
    assert {e["title"] for e in problems} == {"Never downloaded mix", "bot check link"}


def test_remove_entry_deletes_from_the_right_list(filled):
    entries = history.merged_entries()
    never = next(e for e in entries if e["title"] == "Never downloaded mix")
    assert history.remove_entry(never["id"]) is True
    assert [l["url"] for l in settings.links_history] == ["https://y/neo"]
    synth = next(e for e in history.merged_entries() if e["title"] == "Synth Repair Basics")
    assert history.remove_entry(synth["id"]) is True
    assert [d["url"] for d in settings.download_history] == ["https://y/neo", "https://y/bot"]
    assert history.remove_entry("x1") is False
    assert history.remove_entry("d99") is False


def test_clear_older_than_cuts_both_lists_in_place(filled):
    settings.download_history.append(
        entry(datetime.now() - timedelta(days=40), url="https://y/old", title="Old thing", status="completed")
    )
    assert history.count_older_than(30, today=filled) == 1
    removed = history.clear_older_than(30, today=filled)
    assert removed == 1
    assert len(settings.download_history) == 3  # same list object, shortened
    assert history.count_older_than(0, today=filled) == 4  # 0 days: everything is old
    removed = history.clear_older_than(0, today=filled)
    assert removed == 4
    assert settings.download_history == [] and settings.links_history == []


def test_cancelled_and_partial_results(filled):
    settings.download_history.append(
        entry(datetime.now(), url="https://y/part", title="Partial one", status="completed_with_errors")
    )
    results = {e["title"]: e["result"] for e in history.merged_entries()}
    assert results["Partial one"] == "partial"
