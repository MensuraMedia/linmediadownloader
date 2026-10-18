# tests/test_ui_messages.py
"""Every sentence ui/messages.py ships passes the house rules (no shouting, no
urgency words, no raw error codes in headlines) and contains no typed arrow.
No display needed: the module is pure strings."""

from lintheme import status
from ui import messages

ARROWS = ("->", "=>", "→", "⟶")


def module_strings():
    """Every string constant in ui/messages.py, and every string inside ERRORS"""
    found = []
    for name, value in vars(messages).items():
        if name.startswith("__"):
            continue
        if isinstance(value, str):
            found.append((name, value))
        elif isinstance(value, dict):
            for kind, copy in value.items():
                for part, sentence in copy.items():
                    if isinstance(sentence, str):
                        found.append((f"{name}[{kind}].{part}", sentence))
    return found


def test_every_message_is_in_the_module():
    assert len(module_strings()) > 80  # the phase's copy is all here, not inline


def test_every_message_passes_the_house_rules():
    # "UPPER" is the case button that shows its effect in caps, not shouting prose
    case_samples = {messages.LIB_CASE_UPPER}
    breaking = {name: status.problems(text) for name, text in module_strings() if text not in case_samples}
    breaking = {name: problems for name, problems in breaking.items() if problems}
    assert breaking == {}


def test_no_message_contains_a_typed_arrow():
    arrows = {name: [a for a in ARROWS if a in text] for name, text in module_strings()}
    arrows = {name: found for name, found in arrows.items() if found}
    assert arrows == {}


def test_error_copy_names_the_next_step():
    for kind, copy in messages.ERRORS.items():
        assert copy["body"].strip().endswith("."), kind
        assert " " in copy["title"], kind  # a sentence, not a code
