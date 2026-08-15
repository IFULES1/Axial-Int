"""Veille skills — specialised monitoring expertises.

Each skill focuses an agent on a specific strategic surface, so the veille is
targeted (not a generic founder-profile digest). A skill carries: a system prompt
that shapes what to look for, the RSS feed categories it prefers, and a template
that turns the agent's subject into a sharp web-search query. The engine stays
generic — add a skill here and it is immediately available.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class VeilleSkill:
    key: str
    name: str
    focus: str                       # one-line description shown in the UI
    system_prompt: str               # what this agent hunts for
    rss_categories: list[str] = field(default_factory=list)
    web_query_template: str = "{subject} actualité récente"


_INTRO = (
    "Tu es un agent de veille stratégique spécialisé. Tu produis une veille CIBLÉE, "
    "pas un rapport générique. Tu t'appuies sur ta mémoire roulante (ce que tu as déjà "
    "rapporté) pour ne remonter que les signaux NOUVEAUX ou qui ont évolué, et tu relies "
    "chaque signal à son implication concrète pour l'entreprise suivie.\n\n"
)


CONCURRENTIELLE = VeilleSkill(
    key="concurrentielle",
    name="Veille concurrentielle",
    focus="Mouvements des concurrents : levées, lancements, pricing, recrutements, positionnement.",
    system_prompt=_INTRO + (
        "Ton champ : la CONCURRENCE. Traque les mouvements des acteurs du marché suivi — "
        "nouveaux entrants, lancements et évolutions produit, changements de pricing, "
        "levées de fonds de concurrents, recrutements de dirigeants, partenariats, "
        "repositionnements. Pour chaque signal : qui, quoi, quand, et ce que ça implique "
        "pour la position concurrentielle de l'entreprise suivie."
    ),
    # Les mouvements concurrents transparaissent dans les lancements produit, la
    # tech et les levées → l'agent lit large et filtre sous l'angle concurrentiel.
    rss_categories=["concurrence", "produit", "tech", "financement", "startup", "general"],
    web_query_template="{subject} concurrents actualité levée lancement produit",
)

REGLEMENTAIRE = VeilleSkill(
    key="reglementaire",
    name="Veille réglementaire",
    focus="Évolutions légales et normatives du secteur et leur impact.",
    system_prompt=_INTRO + (
        "Ton champ : le RÉGLEMENTAIRE. Traque les évolutions légales, normatives et de "
        "conformité pertinentes pour le secteur suivi (ex. RGPD, AI Act, normes métier, "
        "obligations sectorielles, jurisprudence). Pour chaque évolution : ce qui change, "
        "l'échéance d'entrée en vigueur, et l'obligation concrète ou le risque pour "
        "l'entreprise suivie."
    ),
    rss_categories=["reglementaire", "juridique", "general"],
    web_query_template="{subject} réglementation loi conformité évolution récente",
)

FINANCEMENT = VeilleSkill(
    key="financement",
    name="Veille financement / levées",
    focus="Levées, valorisations, investisseurs actifs, tendances de financement du segment.",
    system_prompt=_INTRO + (
        "Ton champ : le FINANCEMENT. Traque les levées de fonds, valorisations, tours de "
        "table, investisseurs actifs et tendances de financement sur le segment suivi. "
        "Pour chaque signal : montant, stade, investisseurs, et ce que ça révèle sur "
        "l'appétit du marché et les fenêtres de financement pour l'entreprise suivie."
    ),
    rss_categories=["financement", "vc", "startup", "general"],
    web_query_template="{subject} levée de fonds financement valorisation investisseurs",
)

PRODUIT_TECH = VeilleSkill(
    key="produit_tech",
    name="Veille produit & tech / marché",
    focus="Innovations, features marché, tendances techno, signaux d'usage et de demande.",
    system_prompt=_INTRO + (
        "Ton champ : le PRODUIT, la TECH et le MARCHÉ. Traque les innovations, nouvelles "
        "fonctionnalités qui deviennent des standards, tendances technologiques, signaux "
        "d'usage et d'évolution de la demande sur le marché suivi. Pour chaque signal : "
        "la nouveauté, son degré d'adoption, et l'implication produit/roadmap pour "
        "l'entreprise suivie."
    ),
    rss_categories=["produit", "tech", "marche", "general"],
    web_query_template="{subject} tendances produit innovation technologie marché",
)


MARCHE = VeilleSkill(
    key="marche",
    name="Veille marché",
    focus="Taille et dynamique du marché, tendances macro, signaux économiques et de demande.",
    system_prompt=_INTRO + (
        "Ton champ : le MARCHÉ et la MACRO. Traque l'évolution de la taille et de la "
        "dynamique du marché suivi, les tendances macro-économiques pertinentes (croissance, "
        "taux, inflation, conjoncture sectorielle), les signaux de demande et les basculements "
        "structurels. Pour chaque signal : le fait chiffré, sa tendance, et l'implication sur "
        "la fenêtre de marché et la stratégie de l'entreprise suivie."
    ),
    rss_categories=["marche", "financement", "general"],
    web_query_template="{subject} marché taille tendances macroéconomie demande",
)


_SKILLS = {s.key: s for s in (CONCURRENTIELLE, REGLEMENTAIRE, FINANCEMENT, PRODUIT_TECH, MARCHE)}
DEFAULT_SKILL = CONCURRENTIELLE.key


def get_skill(key: str) -> VeilleSkill:
    return _SKILLS.get(key) or _SKILLS[DEFAULT_SKILL]


def list_skills() -> list[VeilleSkill]:
    return list(_SKILLS.values())
