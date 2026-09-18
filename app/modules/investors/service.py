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
import re

from app.modules.investors import client

logger = logging.getLogger("axial.investors")


# Spec §4 : mots FR/EN qui signalent qu'une question de conversation porte sur
# une levée de fonds, des investisseurs, ou du financement — insensible à la
# casse. Fonction pure, testée, sans appel modèle : la base investisseurs ne
# doit pas dépendre d'un jugement LLM pour savoir si elle doit répondre.
#
# Tour de correction 1 (review) : la première version n'ancrait pas ses
# alternances (`lev(er|ée)`, `fonds`, `ticket`, `valorisation` nus) et
# déclenchait sur du vocabulaire courant sans rapport — « marge élevée »,
# « relever », « changements profonds », « prélever », « enlever », « fonds
# de commerce », « ticket moyen », « valorisation de la marque ». Chaque
# alternance est maintenant bornée par `\b` et les mots trop génériques
# (`fonds`, `ticket`, `valorisation`) n'existent qu'en forme composée
# (« fonds d'investissement », « ticket d'investissement », « valorisation
# pré-money »). `financement` de même : seulement en combinaison
# (« financement de la startup », « financement par des fonds »), jamais nu.
_LEVEE_PATTERN = re.compile(
    r"\blever des fonds\b"
    r"|\blevée(s)? de fonds\b"
    r"|\blevée\b"
    r"|\blève\b"
    r"|\bfundrais\w*"
    r"|\binvestisseur\w*"
    r"|\bbusiness angel\w*"
    r"|\bVC\b"
    r"|\bventure\b"
    r"|\bseed\b"
    r"|\bsérie [ABC]\b"
    r"|\bseries [ABC]\b"
    r"|\btour de table\b"
    r"|\bterm sheet\b"
    r"|\bBSA\b"
    r"|\bvalorisation pré-?money\b"
    r"|\bpost-?money\b"
    r"|\bticket d.investissement\b"
    r"|\bfonds d.investissement\b"
    r"|\bfonds VC\b"
    r"|\bcapital-?risque\b"
    r"|\bfinancement (?:de (?:la |notre |cette )?)?(?:startup|entreprise|soci[ée]t[ée])\b"
    r"|\bfinancement par (?:des |les )?fonds\b",
    re.IGNORECASE,
)


def question_de_levee(texte: str) -> bool:
    """Vrai si la question parle de levée de fonds, d'investisseurs ou de
    financement (spec §4 — regex FR/EN, insensible à la casse)."""
    return bool(_LEVEE_PATTERN.search(texte or ""))


# --- Ciblage v2 (spec 2026-09-18) : nombre demandé, montant, stade, exclusions ---
#
# Fonctions pures, sans appel modèle : le ciblage ne doit pas dépendre d'un
# jugement LLM pour lire un nombre ou un montant écrit en clair.

_MOTS_NOMBRE: dict[str, int] = {
    "dizaine": 10, "douzaine": 12, "vingtaine": 20, "trentaine": 30,
    "quarantaine": 40, "cinquantaine": 50,
}

_NOMBRE_RANGE_RE = re.compile(
    r"\b(\d+)\s*(?:à|-|–|to)\s*(\d+)\s*investisseurs?\b"
    r"|\b(\d+)\s*(?:à|-|–|to)\s*(\d+)\s*investors?\b",
    re.IGNORECASE,
)
_NOMBRE_COUNT_RE = re.compile(
    r"\b(\d+)\s*investisseurs?\b|\b(\d+)\s*investors?\b", re.IGNORECASE,
)
_NOMBRE_MOT_RE = re.compile(
    r"\bune?\s+(dizaine|douzaine|vingtaine|trentaine|quarantaine|cinquantaine)\b",
    re.IGNORECASE,
)
_NOMBRE_TOP_RE = re.compile(r"\btop\s*(\d+)\b", re.IGNORECASE)


def nombre_demande(question: str | None) -> int | None:
    """Lit « N investisseurs », « 5 à 10 investisseurs » (→10), « une
    dizaine » (10), « une vingtaine » (20), « top 15 », FR et EN (spec §1).
    `None` si rien n'est lu."""
    if not question:
        return None
    m = _NOMBRE_RANGE_RE.search(question)
    if m:
        groupes = [g for g in m.groups() if g]
        return int(groupes[-1])
    m = _NOMBRE_COUNT_RE.search(question)
    if m:
        return int(m.group(1) or m.group(2))
    m = _NOMBRE_MOT_RE.search(question)
    if m:
        return _MOTS_NOMBRE[m.group(1).lower()]
    m = _NOMBRE_TOP_RE.search(question)
    if m:
        return int(m.group(1))
    return None


# Plausibilité par stade (spec §2) : au-delà, un montant lu littéralement est
# considéré ambigu et la lecture la plus faible (sans le facteur d'échelle) est
# retenue à sa place.
_PLAFOND_PAR_STADE: dict[str, int] = {
    "pre_seed": 2_000_000,
    "seed": 8_000_000,
    "serie_a_plus": 30_000_000,
}


def _categorie_stade(stade: str | None) -> str:
    """Regroupe un libellé de stade libre dans l'une des trois catégories de
    composition du §4 (« pre_seed » couvre aussi l'idéation, « serie_a_plus »
    couvre série A et B+)."""
    s = (stade or "").strip().lower()
    if not s:
        return "seed"
    if any(m in s for m in ("pre-seed", "pré-seed", "preseed", "idéation",
                            "ideation", "amorçage", "amorcage")):
        return "pre_seed"
    if "seed" in s:
        return "seed"
    return "serie_a_plus"


_MONTANT_RE = re.compile(
    r"(?P<nombre>\d{1,3}(?:[  ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
    r"\s*(?P<suffixe>millions?|mille|k|m)?"
    r"\s*(?P<euro>€|euros?)?",
    re.IGNORECASE,
)

_MULTIPLICATEURS: dict[str, int] = {
    "k": 1_000, "mille": 1_000,
    "m": 1_000_000, "million": 1_000_000, "millions": 1_000_000,
}


def _parse_nombre_fr(brut: str) -> float:
    """« 300 000 » ou « 1,5 » → nombre flottant (virgule ou point décimal,
    espace insécable ou normal comme séparateur de milliers)."""
    s = brut.replace(" ", " ").strip()
    m = re.match(r"^([\d ]+)(?:[.,](\d+))?$", s)
    if not m:
        return float(s.replace(" ", "").replace(",", "."))
    entier = m.group(1).replace(" ", "")
    decimal = m.group(2)
    return float(f"{entier}.{decimal}") if decimal else float(entier)


def _format_eur(montant: int) -> str:
    """Ré-écrit un montant en euros dans la forme la plus courte et lisible
    (« 300 M€ », « 300 k€ », « 300 € ») — utilisé par les consignes dynamiques."""
    if montant % 1_000_000 == 0:
        return f"{montant // 1_000_000} M€"
    if montant % 1_000 == 0:
        return f"{montant // 1_000} k€"
    return f"{montant} €"


def montant_de_levee(question: str | None, stade: str | None = None) -> dict | None:
    """Lit un montant de levée écrit en clair (spec §2) : « 300 K€ », « 300k »,
    « 1,5 M€ », « 2 millions », « 500 000 € ». `None` si rien n'est lu.

    Un montant à la fois séparé en milliers ET affublé d'un suffixe k/mille
    (« 300 000k€ ») est ambigu : la lecture littérale (300 M€) et la lecture
    plausible (300 k€, le suffixe pris comme du bruit) sont toutes deux
    renvoyées dans `lectures`, la plausible en second.
    """
    if not question:
        return None
    for m in _MONTANT_RE.finditer(question):
        suffixe = (m.group("suffixe") or "").lower()
        euro = m.group("euro")
        if not suffixe and not euro:
            continue  # un nombre nu n'est pas un montant (ex. « 15 investisseurs »)
        texte = m.group(0).strip()
        valeur = _parse_nombre_fr(m.group("nombre"))
        multiplicateur = _MULTIPLICATEURS.get(suffixe, 1)
        litteral = round(valeur * multiplicateur)

        ambigu = bool(suffixe) and multiplicateur > 1 and valeur >= 1000
        if not ambigu:
            return {"montant_eur": litteral, "texte": texte,
                    "lectures": [litteral], "ambigu": False}

        plausible = round(valeur)
        plafond = _PLAFOND_PAR_STADE.get(_categorie_stade(stade))
        # Si le stade est connu et que la lecture littérale reste plausible
        # (rare, mais un plafond n'exclut jamais formellement), on la garde.
        retenu = plausible
        if plafond is not None and litteral <= plafond:
            retenu = litteral
        return {"montant_eur": retenu, "texte": texte,
                "lectures": [litteral, plausible], "ambigu": True}
    return None


_DEJA_CONTACTE_RE = re.compile(
    r"(?:déjà\s+contact[ée]s?|déjà\s+identifi[ée]s?|\bhors\b)\s*:?\s*"
    r"([^.;\n]+)",
    re.IGNORECASE,
)


def deja_contactes(question: str | None) -> list[str]:
    """Noms cités après « déjà contacté », « déjà identifié » ou « hors »
    (spec §4) — à retirer de la liste remise au modèle."""
    if not question:
        return []
    noms: list[str] = []
    for m in _DEJA_CONTACTE_RE.finditer(question):
        segment = m.group(1)
        for part in re.split(r",| et ", segment, flags=re.IGNORECASE):
            nom = part.strip(" \t.;:")
            nom = re.sub(r"^(par|avec)\s+", "", nom, flags=re.IGNORECASE).strip()
            if nom:
                noms.append(nom)
    return noms


def _exclu(nom: str, noms_exclus: list[str]) -> bool:
    """Comparaison insensible à la casse, tolérante à la sous-chaîne (« Alpha »
    exclut « Fonds Alpha »)."""
    n = (nom or "").strip().lower()
    if not n:
        return False
    for excl in noms_exclus:
        e = (excl or "").strip().lower()
        if e and (e in n or n in e):
            return True
    return False


_STADE_QUESTION_RE = re.compile(
    r"\b(pre-?seed|pré-?seed|id[ée]ation|amor[çc]age|seed|s[ée]rie\s*[ab]\+?|"
    r"series\s*[ab]\+?)\b",
    re.IGNORECASE,
)


def stade_depuis(question: str | None, profile: dict | None = None) -> str | None:
    """Le stade de la QUESTION prime sur celui du profil (décision) — un
    fondateur qui précise « pour un tour seed » outrepasse son profil
    enregistré en série A."""
    if question:
        m = _STADE_QUESTION_RE.search(question)
        if m:
            return m.group(1)
    if profile:
        return profile.get("funding_stage") or None
    return None


def composer_par_stade(funds: list[dict], networks: list[dict], stade: str | None,
                       limit: int) -> tuple[list[dict], list[dict]]:
    """Compose la liste remise au modèle selon la table du §4, sans dépasser
    `limit` acteurs au total (fonds + réseaux confondus)."""
    limit = max(int(limit or 0), 0)
    cat = _categorie_stade(stade)

    if cat == "pre_seed":
        # Réseaux de BA et plateformes d'amorçage d'abord, puis fonds.
        kept_networks = networks[:limit]
        kept_funds = funds[:max(limit - len(kept_networks), 0)]
        return kept_funds, kept_networks

    if cat == "seed":
        # Réseaux + fonds à parts égales (l'éventuel siège impair va aux
        # réseaux) ; le pool le plus court cède sa place à l'autre.
        moitie = (limit + 1) // 2
        kept_networks = networks[:min(moitie, len(networks))]
        kept_funds = funds[:max(limit - len(kept_networks), 0)]
        return kept_funds, kept_networks

    # Série A / B+ : fonds d'abord, réseaux seulement s'il reste de la place.
    kept_funds = funds[:limit]
    kept_networks = networks[:max(limit - len(kept_funds), 0)]
    return kept_funds, kept_networks


_CONSIGNE_COMPOSITION: dict[str, str] = {
    "pre_seed": (
        "Stade pré-seed / idéation : priorise les réseaux de business angels et "
        "les plateformes d'amorçage, puis les fonds tagués pre-seed / amorçage. "
        "Mentionne le non dilutif (Bpifrance Bourse French Tech, prêts "
        "d'honneur, concours, aides régionales) comme premier levier."
    ),
    "seed": (
        "Stade seed : compose la liste à parts égales entre réseaux de "
        "business angels et fonds d'amorçage."
    ),
    "serie_a_plus": (
        "Stade série A ou plus : présente les fonds d'abord, les réseaux de "
        "business angels seulement s'il reste de la place."
    ),
}


def consigne_pour(mapping: dict) -> str:
    """Consigne dynamique (spec §1, §2, §4) construite par le moteur — le TEXTE
    des directives figées n'est jamais modifié, cette chaîne s'y ajoute."""
    parties: list[str] = []

    demande = mapping.get("demande")
    if demande and demande.get("n"):
        n = demande["n"]
        disponibles = demande.get("disponibles") or 0
        if disponibles >= n:
            parties.append(
                f"Le fondateur demande {n} investisseurs : présente exactement "
                f"{n} acteurs, par ordre de priorité, tous issus des sources "
                "numérotées."
            )
        else:
            parties.append(
                f"Le fondateur demande {n} investisseurs ; la base Axial n'en "
                f"référence que {disponibles} qui correspondent à son secteur "
                "et à son stade. Présente-les tous et dis, dès l'introduction, "
                "que cette liste réunit l'exhaustivité et la pertinence de la "
                "base pour sa situation, sans compléter avec des noms venus du "
                "web."
            )

    stade = mapping.get("stade_retenu")
    if stade:
        parties.append(_CONSIGNE_COMPOSITION[_categorie_stade(stade)])

    exclus = mapping.get("exclus")
    if exclus:
        parties.append(
            "Déjà contactés, à exclure de la liste : " + ", ".join(exclus) + "."
        )

    levee = mapping.get("levee")
    if levee:
        montant = levee.get("montant_eur")
        texte = levee.get("texte")
        suffixe_stade = f" · stade {stade}" if stade else ""
        parties.append(
            f"Paramètres de la levée retenus : montant {montant} € "
            f"(« {texte} »){suffixe_stade}. Restitue ces paramètres dans la "
            "première phrase de la synthèse."
        )
        lectures = levee.get("lectures") or []
        if levee.get("ambigu") and len(lectures) >= 2:
            litteral, plausible = lectures[0], lectures[1]
            parties.append(
                f"Le montant écrit (« {texte} ») se lit {_format_eur(litteral)} ; "
                f"pour un {stade or 'ce stade'}, {_format_eur(plausible)} est "
                f"plus vraisemblable : le rapport retient {_format_eur(plausible)} "
                "et le signale."
            )

    return "\n".join(parties)


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
        # Budget large : les modèles récents décomptent leur réflexion du même
        # plafond, et une réponse tronquée en plein mot ne correspond à aucune
        # entrée du vocabulaire (« Agritech / Food » au lieu de « … / Foodtech »).
        out = llm_client.generate(
            system="Tu fais correspondre un profil d'entreprise à un vocabulaire fermé. "
                   "Tu ne réponds QUE par des entrées exactes de la liste fournie.",
            prompt=prompt, tier="chat", max_tokens=2000,
        ).text.strip()
    except Exception as e:
        logger.warning("Mapping LLM du profil échoué (%s) : %s", kind, e)
        return []
    if "AUCUN" in out.upper():
        return []
    return _match_vocabulary(out, vocabulary)


def _match_vocabulary(answer: str, vocabulary: list[str]) -> list[str]:
    """Map a free-form model answer onto exact vocabulary entries.

    Tolerant on purpose: models answer with bullets, line breaks or a truncated
    last item, and a strict equality check would silently return nothing.
    """
    import re

    known = {v.lower(): v for v in vocabulary}
    picked: list[str] = []
    for raw in re.split(r"[,\n]", answer):
        cand = raw.strip().strip("-•*\"' \t").lower()
        if not cand:
            continue
        if cand in known:
            match = known[cand]
        else:
            # Truncated or slightly-off item: accept an unambiguous prefix.
            starts = [v for k, v in known.items() if k.startswith(cand)]
            if len(starts) != 1:
                continue
            match = starts[0]
        if match not in picked:
            picked.append(match)
    return picked


def _alive_sectors() -> set[int]:
    """Sector ids that actually have at least one tagged investor.

    12 of the 35 sectors are tagged on nothing — almost all of them sub-sectors
    whose parent carries the tagging instead. Broadening has to know this, or it
    keeps proposing empty branches.
    """
    d = client.dataset()
    return {r["secteur_id"] for r in d["investisseur_secteur"]}


def _broaden(sector_ids: list[int]) -> tuple[list[int], list[str], str]:
    """Climb the sector taxonomy until the branch actually holds investors.

    Returns (ids, names, how) — `how` is empty when nothing was broadened.
    """
    d = client.dataset()
    by_id = {s["id"]: s for s in d["secteur"]}
    alive = _alive_sectors()

    kept = [i for i in sector_ids if i in alive]
    if kept:
        return kept, [by_id[i]["nom"] for i in kept if i in by_id], ""

    # 1. Parent of each empty sector (a sub-sector's tagging lives on its parent).
    parents: list[int] = []
    for i in sector_ids:
        parent = (by_id.get(i) or {}).get("secteur_parent_id")
        if parent and parent in alive and parent not in parents:
            parents.append(parent)
    if parents:
        return parents, [by_id[p]["nom"] for p in parents], "parent"

    # 2. Siblings under the same parent.
    siblings: list[int] = []
    for i in sector_ids:
        parent = (by_id.get(i) or {}).get("secteur_parent_id")
        if not parent:
            continue
        for s in d["secteur"]:
            if s.get("secteur_parent_id") == parent and s["id"] in alive \
                    and s["id"] not in siblings:
                siblings.append(s["id"])
    if siblings:
        return siblings, [by_id[s]["nom"] for s in siblings], "voisins"

    # 3. Closest populated sectors, chosen by the model among live ones only.
    names = [by_id[i]["nom"] for i in sector_ids if i in by_id]
    if names:
        vocabulary = sorted(by_id[i]["nom"] for i in alive)
        suggested = _llm_map_to_referential(
            "secteur (aucun investisseur n'est tagué sur ce secteur, trouve les "
            "secteurs les plus proches)", names, vocabulary, "secteur")
        ids = resolve_names(suggested, d["secteur"])
        if ids:
            return ids, suggested, "proches"

    return [], [], "aucun"


def map_for_profile(profile: dict, *, limit: int = 15,
                    question: str | None = None) -> dict:
    """Full mapping for a company profile: resolve, search, rank, summarise.

    `question` (spec ciblage v2, 18/09) — quand fournie, lit le nombre
    d'investisseurs demandé, le stade, le montant de levée et les exclusions
    directement dans la question, et compose `funds`/`networks` selon le
    stade (§4) sous un plafond combiné (§1). Facultatif : absente, le
    comportement est inchangé (premier rapport offert, sans question chiffrée)."""
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

    # 3. Le secteur demandé peut n'avoir AUCUN investisseur tagué : on élargit
    # le long de la taxonomie plutôt que de renvoyer une page blanche.
    broadening = ""
    broadened_names: list[str] = []
    if sector_ids:
        sector_ids, broadened_names, broadening = _broaden(sector_ids)

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

    asked = mapped_sectors or raw_sectors
    note = None
    if broadening and broadening != "aucun":
        reason = {
            "parent": "aucun investisseur n'est référencé sur ce secteur précis ; "
                      "la recherche a été élargie au secteur parent",
            "voisins": "aucun investisseur n'est référencé sur ce secteur précis ; "
                       "la recherche a été élargie aux secteurs voisins",
            "proches": "aucun investisseur n'est référencé sur ce secteur précis ; "
                       "la recherche a été élargie aux secteurs les plus proches",
        }[broadening]
        note = (f"Élargissement : {reason} ({', '.join(asked)} → "
                f"{', '.join(broadened_names)}).")

    resolved = {
        "secteurs": [sector_name[i] for i in sector_ids if i in sector_name],
        "secteurs_demandes": asked,
        "stades": [stage_name[i] for i in stage_ids if i in stage_name],
        "zone": raw_zone,
        "via_llm": bool(mapped_sectors or mapped_stages),
        "elargissement": broadening or None,
    }

    resultat = {
        "resolved": resolved,
        "note": note,
    }

    if question:
        stade_retenu = stade_depuis(question, profile) or (resolved["stades"][0]
                                                            if resolved["stades"] else None)
        exclusions = deja_contactes(question)
        if exclusions:
            funds = [f for f in funds if not _exclu(f["nom"], exclusions)]
            networks = [r for r in networks if not _exclu(r["nom"], exclusions)]
        n_demande = nombre_demande(question)
        limite_effective = n_demande if n_demande else limit
        kept_funds, kept_networks = composer_par_stade(
            funds, networks, stade_retenu, limite_effective)
        resultat["demande"] = {"n": n_demande,
                               "disponibles": len(funds) + len(networks)}
        resultat["exclus"] = exclusions
        resultat["levee"] = montant_de_levee(question, stade_retenu)
        resultat["stade_retenu"] = stade_retenu
    else:
        kept_funds, kept_networks = funds[:limit], networks[:limit]

    resultat["funds"] = kept_funds
    resultat["networks"] = kept_networks
    resultat["total_funds"] = len(funds)
    resultat["total_networks"] = len(networks)
    return resultat


def format_context(mapping: dict) -> str:
    """Numbered context block — the same [N] citation contract as web sources."""
    lines: list[str] = []
    levee = mapping.get("levee")
    stade = mapping.get("stade_retenu")
    if levee or stade:
        morceaux = []
        if levee and levee.get("montant_eur") is not None:
            morceaux.append(f"montant {levee['montant_eur']} €")
        if stade:
            morceaux.append(f"stade {stade}")
        if morceaux:
            lines.append("Paramètres de la levée retenus : " + " · ".join(morceaux))
        lectures = (levee or {}).get("lectures") or []
        if levee and levee.get("ambigu") and len(lectures) >= 2:
            litteral, plausible = lectures[0], lectures[1]
            lines.append(
                f"Le montant écrit (« {levee.get('texte')} ») se lit "
                f"{_format_eur(litteral)} ; pour un {stade or 'ce stade'}, "
                f"{_format_eur(plausible)} est plus vraisemblable : le rapport "
                f"retient {_format_eur(plausible)} et le signale."
            )
    if mapping.get("note"):
        # En tête, pour que le rapport annonce l'élargissement au lieu de le taire.
        lines.append(f"(avertissement méthodologique) {mapping['note']}")
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
