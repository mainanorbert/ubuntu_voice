"""Shared validation for user-supplied text fields."""

import re


# C0 and C1 control characters are not safe to persist, render, or log. Chat
# messages deliberately retain common formatting characters for readability.
_DISALLOWED_CONTROLS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_ALL_CONTROLS = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def reject_control_characters(value: str, *, allow_formatting: bool = False) -> str:
    """Reject C0/C1 controls, optionally retaining tabs and line breaks."""
    pattern = _DISALLOWED_CONTROLS if allow_formatting else _ALL_CONTROLS
    if pattern.search(value):
        raise ValueError("Text must not contain control characters.")
    return value
