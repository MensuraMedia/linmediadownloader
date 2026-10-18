# ui/poller.py
"""Reads the download state on the main loop while a download runs.

GLib.timeout_add(250) calls jobs.status_snapshot() and hands each listener a
copy (the worker thread keeps mutating the original). The poller stops once a
final status (completed, completed_with_errors, cancelled, error) has been
delivered and nothing is left in the queue; the tick that sees the final status
is the one that delivers it. Nothing here touches widgets from a thread: the
snapshot is read on the main loop and page code runs there.
"""

import logging

from gi.repository import GLib

from modules.download import jobs

logger = logging.getLogger("lmd.ui.poller")

ACTIVE_STATUSES = ("starting", "downloading", "processing")
FINAL_STATUSES = ("completed", "completed_with_errors", "cancelled", "error")
INTERVAL_MS = 250


def snapshot_copy():
    """A detached copy of jobs.status_snapshot(): per-track states copied too."""
    snap = jobs.status_snapshot()
    snap["tracks"] = {key: dict(track) for key, track in (snap.get("tracks") or {}).items()}
    return snap


class SnapshotPoller:
    """start() delivers one snapshot at once, then one every INTERVAL_MS."""

    def __init__(self, on_snapshot, interval_ms=INTERVAL_MS):
        self._listeners = [on_snapshot]
        self._interval_ms = interval_ms
        self._source = None

    @property
    def running(self):
        return self._source is not None

    def add_listener(self, on_snapshot):
        if on_snapshot not in self._listeners:
            self._listeners.append(on_snapshot)

    def start(self):
        """Poll at once and keep polling; a second start() while running does nothing."""
        if self._source is not None:
            return
        self._source = GLib.timeout_add(self._interval_ms, self._tick)
        self._deliver()

    def stop(self):
        if self._source is not None:
            GLib.source_remove(self._source)
            self._source = None

    def _tick(self):
        return self._deliver()

    def _deliver(self):
        try:
            snap = snapshot_copy()
        except Exception:  # never let a read failure spin the timer forever
            logger.exception("status snapshot failed")
            return True
        for listener in list(self._listeners):
            listener(snap)
        if snap.get("status") in FINAL_STATUSES and not snap.get("queue_pending"):
            self._source = None  # this tick delivered the final status: stop here
            return False
        return True
