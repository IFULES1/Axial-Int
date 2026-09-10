"""Claude enrichment provider.

Second-pass refinement of a draft report. No web search (deliberate: avoids
extra search cost). Gated by CLAUDE_ENRICHMENT_ENABLED + a valid key. Absence
disables enrichment cleanly.
"""
from __future__ import annotations

import logging

from app.config import get_settings
from app.shared.llm_client.base import (
    LLMResult,
    ProviderUnavailable,
    cumuler_mesure,
)

logger = logging.getLogger("axial.llm.claude")


def available() -> bool:
    return bool(get_settings().anthropic_api_key)


# Nombre maximal de reprises après troncature. Trois suffisent : au-delà, le
# problème n'est plus un plafond de sortie mais une consigne de volume absurde.
MAX_REPRISES = 3

SUITE_CONSIGNE = (
    "Ta réponse a été coupée par la limite de sortie. Reprends EXACTEMENT là où "
    "tu t'es arrêté, au caractère près — ne répète rien, ne réécris pas le début, "
    "n'ajoute ni introduction ni rappel. Si la coupure tombe au milieu d'un mot, "
    "commence par la fin de ce mot. Poursuis jusqu'à la conclusion du document."
)


def _messages(history: list[dict] | None, prompt: str) -> list[dict]:
    """Tour utilisateur courant précédé des tours passés.

    `history` arrive déjà nettoyé et alterné par l'appelant (voir
    `intelligence.service._historique`) : on le recopie tel quel plutôt que de
    dupliquer ici une logique de conversation.
    """
    tours = [{"role": m["role"], "content": m["content"]}
             for m in (history or []) if (m.get("content") or "").strip()]
    return tours + [{"role": "user", "content": prompt}]


def generate(*, system: str, prompt: str, model: str | None = None,
             max_tokens: int = 4000, mcp_servers: list | None = None,
             mcp_tools: list | None = None,
             history: list[dict] | None = None) -> LLMResult:
    """General text generation (premium tier — final reports).

    `mcp_servers` / `mcp_tools` branchent les outils du client (Notion…) :
    Claude interroge alors son espace de travail pendant la rédaction. Les deux
    listes vont ensemble — un serveur déclaré sans son `mcp_toolset` est rejeté.

    `history` — tours précédents (`{role, content}`), passés tels quels dans
    `messages` avant la question courante : c'est la mémoire de fil.
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise ProviderUnavailable("ANTHROPIC_API_KEY non configurée")
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    model = model or settings.llm_report_model
    kwargs = {
        "model": model, "max_tokens": max_tokens, "system": system,
        "messages": _messages(history, prompt),
    }
    if mcp_servers and mcp_tools:
        kwargs["mcp_servers"] = mcp_servers
        kwargs["tools"] = mcp_tools
        kwargs["betas"] = ["mcp-client-2025-11-20"]
    # Au-delà de ~16k tokens de sortie, une requête bloquante expire côté HTTP :
    # le SDK impose le streaming. On agrège nous-mêmes le message final.
    espace = client.beta.messages if "betas" in kwargs else client.messages

    def _appel(msgs: list[dict]):
        k = dict(kwargs, messages=msgs)
        if max_tokens > 16000:
            with espace.stream(**k) as stream:
                return stream.get_final_message()
        return espace.create(**k)

    def _texte(msg) -> str:
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")

    def _usage(msg) -> tuple[int, int]:
        u = getattr(msg, "usage", None)
        if u is None:
            return 0, 0
        return (getattr(u, "input_tokens", 0) or 0), (getattr(u, "output_tokens", 0) or 0)

    def _tokens(msg) -> int:
        e, s = _usage(msg)
        return e + s

    messages = list(kwargs["messages"])
    message = _appel(messages)
    texte, tokens = _texte(message), _tokens(message)
    entree, sortie = _usage(message)
    raison = getattr(message, "stop_reason", None)

    # Reprise automatique. Un rapport long peut atteindre le plafond de sortie
    # avant sa conclusion : le modèle s'arrête alors en plein mot. On lui rend
    # ce qu'il a écrit et on lui demande de poursuivre exactement là où il s'est
    # arrêté, plutôt que de livrer un document coupé — ce qui est arrivé en
    # production le 24/08 sur une étude de marché.
    reprises = 0
    while raison == "max_tokens" and reprises < MAX_REPRISES and texte.strip():
        reprises += 1
        logger.info("Sortie tronquée (%s), reprise %d/%d", model, reprises, MAX_REPRISES)
        messages = messages + [
            {"role": "assistant", "content": texte},
            {"role": "user", "content": SUITE_CONSIGNE},
        ]
        suite = _appel(messages)
        morceau = _texte(suite)
        if not morceau.strip():
            break
        # Recollage sans espace parasite : la coupure tombe souvent en plein mot.
        texte += morceau
        tokens += _tokens(suite)
        e2, s2 = _usage(suite)
        entree += e2
        sortie += s2
        raison = getattr(suite, "stop_reason", None)

    return LLMResult(text=texte, model=model, provider="claude", tokens=tokens,
                     stop_reason=raison, input_tokens=entree, output_tokens=sortie)


class ClaudeProvider:
    name = "claude"

    def available(self) -> bool:
        s = get_settings()
        return bool(s.claude_enrichment_enabled and s.anthropic_api_key)

    def enrich(self, *, system: str, draft: str, model: str | None = None,
               max_tokens: int = 8000) -> LLMResult:
        settings = get_settings()
        if not (settings.claude_enrichment_enabled and settings.anthropic_api_key):
            raise ProviderUnavailable("Claude enrichment désactivé ou clé absente")

        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        model = model or settings.claude_enrichment_model
        message = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": draft}],
        )
        text = "".join(b.text for b in message.content if getattr(b, "type", "") == "text")
        usage = getattr(message, "usage", None)
        tokens = 0
        if usage is not None:
            tokens = (getattr(usage, "input_tokens", 0) or 0) + (
                getattr(usage, "output_tokens", 0) or 0
            )
        return LLMResult(text=text, model=model, provider=self.name, tokens=tokens)


def stream(*, system: str, prompt: str, model: str | None = None,
           max_tokens: int = 4000, mcp_servers: list | None = None,
           mcp_tools: list | None = None, history: list[dict] | None = None,
           mesure: dict | None = None):
    """Yield text chunks as they are produced (streaming variant of generate()).

    Avec des serveurs MCP, les appels d'outils sont exécutés côté Anthropic :
    le flux de texte reste le même pour l'appelant, il marque simplement une
    pause pendant que Claude interroge l'outil.

    **Valeur de retour** : le `stop_reason` du message final (`return`, donc
    lisible par l'appelant avec `raison = yield from stream(...)`). Sans elle,
    une réponse coupée par le plafond de sortie est indiscernable en flux d'une
    réponse terminée — et le service ne peut pas la reprendre.

    `mesure` — dictionnaire fourni par l'appelant, rempli du modèle et des
    tokens consommés (cumulés si le même dictionnaire sert à plusieurs appels).
    Sans lui, une réponse en flux n'a ni tokens ni coût mesuré, alors que le
    flux est le chemin normal du chat.
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise ProviderUnavailable("ANTHROPIC_API_KEY non configurée")
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    model = model or settings.llm_report_model
    kwargs = {
        "model": model, "max_tokens": max_tokens, "system": system,
        "messages": _messages(history, prompt),
    }
    if mcp_servers and mcp_tools:
        kwargs["mcp_servers"] = mcp_servers
        kwargs["tools"] = mcp_tools
        kwargs["betas"] = ["mcp-client-2025-11-20"]
    espace = client.beta.messages if "betas" in kwargs else client.messages
    raison = None
    mesure_faite = False
    ecrit = 0  # caractères livrés, pour l'estimation de repli sur interruption
    with espace.stream(**kwargs) as s:
        try:
            for morceau in s.text_stream:
                ecrit += len(morceau)
                yield morceau
            # Le message final n'est complet qu'à l'intérieur du `with`. Tolérant :
            # un SDK qui ne le fournit pas ne doit pas casser un flux déjà livré.
            try:
                final = s.get_final_message()
                raison = getattr(final, "stop_reason", None)
                if mesure is not None:
                    cumuler_mesure(mesure, model, "claude",
                                   *_usage_de(getattr(final, "usage", None)))
                    mesure_faite = True
            except Exception as e:  # noqa: BLE001
                logger.warning("stop_reason indisponible en flux : %s", e)
        finally:
            # Interruption (Stop du client → `GeneratorExit`) ou erreur tardive :
            # `get_final_message()` n'est plus disponible, mais les tokens ont
            # bien été payés. On les récupère du dernier instantané du SDK, et
            # à défaut on estime la sortie depuis le texte livré (≈ 4 caractères
            # par token) : une mesure approchée vaut mieux qu'un partiel archivé
            # à coût nul, qui fausse les métriques de marge dans l'autre sens.
            if mesure is not None and not mesure_faite:
                entree, sortie = _usage_instantane(s)
                if not sortie and ecrit:
                    sortie = max(1, ecrit // 4)
                if entree or sortie:
                    cumuler_mesure(mesure, model, "claude", entree, sortie)
    return raison


def _usage_de(u) -> tuple[int, int]:
    if u is None:
        return 0, 0
    return (getattr(u, "input_tokens", 0) or 0), (getattr(u, "output_tokens", 0) or 0)


def _usage_instantane(s) -> tuple[int, int]:
    """Tokens déjà comptés par le SDK au moment de l'interruption, ou (0, 0).

    `current_message_snapshot` porte l'`usage` reconstruit depuis les événements
    reçus : l'entrée est connue dès le `message_start`, la sortie est cumulée au
    fil des deltas. Tolérant : un SDK qui n'expose rien ne doit pas transformer
    une interruption en erreur.
    """
    try:
        return _usage_de(getattr(s.current_message_snapshot, "usage", None))
    except Exception as e:  # noqa: BLE001
        logger.warning("usage indisponible sur interruption : %s", e)
        return 0, 0
