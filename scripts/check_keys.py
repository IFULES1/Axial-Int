"""Validate provider API keys by making one minimal live call each.

Run with Doppler injecting the secrets:
    doppler run -- .venv/bin/python scripts/check_keys.py

Reports ✅ / ❌ per provider. A red line means the key is missing, invalid, or
the provider rejected the call — the message tells you which.
"""
from __future__ import annotations

import os

import httpx

TIMEOUT = 20.0


def _ok(status: int) -> bool:
    return 200 <= status < 300


def check(name: str, fn) -> None:
    key_present = fn.__doc__  # not used; placeholder
    try:
        status, detail = fn()
        if _ok(status):
            print(f"✅ {name:12} OK ({status})")
        elif status in (401, 403):
            print(f"❌ {name:12} CLÉ INVALIDE / NON AUTORISÉE ({status}) — {detail[:120]}")
        else:
            print(f"⚠️  {name:12} réponse {status} — {detail[:140]}")
    except MissingKey as e:
        print(f"⛔ {name:12} clé manquante ({e})")
    except Exception as e:  # network/other
        print(f"❌ {name:12} erreur: {type(e).__name__}: {str(e)[:120]}")


class MissingKey(Exception):
    pass


def _key(env: str) -> str:
    v = os.getenv(env, "").strip()
    if not v:
        raise MissingKey(env)
    return v


# --- provider checks: each returns (status_code, response_text) ---

def gemini():
    k = _key("GEMINI_API_KEY")
    r = httpx.get(
        f"https://generativelanguage.googleapis.com/v1beta/models?key={k}",
        timeout=TIMEOUT,
    )
    return r.status_code, r.text


def cohere_embed():
    k = _key("COHERE_API_KEY")
    r = httpx.post(
        "https://api.cohere.com/v2/embed",
        headers={"Authorization": f"Bearer {k}", "Content-Type": "application/json"},
        json={"model": "embed-multilingual-v3.0", "texts": ["ping"],
              "input_type": "search_document", "embedding_types": ["float"]},
        timeout=TIMEOUT,
    )
    return r.status_code, r.text


def cohere_rerank():
    k = _key("COHERE_API_KEY")
    r = httpx.post(
        "https://api.cohere.com/v2/rerank",
        headers={"Authorization": f"Bearer {k}", "Content-Type": "application/json"},
        json={"model": "rerank-v3.5", "query": "marché fintech",
              "documents": ["la fintech en France", "recette de cuisine"], "top_n": 1},
        timeout=TIMEOUT,
    )
    return r.status_code, r.text


def tavily():
    k = _key("TAVILY_API_KEY")
    r = httpx.post(
        "https://api.tavily.com/search",
        json={"api_key": k, "query": "ping", "max_results": 1},
        timeout=TIMEOUT,
    )
    return r.status_code, r.text


def exa():
    k = _key("EXA_API_KEY")
    r = httpx.post(
        "https://api.exa.ai/search",
        headers={"x-api-key": k, "Content-Type": "application/json"},
        json={"query": "ping", "numResults": 1},
        timeout=TIMEOUT,
    )
    return r.status_code, r.text


def linkup():
    k = _key("LINKUP_API_KEY")
    r = httpx.post(
        "https://api.linkup.so/v1/search",
        headers={"Authorization": f"Bearer {k}", "Content-Type": "application/json"},
        json={"q": "ping", "depth": "standard", "outputType": "searchResults"},
        timeout=TIMEOUT,
    )
    return r.status_code, r.text


def anthropic():
    k = _key("ANTHROPIC_API_KEY")
    r = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": k, "anthropic-version": "2023-06-01",
                 "Content-Type": "application/json"},
        json={"model": "claude-sonnet-5", "max_tokens": 10,
              "messages": [{"role": "user", "content": "ping"}]},
        timeout=TIMEOUT,
    )
    return r.status_code, r.text


def main() -> int:
    print("=== Validation des clés API (appel live par provider) ===\n")
    check("Gemini", gemini)
    check("Cohere embed", cohere_embed)
    check("Cohere rerank", cohere_rerank)
    check("Tavily", tavily)
    check("Exa", exa)
    check("Linkup", linkup)
    check("Anthropic", anthropic)
    print("\n(✅ = clé OK · ❌ = à corriger · ⚠️ = clé OK mais payload à ajuster · ⛔ = clé absente)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
