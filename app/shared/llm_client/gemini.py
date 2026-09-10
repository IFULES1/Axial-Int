"""Gemini generation provider (Google AI Studio REST).

Cheap/fast tier for chat and draft analyses. Pure text generation — web search
is handled separately by the search orchestrator.
"""
from __future__ import annotations

import logging
import time

import httpx

from app.config import get_settings
from app.shared.llm_client.base import (
    LLMResult,
    ProviderUnavailable,
    cumuler_mesure,
)

logger = logging.getLogger("axial.llm.gemini")
_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
_TRANSIENT = {429, 500, 502, 503, 504}  # retryable server-side / rate errors


def available() -> bool:
    return bool(get_settings().gemini_api_key)


def _contents(history: list[dict] | None, prompt: str) -> list[dict]:
    """Tours passés + question courante, au format `contents` de Gemini.

    Gemini nomme « model » ce que Claude appelle « assistant » : c'est la seule
    différence, l'appelant fournit un historique unique pour les deux.
    """
    tours: list[dict] = []
    for m in history or []:
        texte = (m.get("content") or "").strip()
        if not texte:
            continue
        role = "model" if m.get("role") == "assistant" else "user"
        tours.append({"role": role, "parts": [{"text": texte}]})
    return tours + [{"role": "user", "parts": [{"text": prompt}]}]


def generate(*, system: str, prompt: str, model: str | None = None,
             max_tokens: int = 4000, history: list[dict] | None = None) -> LLMResult:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise ProviderUnavailable("GEMINI_API_KEY non configurée")
    model = model or settings.llm_chat_model
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": _contents(history, prompt),
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.3},
    }
    url = f"{_BASE}/{model}:generateContent?key={settings.gemini_api_key}"
    # ONE quick retry only: catches a truly transient blip, but if Gemini is
    # having a sustained bad time we want to fail over to Claude fast (the caller
    # in llm_client.generate handles that) rather than stall the user for ~10s.
    for attempt in range(2):
        r = httpx.post(url, json=payload, timeout=120.0)
        if r.status_code in _TRANSIENT and attempt < 1:
            logger.warning("Gemini %s (transitoire), 1 retry rapide", r.status_code)
            time.sleep(1.0)
            continue
        break
    r.raise_for_status()
    data = r.json()
    candidates = data.get("candidates") or []
    text = ""
    raison = None
    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)
        # Gemini nomme « MAX_TOKENS » ce que Claude appelle « max_tokens ».
        # On normalise pour que l'appelant n'ait qu'un seul cas à traiter.
        if candidates[0].get("finishReason") == "MAX_TOKENS":
            raison = "max_tokens"
    usage = data.get("usageMetadata") or {}
    tokens = usage.get("totalTokenCount", 0) or 0
    return LLMResult(text=text, model=model, provider="gemini", tokens=tokens,
                     stop_reason=raison,
                     input_tokens=usage.get("promptTokenCount", 0) or 0,
                     output_tokens=usage.get("candidatesTokenCount", 0) or 0)


def stream(*, system: str, prompt: str, model: str | None = None,
           max_tokens: int = 4000, history: list[dict] | None = None,
           mesure: dict | None = None):
    """Yield text chunks as they are produced (SSE variant of generate()).

    **Valeur de retour** : le `stop_reason` normalisé (`max_tokens` pour le
    `MAX_TOKENS` de Gemini), lisible par l'appelant via `yield from`.

    `mesure` — dictionnaire rempli du modèle et des tokens consommés, pour que
    le coût d'une réponse en flux soit mesurable comme celui d'une réponse
    bloquante.
    """
    import json

    settings = get_settings()
    if not settings.gemini_api_key:
        raise ProviderUnavailable("GEMINI_API_KEY non configurée")
    model = model or settings.llm_chat_model
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": _contents(history, prompt),
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.3},
    }
    url = f"{_BASE}/{model}:streamGenerateContent?alt=sse&key={settings.gemini_api_key}"
    raison = None
    with httpx.stream("POST", url, json=payload, timeout=180.0) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            try:
                data = json.loads(line[5:].strip())
            except ValueError:
                continue
            # `usageMetadata` arrive sur les derniers chunks : on garde le
            # dernier vu, c'est le décompte complet de la réponse.
            usage = data.get("usageMetadata") or {}
            if mesure is not None and usage:
                mesure["_dernier_usage"] = usage
            for cand in data.get("candidates") or []:
                # `finishReason` n'apparaît que sur les derniers chunks : on
                # garde le dernier vu, normalisé comme dans generate().
                fin = cand.get("finishReason")
                if fin:
                    raison = "max_tokens" if fin == "MAX_TOKENS" else str(fin).lower()
                for part in (cand.get("content") or {}).get("parts") or []:
                    chunk = part.get("text")
                    if chunk:
                        yield chunk
    if mesure is not None:
        usage = mesure.pop("_dernier_usage", None) or {}
        if usage:
            cumuler_mesure(mesure, model, "gemini",
                           usage.get("promptTokenCount", 0) or 0,
                           usage.get("candidatesTokenCount", 0) or 0)
    return raison
