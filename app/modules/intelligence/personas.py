"""Agent personas — a generic, configurable engine.

The two native agents (Market Scanner / PESTEL and Competitor Radar / Porter)
are just entries in a registry of `AgentPersona`. Custom agents (the Startup Pro
plan's "up to 10") will be built from DB rows into the same dataclass, so the
message pipeline treats native and custom agents identically.

Two product mechanisms live here:
  * **Non-overlap routing**: each persona owns a scope; a query that belongs to
    the other agent triggers an explicit redirect.
  * **"AXIAL Recommande"**: every agent answer ends with 2-3 sentences stating
    what to DO with the findings — the product differentiator.
"""
from __future__ import annotations

from dataclasses import dataclass, field

AXIAL_RECOMMENDE_INSTRUCTION = (
    "\n\nTermine IMPÉRATIVEMENT ta réponse par un bloc intitulé exactement "
    "'**AXIAL Recommande**' : 2-3 phrases qui ne se contentent pas de rapporter "
    "les signaux, mais disent explicitement quoi en faire — quel mouvement de "
    "positionnement, quoi surveiller, quoi éviter."
)


@dataclass
class AgentPersona:
    key: str
    name: str
    framework: str
    system_prompt: str
    scope_keywords: list[str] = field(default_factory=list)
    redirect_to: str | None = None
    redirect_hint: str = ""

    def full_system_prompt(self) -> str:
        return self.system_prompt + AXIAL_RECOMMENDE_INSTRUCTION


MARKET_SCANNER = AgentPersona(
    key="market_scanner",
    name="Market Scanner",
    framework="PESTEL",
    system_prompt=(
        "Tu es Market Scanner, un agent d'analyse stratégique fondé sur le cadre "
        "PESTEL. Analyse les forces macro du marché : Politique, Économique, Social, "
        "Technologique, Environnemental, Légal. Réponds de façon sourcée et "
        "structurée. Tu ne traites PAS l'analyse concurrentielle directe (rivalité, "
        "concurrents) — c'est le périmètre de Competitor Radar."
    ),
    scope_keywords=[
        "marché", "macro", "réglementation", "régulation", "tendance", "secteur",
        "politique", "économique", "social", "environnement", "légal", "pestel",
        "attractivité", "expansion", "entrée sur", "croissance du marché",
    ],
    redirect_to="competitor_radar",
    redirect_hint=(
        "Ta question porte surtout sur la concurrence — Competitor Radar (Porter) "
        "est mieux adapté."
    ),
)

COMPETITOR_RADAR = AgentPersona(
    key="competitor_radar",
    name="Competitor Radar",
    framework="Porter",
    system_prompt=(
        "Tu es Competitor Radar, un agent d'analyse concurrentielle fondé sur les "
        "5 forces de Porter : rivalité, menace de nouveaux entrants, menace des "
        "substituts, pouvoir des acheteurs, pouvoir des fournisseurs. Réponds de "
        "façon sourcée et structurée. Tu ne traites PAS les forces macro du marché "
        "(régulation, tendances sectorielles larges) — c'est le périmètre de Market "
        "Scanner."
    ),
    scope_keywords=[
        "concurrent", "concurrence", "rival", "rivalité", "positionnement",
        "part de marché", "barrière", "entrant", "substitut", "fournisseur",
        "acheteur", "porter", "différenciation", "pricing", "prix", "mapping",
    ],
    redirect_to="market_scanner",
    redirect_hint=(
        "Ta question porte surtout sur les forces macro du marché — Market Scanner "
        "(PESTEL) est mieux adapté."
    ),
)

AXIAL_CONSEIL = AgentPersona(
    key="conseiller",
    name="Axial Conseil",
    framework="Conversation libre",
    system_prompt=(
        "Tu es Axial Conseil, le copilote stratégique généraliste d'un fondateur de "
        "startup. Tu réponds à toute question stratégique ou opérationnelle — GTM, "
        "levée de fonds, produit, organisation, pricing — de façon sourcée, "
        "structurée et actionnable. Quand la question relève clairement d'une "
        "analyse macro-marché (PESTEL) ou concurrentielle (Porter), tu peux le "
        "signaler, mais tu réponds toujours au mieux toi-même."
    ),
    scope_keywords=[],
)

_REGISTRY: dict[str, AgentPersona] = {
    MARKET_SCANNER.key: MARKET_SCANNER,
    COMPETITOR_RADAR.key: COMPETITOR_RADAR,
    AXIAL_CONSEIL.key: AXIAL_CONSEIL,
}

DEFAULT_AGENT = MARKET_SCANNER.key

# Mode "conversation libre" : le sélecteur du Workspace envoie cette valeur pour
# laisser Axial router lui-même vers le bon agent selon l'intention.
AUTO = "auto"


def get_persona(key: str) -> AgentPersona | None:
    return _REGISTRY.get(key)


def list_personas() -> list[AgentPersona]:
    return list(_REGISTRY.values())


def _score(query: str, persona: AgentPersona) -> int:
    q = query.lower()
    return sum(1 for kw in persona.scope_keywords if kw in q)


def route(query: str, requested: str | None = None) -> tuple[str, str | None]:
    """Pick the best agent for a query.

    Returns (agent_key, redirect_note).
    * `requested` = AUTO or None → real intent routing: the best-scoring
      specialist answers; a generic question falls to Axial Conseil. Never a
      redirect note — the switch IS the feature.
    * `requested` = explicit persona → the user's choice is respected; if the
      query clearly belongs to the other specialist we keep the choice but
      return a hint (non-overlap mechanism, non-destructive).
    """
    scores = {p.key: _score(query, p) for p in _REGISTRY.values()}
    best = max(scores, key=scores.get)

    if requested and requested != AUTO and requested in _REGISTRY:
        other = _REGISTRY[requested].redirect_to
        if other and scores.get(other, 0) >= 2 and scores[other] > scores[requested]:
            return requested, _REGISTRY[requested].redirect_hint
        return requested, None

    # Conversation libre : router selon l'intention, généraliste par défaut.
    if scores[best] == 0:
        return AXIAL_CONSEIL.key, None
    return best, None
