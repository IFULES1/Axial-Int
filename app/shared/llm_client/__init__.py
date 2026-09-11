"""llm_client — provider accessors and health.

Business code imports `web_search_provider()` / `enrich_provider()` and the
`providers_health()` helper; it never imports a concrete vendor module.
"""
from __future__ import annotations

import re

from app.shared.llm_client.base import (
    EnrichProvider,
    LLMResult,
    ProviderUnavailable,
    WebSearchProvider,
    resultat_de_mesure,
)
from app.shared.llm_client.claude import ClaudeProvider
from app.shared.llm_client.perplexity import PerplexityProvider

_web = PerplexityProvider()
_enrich = ClaudeProvider()

# httpx met l'URL complète dans le message d'erreur — clé d'API comprise quand
# elle voyage en paramètre de requête (Gemini). Elle finissait en clair dans
# le journal systemd à chaque bascule de fournisseur.
_SECRET_DANS_URL = re.compile(r"([?&](?:key|api_key|apikey|token)=)[^&'\"\s]+", re.IGNORECASE)


def _sans_secret(err: BaseException | str) -> str:
    """Masque la clé d'API d'une URL dans un message d'erreur OU un texte.

    Accepte aussi une chaîne : `app.shared.notifier` passe le traceback complet
    d'un incident avant de l'envoyer par email, et il n'y a aucune raison d'en
    tenir une deuxième copie du motif.
    """
    return _SECRET_DANS_URL.sub(r"\1<masqué>", str(err))


def web_search_provider() -> WebSearchProvider:
    return _web


def enrich_provider() -> EnrichProvider:
    return _enrich


def generation_available() -> bool:
    """True if at least one text-generation LLM (Gemini or Claude) is usable."""
    from app.shared.llm_client import claude, gemini

    return gemini.available() or claude.available()


def generate(*, system: str, prompt: str, tier: str = "chat",
             max_tokens: int = 4000, mcp_servers: list | None = None,
             mcp_tools: list | None = None,
             history: list[dict] | None = None) -> LLMResult:
    """Two-tier text generation with runtime failover.

    tier="report" → Claude first (premium, final reports); tier="chat"/"draft" →
    Gemini first (cheap/fast). If the preferred provider fails at runtime
    (e.g. a transient 503), fall back to the other configured provider.

    `history` — tours précédents `[{"role": "user"|"assistant", "content": str}]`,
    transmis tel quel aux deux fournisseurs (`messages` chez Claude, `contents`
    avec `role: "model"` chez Gemini). Absent = requête sans mémoire, comme avant.
    """
    import logging

    from app.shared.llm_client import claude, gemini

    logger = logging.getLogger("axial.llm")
    chain = ([("claude", claude), ("gemini", gemini)] if tier == "report"
             else [("gemini", gemini), ("claude", claude)])

    last_err: Exception | None = None
    for name, mod in chain:
        if not mod.available():
            continue
        try:
            # Seul Claude sait joindre des serveurs MCP ; Gemini reste le repli
            # sans outils plutôt que d'échouer.
            if mcp_servers and name == "claude":
                return mod.generate(system=system, prompt=prompt,
                                    max_tokens=max_tokens, history=history,
                                    mcp_servers=mcp_servers, mcp_tools=mcp_tools)
            return mod.generate(system=system, prompt=prompt,
                                max_tokens=max_tokens, history=history)
        except Exception as e:  # noqa: BLE001 — try the next provider, whatever the cause
            last_err = e
            logger.warning("LLM %s a échoué, bascule sur le suivant : %s", name, _sans_secret(e))
    if last_err:
        raise last_err
    raise ProviderUnavailable("Aucun LLM de génération configuré (Gemini/Claude).")


def stream_text(*, system: str, prompt: str, tier: str = "chat",
                max_tokens: int = 4000, mcp_servers: list | None = None,
                mcp_tools: list | None = None,
                history: list[dict] | None = None,
                mesure: dict | None = None):
    """Streaming counterpart of generate(): yields text chunks.

    Failover only applies BEFORE the first chunk — once text has reached the
    user, switching provider mid-answer would splice two different replies
    together, so a late failure surfaces as an error instead.

    **Valeur de retour** : le `stop_reason` du fournisseur qui a répondu
    (`raison = yield from llm_client.stream_text(...)`). `max_tokens` dit à
    l'appelant que la réponse est coupée et qu'il peut la faire reprendre.

    `mesure` — dictionnaire rempli par le fournisseur (modèle, tokens
    d'entrée et de sortie, cumulés d'un appel à l'autre) : c'est ce qui rend
    le coût d'une réponse en flux mesurable. `resultat_de_mesure` en fait un
    `LLMResult`.
    """
    import logging

    from app.shared.llm_client import claude, gemini

    logger = logging.getLogger("axial.llm")
    chain = ([("claude", claude), ("gemini", gemini)] if tier == "report"
             else [("gemini", gemini), ("claude", claude)])

    last_err: Exception | None = None
    for name, mod in chain:
        if not mod.available():
            continue
        started = False
        flux = None
        try:
            extra = ({"mcp_servers": mcp_servers, "mcp_tools": mcp_tools}
                     if (mcp_servers and name == "claude") else {})
            flux = mod.stream(system=system, prompt=prompt, history=history,
                              max_tokens=max_tokens, mesure=mesure, **extra)
            # `next()` explicite plutôt qu'un `for` : c'est le seul moyen de
            # récupérer la valeur de retour du générateur du fournisseur (le
            # `stop_reason`) tout en gardant le drapeau `started`.
            while True:
                try:
                    chunk = next(flux)
                except StopIteration as fin:
                    return fin.value
                started = True
                yield chunk
        except Exception as e:  # noqa: BLE001
            if started:
                logger.warning("LLM %s a coupé en cours de réponse : %s", name, _sans_secret(e))
                raise
            last_err = e
            logger.warning("LLM %s a échoué avant le 1er mot, bascule : %s", name, _sans_secret(e))
        finally:
            # Fermer le générateur du fournisseur dans un `finally`, et pas
            # seulement dans l'`except` : sur un Stop, c'est un `GeneratorExit`
            # (une `BaseException`) qui traverse le `yield chunk`, l'`except
            # Exception` ne le voyait pas et le générateur du fournisseur
            # restait ouvert — donc son `finally` de mesure ne tournait pas et
            # le `with httpx.stream(...)` / `with espace.stream(...)` ne se
            # refermait qu'au ramasse-miettes. Sur le chemin normal, le
            # générateur est déjà épuisé : `close()` ne fait rien.
            if flux is not None:
                try:
                    flux.close()
                except Exception as fermeture:  # noqa: BLE001
                    logger.warning("Flux %s non refermé : %s", name,
                                   _sans_secret(fermeture))
    if last_err:
        raise last_err
    raise ProviderUnavailable("Aucun LLM de génération configuré (Gemini/Claude).")


def providers_health() -> dict[str, bool]:
    """Real availability of each provider, for GET /health/providers."""
    from app.shared.llm_client import claude, gemini

    return {"gemini": gemini.available(), "claude": claude.available(),
            "perplexity": _web.available()}


__all__ = [
    "web_search_provider",
    "enrich_provider",
    "generate",
    "stream_text",
    "resultat_de_mesure",
    "generation_available",
    "providers_health",
    "LLMResult",
    "ProviderUnavailable",
    "WebSearchProvider",
    "EnrichProvider",
]
