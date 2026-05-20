"""Phone number normalization utility for duplicate detection.

Strategy: strip all non-digit characters, then use the last 10 digits as the
canonical form. This handles international prefixes (+1, 00XX) gracefully while
comparing numbers that refer to the same local number.
"""
from __future__ import annotations

import re


def normalize_phone(phone: str | None) -> str | None:
    """Return a canonical 10-digit phone string, or None if not parseable.

    Examples
    --------
    >>> normalize_phone("+1 (555) 123-4567")
    '5551234567'
    >>> normalize_phone("0091-9876543210")
    '9876543210'
    >>> normalize_phone(None)
    None
    >>> normalize_phone("123")  # too short
    None
    """
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 10:
        return None
    return digits[-10:]
