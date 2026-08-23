"""Memory service: profile CRUD, onboarding gate, context injection."""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.modules.memory.models import CompanyProfile

# Fields rendered into the injected context, with human labels.
_CONTEXT_FIELDS: list[tuple[str, str]] = [
    ("company_name", "Entreprise"),
    ("website", "Site web"),
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

# Champs modifiables : le contexte entreprise, plus les réglages personnels.
# Sans ces deux ajouts, la langue et les préférences étaient acceptées par
# l'API puis silencieusement jetées — un réglage qui ne s'enregistre jamais.
_EDITABLE = {f for f, _ in _CONTEXT_FIELDS} | {"language", "preferences"}


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


# --- Onboarding prefill: read the company website, extract profile fields ---

_PREFILL_SYSTEM = (
    "Tu extrais des informations factuelles depuis le site web d'une startup. "
    "Réponds UNIQUEMENT avec un objet JSON, sans texte autour."
)

_PREFILL_PROMPT = """Voici le texte de la page d'accueil du site {url} :

---
{page_text}
---

Extrais en JSON (valeurs en français, null si introuvable) :
{{"company_name": "nom officiel de l'entreprise",
  "positioning": "ce que fait l'entreprise, pour qui, en 1 phrase précise (pas un slogan)",
  "sector": "secteur d'activité court, ex: SaaS RH, Fintech, Deeptech quantique"}}"""


def _fetch_website_text(url: str) -> str:
    """Fetch the homepage and return readable text (tags stripped, truncated)."""
    import re

    import httpx

    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    resp = httpx.get(url, follow_redirects=True, timeout=10.0,
                     headers={"User-Agent": "Mozilla/5.0 (compatible; AxialBot/1.0)"})
    resp.raise_for_status()
    html = resp.text
    html = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:6000]


def prefill_from_website(url: str) -> dict:
    """Best-effort {company_name, positioning, sector} extracted from a website.

    Raises AppError with a user-readable message when the site is unreachable
    or the extraction fails — the frontend falls back to manual input.
    """
    import json as _json

    from app.errors import AppError
    from app.shared import llm_client

    try:
        page_text = _fetch_website_text(url)
    except Exception as e:
        raise AppError("Site injoignable — remplis les champs à la main.", 422,
                       code="prefill_fetch_failed") from e
    if len(page_text) < 80:
        raise AppError("Page trop pauvre pour être analysée — remplis les champs à la main.",
                       422, code="prefill_empty_page")

    try:
        result = llm_client.generate(
            system=_PREFILL_SYSTEM,
            prompt=_PREFILL_PROMPT.format(url=url, page_text=page_text),
            tier="chat", max_tokens=400,
        )
        raw = result.text.strip()
        # Tolerate ```json fences or stray prose around the object.
        start, end = raw.find("{"), raw.rfind("}")
        data = _json.loads(raw[start:end + 1])
    except AppError:
        raise
    except Exception as e:
        raise AppError("Extraction impossible — remplis les champs à la main.", 422,
                       code="prefill_extract_failed") from e

    return {
        "company_name": (data.get("company_name") or None),
        "positioning": (data.get("positioning") or None),
        "sector": (data.get("sector") or None),
        "website": url if url.startswith("http") else "https://" + url,
    }


# --- Préférences de notification -------------------------------------------

def get_notification_prefs(db: Session, user_id: str) -> dict:
    from app.modules.memory.models import NotificationPrefs

    row = db.get(NotificationPrefs, uuid.UUID(user_id))
    if row is None:
        return {"findings": True, "weekly": True, "marketing": False}
    return {"findings": row.findings, "weekly": row.weekly, "marketing": row.marketing}


def set_notification_prefs(db: Session, user_id: str, prefs: dict) -> dict:
    from app.modules.memory.models import NotificationPrefs

    uid = uuid.UUID(user_id)
    row = db.get(NotificationPrefs, uid)
    if row is None:
        row = NotificationPrefs(user_id=uid)
        db.add(row)
    for k in ("findings", "weekly", "marketing"):
        if k in prefs and prefs[k] is not None:
            setattr(row, k, bool(prefs[k]))
    db.commit()
    return get_notification_prefs(db, user_id)
