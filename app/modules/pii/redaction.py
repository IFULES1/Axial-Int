"""Deterministic PII redaction — pure functions, no I/O.

Regex-based detection for the structured PII types (email, French/intl phone,
IBAN, credit card, NIR). Produces placeholder-substituted text plus a reversible
mapping. NER (names, locations) is handled separately by the Presidio sidecar.
"""
from __future__ import annotations

import re

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")),
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}\b")),
    # Phone before credit card so it isn't swallowed by the digit run.
    ("PHONE_FR", re.compile(r"(?:\+33|0)\s?[1-9](?:[\s.-]?\d{2}){4}")),
    ("NIR", re.compile(r"\b[12]\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{3}\s?\d{3}\s?\d{2}\b")),
    ("CREDIT_CARD", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
]


def redact(text: str) -> tuple[str, dict[str, str]]:
    """Return (redacted_text, mapping placeholder→original)."""
    mapping: dict[str, str] = {}
    counters: dict[str, int] = {}

    def _sub(kind: str, match: re.Match) -> str:
        original = match.group(0)
        counters[kind] = counters.get(kind, 0) + 1
        placeholder = f"[{kind}_{counters[kind]}]"
        mapping[placeholder] = original
        return placeholder

    for kind, pattern in _PATTERNS:
        text = pattern.sub(lambda m, k=kind: _sub(k, m), text)
    return text, mapping


def restore(text: str, mapping: dict[str, str]) -> str:
    """Reverse redaction using the mapping (demasking)."""
    for placeholder, original in mapping.items():
        text = text.replace(placeholder, original)
    return text
