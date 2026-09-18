"""Ciblage investisseurs v2 — Task T1 : nombre demandé, montant de levée,
composition par stade. Voir
`docs/superpowers/specs/2026-09-18-ciblage-investisseurs-v2.md` §1, §2, §4, §5.
"""
from __future__ import annotations

import pytest

from app.modules.analysis import prompts as analysis_prompts
from app.modules.analysis import service as analysis_service
from app.modules.investors import service as investors_service


# --- nombre_demande : formats FR/EN -----------------------------------------

@pytest.mark.parametrize("question,attendu", [
    ("Trouve-moi 8 investisseurs pour ma seed", 8),
    ("Find me 12 investors for my round", 12),
    ("Je cherche 5 à 10 investisseurs", 10),
    ("Looking for 5 to 10 investors", 10),
    ("Propose-moi une dizaine d'investisseurs", 10),
    ("Une vingtaine d'investisseurs suffirait", 20),
    ("Donne-moi le top 15", 15),
    ("Top 6 fonds pour ma série A", 6),  # "top N" lu quel que soit le nom qui suit
    ("Quels investisseurs pour mon secteur ?", None),
    ("", None),
])
def test_nombre_demande_formats(question, attendu):
    assert investors_service.nombre_demande(question) == attendu


def test_nombre_demande_top_seul_sans_mot_investisseurs():
    assert investors_service.nombre_demande("Donne-moi le top 6") == 6


def test_nombre_demande_aucun_si_texte_vide_ou_none():
    assert investors_service.nombre_demande(None) is None
    assert investors_service.nombre_demande("") is None


# --- montant_de_levee : formats, ambiguïté, plausibilité --------------------

def test_montant_de_levee_300k_euros():
    r = investors_service.montant_de_levee("Je lève 300 K€ en pre-seed")
    assert r == {"montant_eur": 300_000, "texte": "300 K€",
                "lectures": [300_000], "ambigu": False}


def test_montant_de_levee_300k_sans_signe_euro():
    r = investors_service.montant_de_levee("On vise 300k pour démarrer")
    assert r["montant_eur"] == 300_000
    assert r["ambigu"] is False


def test_montant_de_levee_virgule_decimale_millions():
    r = investors_service.montant_de_levee("Nous levons 1,5 M€ en série A")
    assert r["montant_eur"] == 1_500_000
    assert r["texte"] == "1,5 M€"
    assert r["ambigu"] is False


def test_montant_de_levee_mot_millions():
    r = investors_service.montant_de_levee("Objectif : 2 millions en série A")
    assert r["montant_eur"] == 2_000_000
    assert r["ambigu"] is False


def test_montant_de_levee_montant_simple_avec_espaces_milliers():
    r = investors_service.montant_de_levee("On cherche 500 000 € pour la seed")
    assert r == {"montant_eur": 500_000, "texte": "500 000 €",
                "lectures": [500_000], "ambigu": False}


def test_montant_de_levee_ambigu_300000k_pre_seed():
    """Spec §2 : « 300 000k€ » se lit littéralement 300 M€, mais 300 k€ est
    plausible pour un pre-seed (plafond 2 M€) — c'est la lecture retenue."""
    r = investors_service.montant_de_levee("On lève 300 000k€ en pre-seed", "pre-seed")
    assert r["texte"] == "300 000k€"
    assert r["lectures"] == [300_000_000, 300_000]
    assert r["ambigu"] is True
    assert r["montant_eur"] == 300_000


def test_montant_de_levee_ambigu_sans_stade_retient_la_lecture_plausible():
    r = investors_service.montant_de_levee("On lève 300 000k€")
    assert r["ambigu"] is True
    assert r["montant_eur"] == 300_000


def test_montant_de_levee_plausibilite_seed_8m():
    """8 M€ tient sous le plafond seed (≤ 8 M€) : pas d'ambiguïté déclenchée
    par la plausibilité de stade, seulement par le motif de double échelle."""
    r = investors_service.montant_de_levee("Levée de 7 M€ en seed", "seed")
    assert r["montant_eur"] == 7_000_000
    assert r["ambigu"] is False


def test_montant_de_levee_aucun_montant_retourne_none():
    assert investors_service.montant_de_levee("Quels investisseurs pour mon secteur ?") is None
    assert investors_service.montant_de_levee(None) is None


def test_montant_de_levee_nombre_nu_sans_devise_ignore():
    """« 15 investisseurs » ne doit jamais être lu comme un montant."""
    assert investors_service.montant_de_levee("Trouve-moi 15 investisseurs") is None


# --- deja_contactes ----------------------------------------------------------

def test_deja_contactes_apres_deja_contacte():
    noms = investors_service.deja_contactes(
        "Trouve des fonds seed, déjà contacté Alpha Ventures et Beta Capital.")
    assert noms == ["Alpha Ventures", "Beta Capital"]


def test_deja_contactes_apres_deja_identifie():
    noms = investors_service.deja_contactes("Déjà identifié : Réseau Gamma.")
    assert noms == ["Réseau Gamma"]


def test_deja_contactes_apres_hors():
    noms = investors_service.deja_contactes("Trouve des investisseurs, hors Delta Capital.")
    assert noms == ["Delta Capital"]


def test_deja_contactes_aucun_si_absent():
    assert investors_service.deja_contactes("Quels investisseurs pour ma seed ?") == []
    assert investors_service.deja_contactes(None) == []


# --- stade_depuis : la question prime sur le profil -------------------------

def test_stade_depuis_question_prime_sur_profil():
    stade = investors_service.stade_depuis(
        "Pour un tour seed, quels investisseurs ?", {"funding_stage": "Série A"})
    assert stade.lower() == "seed"


def test_stade_depuis_repli_sur_profil_si_absent_de_la_question():
    stade = investors_service.stade_depuis(
        "Quels investisseurs pour mon secteur ?", {"funding_stage": "Série A"})
    assert stade == "Série A"


def test_stade_depuis_aucun_si_ni_question_ni_profil():
    assert investors_service.stade_depuis("Quels investisseurs ?", {}) is None
    assert investors_service.stade_depuis("Quels investisseurs ?", None) is None


# --- composer_par_stade : les 3 cas du §4 -----------------------------------

def _fonds(n: int) -> list[dict]:
    return [{"nom": f"Fonds {i}"} for i in range(n)]


def _reseaux(n: int) -> list[dict]:
    return [{"nom": f"Réseau {i}"} for i in range(n)]


def test_composer_par_stade_pre_seed_reseaux_puis_fonds():
    """Tour de correction 1 (revue Q2) : un plancher de min(3, disponibles)
    fonds est réservé — les réseaux ne mangent plus tout le budget."""
    funds, networks = investors_service.composer_par_stade(
        _fonds(10), _reseaux(10), "pre-seed", limit=6)
    assert len(networks) == 3
    assert len(funds) == 3
    assert len(funds) + len(networks) == 6


def test_composer_par_stade_pre_seed_fonds_complete_si_peu_de_reseaux():
    funds, networks = investors_service.composer_par_stade(
        _fonds(10), _reseaux(2), "idéation", limit=6)
    assert len(networks) == 2
    assert len(funds) == 4
    assert len(funds) + len(networks) == 6


def test_composer_par_stade_seed_parts_egales():
    funds, networks = investors_service.composer_par_stade(
        _fonds(10), _reseaux(10), "seed", limit=6)
    assert len(funds) == 3
    assert len(networks) == 3


def test_composer_par_stade_serie_a_fonds_dabord():
    """Tour de correction 1 (revue Q2) : plancher symétrique de min(3,
    disponibles) réseaux réservé en série A."""
    funds, networks = investors_service.composer_par_stade(
        _fonds(10), _reseaux(10), "série A", limit=6)
    assert len(funds) == 3
    assert len(networks) == 3


def test_composer_par_stade_serie_b_plus_reseaux_completent_si_place():
    funds, networks = investors_service.composer_par_stade(
        _fonds(3), _reseaux(10), "Série B+", limit=6)
    assert len(funds) == 3
    assert len(networks) == 3


def test_composer_par_stade_respecte_toujours_la_limite_globale():
    for stade in ("pre-seed", "seed", "série A"):
        funds, networks = investors_service.composer_par_stade(
            _fonds(20), _reseaux(20), stade, limit=9)
        assert len(funds) + len(networks) <= 9


# --- consigne_pour : N >= et N > --------------------------------------------

def test_consigne_pour_demande_n_disponibles_egal_presente_exactement_n():
    mapping = {"demande": {"n": 8, "disponibles": 8}}
    consigne = investors_service.consigne_pour(mapping)
    assert "présente exactement 8" in consigne


def test_consigne_pour_demande_n_disponibles_superieur_presente_exactement_n():
    mapping = {"demande": {"n": 8, "disponibles": 12}}
    consigne = investors_service.consigne_pour(mapping)
    assert "présente exactement 8" in consigne


def test_consigne_pour_demande_n_disponibles_inferieur_annonce_exhaustivite():
    mapping = {"demande": {"n": 10, "disponibles": 4}}
    consigne = investors_service.consigne_pour(mapping)
    assert "n'en référence que 4" in consigne
    assert "sans compléter avec des noms venus du web" in consigne


def test_consigne_pour_composition_pre_seed_mentionne_non_dilutif():
    mapping = {"stade_retenu": "pre-seed"}
    consigne = investors_service.consigne_pour(mapping)
    assert "Bpifrance" in consigne


def test_consigne_pour_composition_seed_parts_egales():
    mapping = {"stade_retenu": "seed"}
    consigne = investors_service.consigne_pour(mapping)
    assert "parts égales" in consigne


def test_consigne_pour_composition_serie_a_fonds_dabord():
    mapping = {"stade_retenu": "série A"}
    consigne = investors_service.consigne_pour(mapping)
    assert "fonds d'abord" in consigne


def test_consigne_pour_levee_ambigue_phrase_complete():
    mapping = {
        "levee": {"montant_eur": 300_000, "texte": "300 000k€",
                 "lectures": [300_000_000, 300_000], "ambigu": True},
        "stade_retenu": "pre-seed",
    }
    consigne = investors_service.consigne_pour(mapping)
    assert "300 M€" in consigne
    assert "300 k€" in consigne
    assert "300 000k€" in consigne


def test_consigne_pour_exclusions_listees():
    mapping = {"exclus": ["Alpha Ventures", "Beta Capital"]}
    consigne = investors_service.consigne_pour(mapping)
    assert "Alpha Ventures" in consigne
    assert "Beta Capital" in consigne


def test_consigne_pour_vide_si_mapping_sans_signal():
    assert investors_service.consigne_pour({}) == ""


# --- format_context : bloc « Paramètres de la levée retenus » --------------

def test_format_context_bloc_levee_en_tete():
    mapping = {
        "levee": {"montant_eur": 300_000, "texte": "300 K€",
                 "lectures": [300_000], "ambigu": False},
        "stade_retenu": "pre-seed",
        "funds": [], "networks": [],
    }
    ctx = investors_service.format_context(mapping)
    # Tour de correction 1 (revue Q5) : le montant est formaté avec séparateurs
    # de milliers dans le bloc lu par le modèle (« 300 000 € », pas « 300000 »).
    assert ctx.startswith(
        "Paramètres de la levée retenus : montant 300 000 € · stade pre-seed")


def test_format_context_sans_levee_ni_stade_inchange():
    mapping = {
        "funds": [{"nom": "Fonds Alpha", "site_web": "", "score": 1.0,
                  "n_vehicules": 1, "zone": "France",
                  "secteurs": ["Fintech"], "stades": ["Seed"]}],
        "networks": [],
    }
    ctx = investors_service.format_context(mapping)
    assert "Paramètres de la levée" not in ctx
    assert ctx.startswith("[1]")


def test_format_context_ambigu_ajoute_la_phrase_dexplication():
    mapping = {
        "levee": {"montant_eur": 300_000, "texte": "300 000k€",
                 "lectures": [300_000_000, 300_000], "ambigu": True},
        "stade_retenu": "pre-seed",
        "funds": [], "networks": [],
    }
    ctx = investors_service.format_context(mapping)
    assert "se lit 300 M€" in ctx
    assert "300 k€ est plus vraisemblable" in ctx


# --- map_for_profile : question optionnelle, champs exposés ----------------

def _mapping_base(monkeypatch, funds=None, networks=None):
    """Bouchonne la résolution secteur/stade et `search()` pour isoler la
    composition/N/exclusions de `map_for_profile`, sans dataset réel."""
    monkeypatch.setattr(investors_service, "resolve_names",
                        lambda names, referential: [1] if names else [])
    monkeypatch.setattr(investors_service, "_from_onboarding", lambda v, t: [])
    monkeypatch.setattr(investors_service, "_broaden", lambda ids: (ids, [], ""))

    class _FakeDataset(dict):
        def __missing__(self, key):
            return []

    fake = _FakeDataset({
        "secteur": [{"id": 1, "nom": "Fintech"}],
        "stade": [{"id": 1, "nom": "Seed"}],
        "zone_geographique": [],
    })
    monkeypatch.setattr(investors_service.client, "dataset", lambda: fake)
    monkeypatch.setattr(investors_service, "search",
                        lambda secs, stades, zone_id=None:
                        (funds or [], networks or []))


def test_map_for_profile_sans_question_comportement_inchange(monkeypatch):
    funds = [{"nom": f"Fonds {i}"} for i in range(20)]
    networks = [{"nom": f"Réseau {i}"} for i in range(20)]
    _mapping_base(monkeypatch, funds, networks)

    mapping = investors_service.map_for_profile(
        {"sector": "Fintech", "funding_stage": "Seed"})

    assert len(mapping["funds"]) == 15
    assert len(mapping["networks"]) == 15
    assert "demande" not in mapping
    assert "levee" not in mapping


def test_map_for_profile_avec_question_n_et_disponibles(monkeypatch):
    funds = [{"nom": f"Fonds {i}"} for i in range(3)]
    networks = [{"nom": f"Réseau {i}"} for i in range(2)]
    _mapping_base(monkeypatch, funds, networks)

    mapping = investors_service.map_for_profile(
        {"sector": "Fintech", "funding_stage": "Seed"},
        question="Trouve-moi 8 investisseurs déjà contacté Fonds 0")

    assert mapping["demande"]["n"] == 8
    # 3 fonds + 2 réseaux - 1 exclu (« Fonds 0 ») = 4 disponibles.
    assert mapping["demande"]["disponibles"] == 4
    assert mapping["exclus"] == ["Fonds 0"]
    assert all(f["nom"] != "Fonds 0" for f in mapping["funds"])


def test_map_for_profile_avec_question_expose_stade_et_levee(monkeypatch):
    _mapping_base(monkeypatch, [], [])

    mapping = investors_service.map_for_profile(
        {"sector": "Fintech", "funding_stage": "Seed"},
        question="Je lève 500 000 € en seed")

    assert mapping["stade_retenu"].lower() == "seed"
    assert mapping["levee"]["montant_eur"] == 500_000


def test_map_for_profile_premier_rapport_offert_sans_montant_fonctionne(monkeypatch):
    """Le premier rapport offert (question suggérée, sans chiffre) ne doit
    jamais lever d'exception : tous les nouveaux champs sont optionnels."""
    funds = [{"nom": f"Fonds {i}"} for i in range(5)]
    networks = [{"nom": f"Réseau {i}"} for i in range(5)]
    _mapping_base(monkeypatch, funds, networks)

    mapping = investors_service.map_for_profile(
        {"sector": "Fintech", "funding_stage": "Seed"},
        question="Quels investisseurs pourraient financer mon projet ?")

    assert mapping["demande"]["n"] is None
    assert mapping["levee"] is None
    assert mapping["exclus"] == []
    assert mapping["stade_retenu"]
    assert len(mapping["funds"]) + len(mapping["networks"]) <= 15


# --- run_analysis : consigne dynamique dans le prompt, `detail` exposé -----

def _neutraliser_pipeline(monkeypatch, *, mapping):
    monkeypatch.setattr(analysis_service.llm_client, "generation_available",
                        lambda: True)
    monkeypatch.setattr(analysis_service, "sources_de",
                        lambda t: {"web": False, "rag": False, "notion": False,
                                   "investisseurs": True, "pappers": False})
    monkeypatch.setattr(analysis_service, "_evaluer_couverture", lambda q, c: "oui")

    import app.modules.investors.service as investors_mod

    appels = {"map": []}

    def _fake_map(profile, **kw):
        appels["map"].append(kw)
        return mapping

    monkeypatch.setattr(investors_mod, "map_for_profile", _fake_map)
    monkeypatch.setattr(investors_mod, "format_context", lambda m: "contexte investisseurs")
    monkeypatch.setattr(investors_mod, "citations", lambda m: [
        {"title": f"Fonds {i}", "url": f"https://f{i}.vc", "source": "investisseurs"}
        for i in range(5)
    ])

    prompts_captures = []

    class _FakeResult:
        text = "Rapport."
        input_tokens = 10
        output_tokens = 10
        model = "modele-test"
        provider = "test"
        tokens = 20
        stop_reason = "end_turn"

    def _fake_rediger(*, system, prompt, tier, max_tokens, suivi=None, analysis_type=None):
        prompts_captures.append(prompt)
        return _FakeResult()

    monkeypatch.setattr(analysis_service, "_rediger", _fake_rediger)
    return appels, prompts_captures


def test_run_analysis_transmet_la_question_a_map_for_profile(monkeypatch):
    mapping = {"funds": [], "networks": [], "note": None}
    appels, _ = _neutraliser_pipeline(monkeypatch, mapping=mapping)

    analysis_service.run_analysis(
        query="Trouve-moi 8 investisseurs en seed",
        analysis_type="cartographie_investisseurs",
        user_id="11111111-2222-3333-4444-555555555555", profile={"sector": "Fintech"},
    )
    assert appels["map"][0].get("question") == "Trouve-moi 8 investisseurs en seed"


def test_run_analysis_consigne_dynamique_n_egal_disponibles(monkeypatch):
    mapping = {"funds": [], "networks": [], "note": None,
              "demande": {"n": 8, "disponibles": 8}, "exclus": [],
              "levee": None, "stade_retenu": "seed"}
    _, prompts_captures = _neutraliser_pipeline(monkeypatch, mapping=mapping)

    analysis_service.run_analysis(
        query="Trouve-moi 8 investisseurs en seed",
        analysis_type="cartographie_investisseurs",
        user_id="11111111-2222-3333-4444-555555555555", profile={"sector": "Fintech"},
    )
    assert len(prompts_captures) == 1
    assert "présente exactement 8" in prompts_captures[0]


def test_run_analysis_consigne_dynamique_n_superieur_disponibles(monkeypatch):
    mapping = {"funds": [], "networks": [], "note": None,
              "demande": {"n": 10, "disponibles": 4}, "exclus": [],
              "levee": None, "stade_retenu": "seed"}
    _, prompts_captures = _neutraliser_pipeline(monkeypatch, mapping=mapping)

    analysis_service.run_analysis(
        query="Trouve-moi 10 investisseurs en seed",
        analysis_type="cartographie_investisseurs",
        user_id="11111111-2222-3333-4444-555555555555", profile={"sector": "Fintech"},
    )
    assert "n'en référence que 4" in prompts_captures[0]


def test_run_analysis_prompt_garde_les_instructions_specifiques_intactes(monkeypatch):
    """La consigne dynamique s'AJOUTE après `special_instructions` — le texte
    figé de la directive reste mot pour mot présent dans le prompt."""
    mapping = {"funds": [], "networks": [], "note": None,
              "demande": {"n": 8, "disponibles": 8}, "exclus": [],
              "levee": None, "stade_retenu": "seed"}
    _, prompts_captures = _neutraliser_pipeline(monkeypatch, mapping=mapping)

    analysis_service.run_analysis(
        query="Trouve-moi 8 investisseurs en seed",
        analysis_type="cartographie_investisseurs",
        user_id="11111111-2222-3333-4444-555555555555", profile={"sector": "Fintech"},
    )
    directive = analysis_prompts.ANALYSIS_DIRECTIVES["cartographie_investisseurs"]
    assert directive["special_instructions"] in prompts_captures[0]


def test_run_analysis_detail_levee_et_demande_exposes(monkeypatch):
    mapping = {"funds": [], "networks": [], "note": None,
              "demande": {"n": 8, "disponibles": 8}, "exclus": [],
              "levee": {"montant_eur": 500_000, "texte": "500 K€",
                       "lectures": [500_000], "ambigu": False},
              "stade_retenu": "seed"}
    _neutraliser_pipeline(monkeypatch, mapping=mapping)

    resultat = analysis_service.run_analysis(
        query="Trouve-moi 8 investisseurs, on lève 500 K€ en seed",
        analysis_type="cartographie_investisseurs",
        user_id="11111111-2222-3333-4444-555555555555", profile={"sector": "Fintech"},
    )
    assert resultat.metadata["demande"] == {"n": 8, "disponibles": 8}
    assert resultat.metadata["levee"]["montant_eur"] == 500_000


def test_run_analysis_premier_rapport_sans_question_chiffree_fonctionne(monkeypatch):
    """Le premier rapport offert (question suggérée par le produit, sans
    montant ni nombre) doit continuer à produire un rapport normalement."""
    mapping = {"funds": [{"nom": "Fonds Alpha", "site_web": "", "score": 1.0,
                          "n_vehicules": 1, "zone": "France",
                          "secteurs": ["Fintech"], "stades": ["Seed"]}],
              "networks": [], "note": None}
    _, prompts_captures = _neutraliser_pipeline(monkeypatch, mapping=mapping)

    resultat = analysis_service.run_analysis(
        query="Quels investisseurs pourraient me financer ?",
        analysis_type="cartographie_investisseurs",
        user_id="11111111-2222-3333-4444-555555555555", profile={"sector": "Fintech"},
    )
    assert resultat.degraded is False
    assert len(prompts_captures) == 1
    assert resultat.metadata.get("levee") is None
    assert resultat.metadata.get("demande") is None


def test_get_prompt_template_sans_consigne_texte_inchange():
    """Sans consigne complémentaire, le prompt est byte pour byte identique à
    avant — aucune régression sur les autres types de rapport."""
    avant = (
        analysis_prompts.get_prompt_template("synthese_executive")
    )
    apres = analysis_prompts.get_prompt_template(
        "synthese_executive", consigne_supplementaire="")
    assert avant == apres
    assert "Consigne complémentaire" not in avant


def test_get_prompt_template_avec_consigne_apres_special_instructions():
    prompt = analysis_prompts.get_prompt_template(
        "cartographie_investisseurs", consigne_supplementaire="Fais ceci.")
    directive = analysis_prompts.ANALYSIS_DIRECTIVES["cartographie_investisseurs"]
    idx_special = prompt.index(directive["special_instructions"])
    idx_consigne = prompt.index("Fais ceci.")
    assert idx_consigne > idx_special


# =============================================================================
# Tour de correction 1 (revue `.superpowers/sdd/2026-09-18-ciblage-v2/
# t1-review.md`) : C1 (pre seed avec espace), C2 (plausibilité générale +
# choix du bon montant), C3 (faux montants « 6 mois »), Q1 (ordre des
# sources), Q2 (plancher catégorie secondaire), Q3 (`hors` et exclusion par
# nom complet). Les questions citées ci-dessous reprennent, aussi
# fidèlement que le permettent les extraits du rapport de revue, les
# formulations réelles du batch du 16/09 (le batch complet des 11 questions
# n'est pas rejouable hors ligne : seules celles citées verbatim dans la
# revue le sont ici).
# =============================================================================

def test_c1_stade_depuis_pre_seed_avec_espace_questions_reelles():
    """Revue C1 : « pre seed » / « pré seed » écrits avec une espace (et non
    un trait d'union) étaient lus « seed ». Trois questions réelles citées
    par la revue."""
    cas = [
        "Nous levons 4 millions en pre seed/seed, quels investisseurs ?",
        "Nous visons 2 millions en pre seed/seed pour démarrer.",
        "On prépare un tour, 300k euros en pré seed.",
    ]
    for question in cas:
        stade = investors_service.stade_depuis(question, {})
        assert investors_service._categorie_stade(stade) == "pre_seed", question


def test_c1_categorie_stade_pre_seed_avec_espace():
    assert investors_service._categorie_stade("Pre seed") == "pre_seed"
    assert investors_service._categorie_stade("pré seed") == "pre_seed"
    assert investors_service._categorie_stade("preseed") == "pre_seed"


def test_c2_plausibilite_appliquee_a_tout_montant_retenu():
    """Revue C2 : le plafond de plausibilité s'applique à TOUT montant, pas
    seulement au motif « milliers groupés + suffixe » — « 4 millions » en
    pre-seed doit être signalé, pas accepté tel quel."""
    r = investors_service.montant_de_levee(
        "Nous levons 4 millions en pre seed/seed, quels investisseurs ?", "pre-seed")
    assert r["ambigu"] is True
    assert r["lectures"][0] == 4_000_000


def test_c2_montant_adjacent_au_verbe_de_levee_prefere_au_premier():
    """Revue C2, cas exact cité : « Notre marché pèse 300 millions, nous
    levons 800 K€ en pre-seed » doit retenir 800 000 €, pas 300 M€."""
    r = investors_service.montant_de_levee(
        "Notre marché pèse 300 millions, nous levons 800 K€ en pre-seed.",
        "pre-seed")
    assert r["montant_eur"] == 800_000
    assert r["ambigu"] is False


def test_c3_faux_montant_6_mois_le_vrai_montant_est_lu():
    """Revue C3, cas exact cité : « 6 mois » n'est pas 6 M€ ; le vrai montant
    (500 K€) est bien lu."""
    r = investors_service.montant_de_levee(
        "Nous sommes 6 mois après la création, nous levons 500 K€ en seed.",
        "seed")
    assert r["montant_eur"] == 500_000
    assert "mois" not in r["texte"]


@pytest.mark.parametrize("bruit", ["6 mois", "12 marchés", "2 mois", "3 mètres"])
def test_c3_faux_montants_seuls_jamais_lus(bruit):
    assert investors_service.montant_de_levee(f"Nous sommes {bruit} après le lancement.") is None


def test_c3_suffixe_colle_ou_suivi_deuro_reste_valide():
    assert investors_service.montant_de_levee("Objectif 2M pour la suite.")["montant_eur"] == 2_000_000
    assert investors_service.montant_de_levee("On vise 1,5 M€ en série A.")["montant_eur"] == 1_500_000


def test_q3_hors_de_france_nest_plus_une_exclusion():
    assert investors_service.deja_contactes("Trouve 10 investisseurs, hors de France.") == []


def test_q3_hors_nom_propre_reste_une_exclusion():
    assert investors_service.deja_contactes(
        "Trouve des investisseurs, hors Delta Capital.") == ["Delta Capital"]


def test_q3_exclusion_par_nom_complet_pas_par_sous_chaine():
    """Revue Q3 : « Alpha » ne doit plus exclure « Fonds Alpha » par simple
    inclusion — seul le nom complet (insensible casse/accents) compte."""
    assert investors_service._exclu("Fonds Alpha", ["Alpha"]) is False
    assert investors_service._exclu("Alpha", ["Alpha"]) is True
    assert investors_service._exclu("ALPHA VENTURES", ["Alpha Ventures"]) is True
    assert investors_service._exclu("Alpha Ventures", ["alpha ventures"]) is True
    assert investors_service._exclu("Alphà Ventures", ["Alpha Ventures"]) is True


# --- Q1 : l'ordre des sources numérotées suit la composition par stade -----

def _fonds_ctx(n=1, nom="Fonds"):
    return [{"nom": f"{nom} {i}", "site_web": "", "score": 1.0, "n_vehicules": 1,
            "zone": "France", "secteurs": [], "stades": []} for i in range(n)]


def _reseaux_ctx(n=1, nom="Reseau"):
    return [{"nom": f"{nom} {i}", "nature": "business angels", "score": 0.9,
            "secteurs": [], "stades": []} for i in range(n)]


def test_q1_ordre_pre_seed_reseaux_avant_fonds():
    mapping = {"funds": _fonds_ctx(1), "networks": _reseaux_ctx(1),
              "stade_retenu": "pre-seed", "note": None}
    ctx = investors_service.format_context(mapping)
    cits = investors_service.citations(mapping)
    assert "[1]" in ctx.split("[2]")[0]
    assert "Reseau 0" in ctx.split("[2]")[0]
    assert cits[0]["title"] == "Reseau 0"
    assert cits[1]["title"] == "Fonds 0"


def test_q1_ordre_serie_a_fonds_avant_reseaux():
    mapping = {"funds": _fonds_ctx(1), "networks": _reseaux_ctx(1),
              "stade_retenu": "série A", "note": None}
    cits = investors_service.citations(mapping)
    assert cits[0]["title"] == "Fonds 0"
    assert cits[1]["title"] == "Reseau 0"


def test_q1_ordre_seed_alterne():
    mapping = {"funds": _fonds_ctx(2), "networks": _reseaux_ctx(2),
              "stade_retenu": "seed", "note": None}
    cits = investors_service.citations(mapping)
    assert [c["title"] for c in cits] == ["Reseau 0", "Fonds 0", "Reseau 1", "Fonds 1"]


def test_q1_ordre_inchange_sans_stade_retenu():
    """Sans `stade_retenu` (appel direct sans `question`), l'ordre reste
    fonds-puis-réseaux : aucune régression sur le contrat existant."""
    mapping = {"funds": _fonds_ctx(1), "networks": _reseaux_ctx(1), "note": None}
    cits = investors_service.citations(mapping)
    assert cits[0]["title"] == "Fonds 0"
    assert cits[1]["title"] == "Reseau 0"


# --- Batterie de questions réelles du 16/09 (spec §5, revue Q5) ------------

_QUESTIONS_REELLES_16_09 = [
    # (question, catégorie de stade attendue, montant_eur attendu, ambigu attendu)
    ("Nous levons 4 millions en pre seed/seed, quels investisseurs ?",
     "pre_seed", 4_000, True),
    ("Nous visons 2 millions en pre seed/seed pour démarrer.",
     "pre_seed", 2_000_000, False),
    ("On prépare un tour, 300k euros en pré seed.",
     "pre_seed", 300_000, False),
    ("Notre marché pèse 300 millions, nous levons 800 K€ en pre-seed.",
     "pre_seed", 800_000, False),
    ("Nous sommes 6 mois après la création, nous levons 500 K€ en seed.",
     "seed", 500_000, False),
    ("Je prépare une levée de 300 000k€ en pre-seed.",
     "pre_seed", 300_000, True),
]


@pytest.mark.parametrize("question,categorie_attendue,montant_attendu,ambigu_attendu",
                         _QUESTIONS_REELLES_16_09)
def test_questions_reelles_16_09_stade_et_montant(
        question, categorie_attendue, montant_attendu, ambigu_attendu):
    stade = investors_service.stade_depuis(question, {})
    assert investors_service._categorie_stade(stade) == categorie_attendue, question
    r = investors_service.montant_de_levee(question, stade)
    assert r is not None, question
    assert r["montant_eur"] == montant_attendu, question
    assert r["ambigu"] is ambigu_attendu, question
