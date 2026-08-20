"""Investor mapping — scoring ported from the DB-investisseur research script.

The ranking logic is not new work: it reproduces the manual triage validated on
three real startup profiles (Papilio.bio, Startzup, Imagine Data) and encoded in
`rechercher_investisseurs.py`. Two rules carry it:

  * **Group by management company (SGP), not by fund vehicle** — one firm often
    runs 5-20 vehicles, which would otherwise flood any raw ranking.
  * **Weight matches by specificity** — a firm tagged with one sector is a more
    reliable match than a generalist tagged with twelve; the audit of 06/08
    showed the generalists carry most of the false positives.

Angel networks and crowdequity platforms are scored separately and never mixed
into the funds ranking: they have no structured sector/stage tagging, so their
scores are not comparable.
"""
from __future__ import annotations

import logging

from app.modules.investors import client

logger = logging.getLogger("axial.investors")


def referentials() -> dict:
    """Sector / stage / zone vocabularies, for the UI and for name resolution."""
    d = client.dataset()
    return {
        "secteurs": sorted((s["nom"] for s in d["secteur"]), key=str.lower),
        "stades": [s["nom"] for s in sorted(d["stade"], key=lambda x: x.get("ordre") or 0)],
        "zones": sorted((z["nom"] for z in d["zone_geographique"]), key=str.lower),
    }


def resolve_names(requested: list[str], referential: list[dict]) -> list[int]:
    """Resolve names to ids, exact match first.

    The exact-match priority is load-bearing: a substring search alone maps
    "Edtech" onto "Healthtech / Medtech" and "Seed" onto "Pre-seed".
    """
    ids: list[int] = []
    for name in requested:
        needle = (name or "").strip().lower()
        if not needle:
            continue
        exact = [r for r in referential if (r["nom"] or "").lower() == needle]
        if exact:
            ids.append(exact[0]["id"])
            continue
        partial = [r for r in referential if needle in (r["nom"] or "").lower()]
        if partial:
            ids.append(partial[0]["id"])
    return ids


def search(sector_ids: set[int], stage_ids: set[int],
           zone_id: int | None = None) -> tuple[list[dict], list[dict]]:
    """Return (funds grouped by SGP, angel networks/crowdequity), best first."""
    d = client.dataset()

    inv_secteurs: dict[int, set[int]] = {}
    inv_stades: dict[int, set[int]] = {}
    inv_zones: dict[int, set[int]] = {}
    for r in d["investisseur_secteur"]:
        inv_secteurs.setdefault(r["investisseur_id"], set()).add(r["secteur_id"])
    for r in d["investisseur_stade"]:
        inv_stades.setdefault(r["investisseur_id"], set()).add(r["stade_id"])
    for r in d["investisseur_zone"]:
        inv_zones.setdefault(r["investisseur_id"], set()).add(r["zone_id"])

    inv_to_sgp = {f["investisseur_id"]: f["societe_gestion_id"] for f in d["fonds"]}
    sgp_info = {r["id"]: r for r in d["societe_gestion"]}
    inv_info = {r["id"]: r for r in d["investisseur"]}
    pmi_nature = {r["investisseur_id"]: r["nature"]
                  for r in d["personne_morale_investisseur"]}
    sector_name = {s["id"]: s["nom"] for s in d["secteur"]}
    stage_name = {s["id"]: s["nom"] for s in d["stade"]}

    def _score(secs: set[int], stades: set[int]) -> float:
        n_sec = len(secs & sector_ids)
        n_std = len(stades & stage_ids)
        sector_match = 2.0 + 0.5 * (n_sec - 1) if n_sec else 0.0
        stage_match = 1.5 + 0.3 * (n_std - 1) if n_std else 0.0
        # Specificity in 1/n, not linear: going from 1 to 2 tags costs a lot
        # (genuinely specialised → already a bit generic), 6 to 7 barely matters.
        specificity = (3.0 / len(secs) if secs else 0) + (1.5 / len(stades) if stades else 0)
        return sector_match + stage_match + specificity

    by_sgp: dict[int, dict] = {}
    networks: list[dict] = []
    for inv_id, secs in inv_secteurs.items():
        if not (secs & sector_ids):
            continue
        stades = inv_stades.get(inv_id, set())
        if not (stades & stage_ids):
            continue
        info = inv_info.get(inv_id, {})

        if info.get("type") == "personne_morale":
            networks.append({
                "nom": info.get("nom", "?"),
                "nature": pmi_nature.get(inv_id, "?"),
                "secteurs": [sector_name.get(i, "?") for i in sorted(secs)],
                "stades": [stage_name.get(i, "?") for i in sorted(stades)],
                "score": round(_score(secs, stades), 2),
            })
            continue

        if info.get("type") != "fonds":
            continue
        sgp_id = inv_to_sgp.get(inv_id)
        if sgp_id is None:
            continue
        agg = by_sgp.setdefault(sgp_id, {"secteurs": set(), "stades": set(),
                                         "zones": set(), "n": 0})
        agg["secteurs"] |= secs
        agg["stades"] |= stades
        agg["zones"] |= inv_zones.get(inv_id, set())
        agg["n"] += 1

    funds: list[dict] = []
    for sgp_id, agg in by_sgp.items():
        sgp = sgp_info.get(sgp_id, {})
        zones = agg["zones"]
        if not zones:
            zone_label = "national / non renseigné"
        elif zone_id is not None and zone_id in zones:
            zone_label = "zone demandée couverte"
        else:
            zone_label = "autre zone"
        funds.append({
            "nom": sgp.get("nom", "?"),
            "site_web": sgp.get("site_web") or "",
            "n_vehicules": agg["n"],
            "secteurs": [sector_name.get(i, "?") for i in sorted(agg["secteurs"])],
            "stades": [stage_name.get(i, "?") for i in sorted(agg["stades"])],
            "score": round(_score(agg["secteurs"], agg["stades"]), 2),
            "zone": zone_label,
            "zone_match": zone_id is None or zone_id in zones or not zones,
        })

    funds.sort(key=lambda r: -r["score"])
    networks.sort(key=lambda r: -r["score"])
    return funds, networks


# --- Bridging a company profile to the referentials -------------------------

# The onboarding collects sector and stage from closed lists, so most profiles
# translate deterministically. The LLM below is only the fallback for profiles
# that were edited freely or prefilled from a website.
ONBOARDING_SECTORS: dict[str, list[str]] = {
    "SaaS B2B": ["SaaS / Logiciel B2B"],
    "SaaS B2C": ["Consumer / D2C", "SaaS / Logiciel B2B"],
    "Marketplace": ["Marketplace"],
    "Fintech": ["Fintech", "Paiement"],
    "Deeptech / IA": ["Deeptech", "Intelligence Artificielle", "IA appliquée / Vertical AI"],
    "Industrie / Hardware": ["Hardware / IoT", "Industrie 4.0 / Manufacturing", "Robotique"],
    "Services pro": ["SaaS / Logiciel B2B", "HR Tech", "Legal Tech"],
    "E-commerce": ["Consumer / D2C", "Marketplace"],
}

ONBOARDING_STAGES: dict[str, list[str]] = {
    "Idéation": ["Pre-seed"],
    "Pre-seed": ["Pre-seed"],
    "Seed": ["Seed"],
    "Série A": ["Pre-Série A", "Série A"],
    "Série B+": ["Série B", "Série C"],
    "Profitable": ["Série B", "Série C", "Growth / Late stage"],
}


def _from_onboarding(value: str | None, table: dict[str, list[str]]) -> list[str]:
    if not value:
        return []
    needle = value.strip().lower()
    for key, mapped in table.items():
        if key.lower() == needle:
            return mapped
    return []



def _llm_map_to_referential(label: str, values: list[str], vocabulary: list[str],
                            kind: str) -> list[str]:
    """Ask the LLM which vocabulary entries a free-text profile corresponds to.

    Onboarding collects free text ("robotique agricole"), while the investor
    database uses a closed vocabulary. Anything unmatched would silently return
    zero investors, so we translate instead of failing.
    """
    from app.shared import llm_client

    if not llm_client.generation_available():
        return []
    prompt = (
        f"Profil de l'entreprise — {label} : {', '.join(values)}\n\n"
        f"Vocabulaire {kind} disponible (choisis UNIQUEMENT dans cette liste) :\n"
        + "\n".join(f"- {v}" for v in vocabulary)
        + f"\n\nRéponds avec les 1 à 4 entrées du vocabulaire {kind} qui "
          "correspondent le mieux à ce profil, séparées par des virgules, sans "
          "aucun autre texte. Si rien ne correspond vraiment, réponds : AUCUN."
    )
    try:
        out = llm_client.generate(
            system="Tu fais correspondre un profil d'entreprise à un vocabulaire fermé. "
                   "Tu ne réponds QUE par des entrées exactes de la liste fournie.",
            prompt=prompt, tier="chat", max_tokens=200,
        ).text.strip()
    except Exception as e:
        logger.warning("Mapping LLM du profil échoué (%s) : %s", kind, e)
        return []
    if "AUCUN" in out.upper():
        return []
    known = {v.lower(): v for v in vocabulary}
    return [known[p.strip().lower()] for p in out.split(",") if p.strip().lower() in known]


def map_for_profile(profile: dict, *, limit: int = 15) -> dict:
    """Full mapping for a company profile: resolve, search, rank, summarise."""
    d = client.dataset()
    refs = referentials()

    raw_sectors = [s for s in [profile.get("sector")] if s]
    raw_stages = [s for s in [profile.get("funding_stage")] if s]
    raw_zone = profile.get("target_market") or profile.get("country")

    # 1. Onboarding vocabulary → investor vocabulary (deterministic).
    mapped_sectors = _from_onboarding(profile.get("sector"), ONBOARDING_SECTORS)
    mapped_stages = _from_onboarding(profile.get("funding_stage"), ONBOARDING_STAGES)
    sector_ids = resolve_names(mapped_sectors or raw_sectors, d["secteur"])
    stage_ids = resolve_names(mapped_stages or raw_stages, d["stade"])

    # 2. Anything else (free text, website prefill) → ask the model.
    if not sector_ids and raw_sectors:
        mapped_sectors = _llm_map_to_referential("secteur", raw_sectors,
                                                 refs["secteurs"], "secteur")
        sector_ids = resolve_names(mapped_sectors, d["secteur"])
    if not stage_ids and raw_stages:
        mapped_stages = _llm_map_to_referential("stade de financement", raw_stages,
                                                refs["stades"], "stade")
        stage_ids = resolve_names(mapped_stages, d["stade"])

    zone_ids = resolve_names([raw_zone] if raw_zone else [], d["zone_geographique"])
    zone_id = zone_ids[0] if zone_ids else None

    if not sector_ids or not stage_ids:
        return {
            "resolved": {"secteurs": mapped_sectors or raw_sectors,
                         "stades": mapped_stages or raw_stages, "zone": raw_zone},
            "funds": [], "networks": [], "total_funds": 0, "total_networks": 0,
            "note": ("Le profil n'a pas pu être rattaché au référentiel "
                     "(secteur ou stade manquant/inconnu)."),
        }

    funds, networks = search(set(sector_ids), set(stage_ids), zone_id)
    sector_name = {s["id"]: s["nom"] for s in d["secteur"]}
    stage_name = {s["id"]: s["nom"] for s in d["stade"]}
    return {
        "resolved": {
            "secteurs": [sector_name[i] for i in sector_ids if i in sector_name],
            "stades": [stage_name[i] for i in stage_ids if i in stage_name],
            "zone": raw_zone,
            "via_llm": bool(mapped_sectors or mapped_stages),
        },
        "funds": funds[:limit],
        "networks": networks[:limit],
        "total_funds": len(funds),
        "total_networks": len(networks),
        "note": None,
    }


def format_context(mapping: dict) -> str:
    """Numbered context block — the same [N] citation contract as web sources."""
    lines: list[str] = []
    n = 0
    for f in mapping.get("funds") or []:
        n += 1
        site = f" — {f['site_web']}" if f["site_web"] else ""
        lines.append(
            f"[{n}] (base Axial — société de gestion) {f['nom']}{site}\n"
            f"Score de pertinence : {f['score']} · {f['n_vehicules']} véhicule(s) "
            f"référencé(s) · Couverture : {f['zone']}\n"
            f"Secteurs tagués : {', '.join(f['secteurs'])}\n"
            f"Stades tagués : {', '.join(f['stades'])}"
        )
    for r in mapping.get("networks") or []:
        n += 1
        lines.append(
            f"[{n}] (base Axial — {r['nature']}) {r['nom']}\n"
            f"Score de pertinence : {r['score']}\n"
            f"Secteurs : {', '.join(r['secteurs'])} · Stades : {', '.join(r['stades'])}"
        )
    return "\n\n".join(lines)


def citations(mapping: dict) -> list[dict]:
    """Citation entries matching the [N] numbering of format_context()."""
    out: list[dict] = []
    for f in mapping.get("funds") or []:
        out.append({
            "title": f["nom"],
            "url": f["site_web"] or None,
            "source": "investisseurs",
            "reference": f"Base investisseurs Axial · score {f['score']}",
            "excerpt": (f"Secteurs : {', '.join(f['secteurs'])}. "
                        f"Stades : {', '.join(f['stades'])}. "
                        f"{f['n_vehicules']} véhicule(s). {f['zone']}."),
        })
    for r in mapping.get("networks") or []:
        out.append({
            "title": r["nom"],
            "url": None,
            "source": "investisseurs",
            "reference": f"Base investisseurs Axial · {r['nature']}",
            "excerpt": (f"Secteurs : {', '.join(r['secteurs'])}. "
                        f"Stades : {', '.join(r['stades'])}."),
        })
    return out
