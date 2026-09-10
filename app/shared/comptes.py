"""Ce qu'est un compte interne, défini une seule fois.

Deux endroits en dépendent et doivent rester d'accord : les métriques, qui
excluent ces comptes des statistiques d'activation, et la facturation, qui les
dispense de l'écran carte. Une définition dupliquée dériverait — un compte
compté comme client d'un côté et comme interne de l'autre.
"""
from __future__ import annotations

DOMAINES_INTERNES = (
    "axial-ia.fr",
    "axial.com",
    "axial-qa.fr",
    "skema.edu",
    "francedigitale.org",
)


def est_interne(email: str | None) -> bool:
    if not email:
        return False
    return email.strip().lower().endswith(tuple(f"@{d}" for d in DOMAINES_INTERNES))
