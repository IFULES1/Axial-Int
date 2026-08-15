"""PII guard — the outbound gate before payloads reach external providers.

Three modes (config `pii_guard_mode`):
  * off      → passthrough, no redaction.
  * shadow   → detect + log what WOULD be redacted, but send the original.
  * enforce  → redact structured PII (and Presidio NER when reachable) before send.

Presidio (the NER sidecar) is best-effort: if it's down or slow, we fall back to
regex-only redaction and never block the request.
"""
from __future__ import annotations

import logging

import httpx

from app.config import get_settings
from app.modules.pii.redaction import redact

logger = logging.getLogger("axial.pii")


def _presidio_entities(text: str, timeout: float = 2.0) -> list[dict]:
    """Ask the Presidio sidecar for NER spans. Empty on any failure."""
    settings = get_settings()
    try:
        resp = httpx.post(
            f"{settings.presidio_url}/analyze",
            json={"text": text, "language": "fr"},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json() if isinstance(resp.json(), list) else resp.json().get("entities", [])
    except Exception as e:
        logger.debug("Presidio unreachable, regex-only: %s", e)
        return []


def _apply_ner(text: str, entities: list[dict]) -> str:
    """Replace NER spans (highest offset first to keep indices valid)."""
    spans = sorted(
        [(e.get("start"), e.get("end"), e.get("entity_type", "PII"))
         for e in entities if e.get("start") is not None and e.get("end") is not None],
        key=lambda s: s[0], reverse=True,
    )
    for start, end, kind in spans:
        text = text[:start] + f"[{kind}]" + text[end:]
    return text


def guard_outbound(text: str) -> str:
    """Return the text to actually send to an external provider, per mode."""
    mode = get_settings().pii_guard_mode
    if mode == "off" or not text:
        return text

    redacted, mapping = redact(text)

    if mode == "shadow":
        if mapping:
            logger.info("PII shadow: %d structured item(s) would be redacted", len(mapping))
        return text  # send original in shadow mode

    # enforce: structured redaction + best-effort NER
    entities = _presidio_entities(redacted)
    if entities:
        redacted = _apply_ner(redacted, entities)
    return redacted
