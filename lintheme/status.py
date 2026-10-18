"""
The status vocabulary and the message pattern, shared by every Lin* app.

Four device states, each always shown as an icon AND a word (never colour
alone), the same everywhere: header chip, page cards, device page.

Messages follow one pattern: what happened · why (with evidence) · the next
step. The rules come from LinPrinter's 2026 USB incident: say where the fault
is, lead with the cheapest physical check, and never present a guess as fact.
"""

from collections import namedtuple

Status = namedtuple("Status", "key word icon css")

STATUSES = {
    "ok": Status("ok", "Ready", "check-circle", "lt-ok"),
    "busy": Status("busy", "Busy", "circle-notch", "lt-busy"),
    "attention": Status("attention", "Needs you", "warning", "lt-attention"),
    "error": Status("error", "Can't reach", "link-break", "lt-error"),
    "none": Status("none", "Not found yet", "magnifying-glass", "lt-none"),
}

# Words that create false urgency (no dark patterns): allowed only when something will be lost
URGENCY_WORDS = ("immediately", "critical", "urgent", "hurry", "act now", "warning!")

CABLE_FIRST = (
    "Try another USB cable first, plugged straight into the computer — a faulty cable is the most "
    "common cause, even one that worked for a while. No driver or setting fixes this."
)


def status(key):
    """The Status for 'ok', 'busy', 'attention', 'error' or 'none'"""
    return STATUSES[key]


def chip_text(device, key):
    """'Canon TR150 · Ready'"""
    return f"{device} · {STATUSES[key].word}" if device else STATUSES[key].word


def message(what, why=None, next_step=None):
    """One message in the house pattern: 'What happened. Why. Next step.'"""
    parts = [what.rstrip(".") + "."]
    if why:
        parts.append(why.rstrip(".") + ".")
    if next_step:
        parts.append(next_step.rstrip(".") + ".")
    return " ".join(parts)


def problems(text):
    """Reasons a user-facing message breaks the house rules ([] = fine)"""
    found = []
    low = text.lower()
    for word in URGENCY_WORDS:
        if word in low:
            found.append(f"urgency word: {word!r}")
    if any(code in text for code in ("errno", "EPROTO", "HTTP 5", "-71", "Traceback")) and "(" not in text:
        found.append(
            "raw error code in the headline: put it in Details, or in brackets after the plain words"
        )
    if text.isupper():
        found.append("shouting (all capitals)")
    return found
