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


def _luhn(numero: str) -> bool:
    """Clé de contrôle des numéros de carte bancaire.

    Sans elle, le motif « 13 à 16 chiffres » attrape n'importe quelle suite de
    nombres. Un rapport de marché en est plein : la suite d'années
    « 2024 2025 2026 … 2031 » a été détectée comme une carte pendant la
    génération d'une étude le 25/08. En mode enforce, ces chiffres auraient été
    remplacés par un marqueur — le rapport aurait perdu ses données.

    Un vrai numéro de carte satisfait Luhn ; une suite de nombres quelconque
    n'a qu'une chance sur dix d'y parvenir par hasard.
    """
    chiffres = [int(c) for c in numero if c.isdigit()]
    if not 13 <= len(chiffres) <= 19:
        return False
    total, pair = 0, False
    for c in reversed(chiffres):
        if pair:
            c *= 2
            if c > 9:
                c -= 9
        total += c
        pair = not pair
    return total % 10 == 0


# Motifs dont la forme ne suffit pas à conclure : une validation supplémentaire
# décide si la correspondance est réelle.
_VALIDATEURS = {"CREDIT_CARD": _luhn}


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
        if kind in _VALIDATEURS:
            valide = _VALIDATEURS[kind]
            text = pattern.sub(
                lambda m, k=kind, v=valide: _sub(k, m) if v(m.group(0)) else m.group(0),
                text)
        else:
            text = pattern.sub(lambda m, k=kind: _sub(k, m), text)
    return text, mapping


def restore(text: str, mapping: dict[str, str]) -> str:
    """Reverse redaction using the mapping (demasking)."""
    for placeholder, original in mapping.items():
        text = text.replace(placeholder, original)
    return text
