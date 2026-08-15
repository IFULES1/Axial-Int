"""Memory service: profile CRUD, onboarding gate, context injection."""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.modules.memory.models import CompanyProfile

# Fields rendered into the injected context, with human labels.
_CONTEXT_FIELDS: list[tuple[str, str]] = [
    ("company_name", "Entreprise"),
    ("sector", "Secteur"),
    ("positioning", "Positionnement"),
    ("founding_year", "Année de création"),
    ("funding_stage", "Stade de financement"),
    ("team_size", "Taille d'équipe"),
    ("country", "Pays"),
    ("target_market", "Marché cible"),
    ("client_segment", "Segment client"),
    ("known_competitors", "Concurrents connus"),
    ("main_challenge", "Défi principal"),
]

_EDITABLE = {f for f, _ in _CONTEXT_FIELDS}


def get_profile(db: Session, user_id: str) -> CompanyProfile | None:
    return db.get(CompanyProfile, uuid.UUID(user_id))


def upsert_profile(db: Session, user_id: str, data: dict) -> CompanyProfile:
    profile = db.get(CompanyProfile, uuid.UUID(user_id))
    if profile is None:
        profile = CompanyProfile(user_id=uuid.UUID(user_id))
        db.add(profile)
    for field, value in data.items():
        if field in _EDITABLE:
            setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile


def delete_profile(db: Session, user_id: str) -> None:
    profile = db.get(CompanyProfile, uuid.UUID(user_id))
    if profile:
        db.delete(profile)
        db.commit()


def onboarding_complete(db: Session, user_id: str) -> bool:
    """Onboarding is done once the user has given some company context.

    The product's onboarding collects sector/stage/challenge/market (not
    necessarily a company name), so any populated context field counts.
    """
    profile = get_profile(db, user_id)
    if not profile:
        return False
    return any(
        (getattr(profile, f, None) or "").strip()
        for f in ("company_name", "sector", "funding_stage", "main_challenge", "target_market")
    )


def build_context(db: Session, user_id: str) -> str:
    """Compact context block injected into every analysis/agent prompt.

    Returns "" when there is no profile, so callers can inject unconditionally.
    """
    profile = get_profile(db, user_id)
    if profile is None:
        return ""
    lines: list[str] = []
    for field, label in _CONTEXT_FIELDS:
        value = getattr(profile, field, None)
        if value not in (None, ""):
            lines.append(f"- {label} : {value}")
    if not lines:
        return ""
    return "## Contexte entreprise (mémoire)\n" + "\n".join(lines)
