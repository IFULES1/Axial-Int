"""Credit costs and plan catalog (product spec V1).

Costs are canonical per analysis type; legacy aliases map onto them so old
clients keep working. Plans mirror the 5-tier pricing grid.
"""
from __future__ import annotations

# Canonical credit cost per action.
CREDIT_COSTS: dict[str, int] = {
    "etude_marche": 40,
    "analyse_concurrentielle": 25,
    "veille_technologique": 25,
    "analyse_risques": 25,
    "synthese_executive": 25,
    "agent_message": 2,
    "run_agent_veille": 5,  # one cumulative veille run (RSS + web + LLM)
}

# Legacy / alternate keys → canonical.
_ALIASES: dict[str, str] = {
    "market_study": "etude_marche",
    "competition": "analyse_concurrentielle",
    "tech_watch": "veille_technologique",
    "risk_analysis": "analyse_risques",
}

DEFAULT_COST = 25


def cost_for(action: str) -> int:
    key = _ALIASES.get(action, action)
    return CREDIT_COSTS.get(key, DEFAULT_COST)


# Plan catalog (display + entitlements). Amounts in EUR.
PLANS: list[dict] = [
    {"key": "free_beta", "name": "Free Beta", "price_eur": 0, "period": "month",
     "monthly_credits": 20, "seats": 1,
     "features": ["Découverte", "export PDF"]},
    {"key": "solo_founder", "name": "Pro", "price_eur": 50, "period": "month",
     "monthly_credits": 120, "seats": 1,
     "features": ["Workspace", "2 agents", "templates (fundraising, ICP, GTM, mapping)"]},
    {"key": "startup_pro", "name": "Premium", "price_eur": 90, "period": "month",
     "monthly_credits": 250, "seats": 2,
     "features": ["Tout Pro", "jusqu'à 10 agents personnalisés", "mémoire avancée"]},
    {"key": "enterprise", "name": "Enterprise", "price_eur": None, "period": "custom",
     "monthly_credits": None, "seats": None,
     "features": ["Workspace multi-startups", "signaux portefeuille", "accès équipe"]},
]
