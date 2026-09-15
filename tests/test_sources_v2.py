"""Sources v2 — Task 1 : contraintes de recherche, propagation, filtre de
pertinence. Voir `docs/superpowers/specs/2026-09-14-sources-v2.md` §1.
"""
from __future__ import annotations

import dataclasses
import re
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.modules.kb.models import KbDocument
from app.shared.search.contraintes import (
    Contraintes,
    DOMAINES_EXCLUS_DEFAUT,
    DOMAINES_OFFICIELS_FR_UE,
    contraintes_pour,
)
from app.shared.search import rerank
from app.shared.search.base import SearchResult
from app.shared.search import orchestrator
from app.shared.search.providers import ExaProvider, LinkupProvider, TavilyProvider


# --- Contraintes : dataclass -------------------------------------------------

def test_contraintes_dataclass_defauts():
    c = Contraintes()
    assert c.fraicheur_jours is None
    assert c.domaines_inclus == ()
    assert c.domaines_exclus == ()
    assert c.seuil_pertinence is None
    assert c.garde_minimale == 3


def test_contraintes_dataclass_est_immuable():
    c = Contraintes()
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.fraicheur_jours = 90  # type: ignore[misc]


# --- contraintes_pour : défauts par type de rapport --------------------------

def test_contraintes_pour_type_reglementaire():
    c = contraintes_pour("point sur le marché", "analyse_reglementaire")
    assert c.fraicheur_jours == 365
    assert set(DOMAINES_OFFICIELS_FR_UE) <= set(c.domaines_inclus)


def test_contraintes_pour_type_risques():
    c = contraintes_pour("point sur le marché", "analyse_risques")
    assert c.fraicheur_jours == 365


def test_contraintes_pour_type_veille_technologique():
    c = contraintes_pour("point sur le marché", "veille_technologique")
    assert c.fraicheur_jours == 365


def test_contraintes_pour_type_concurrentielle_730():
    c = contraintes_pour("point sur le marché", "analyse_concurrentielle")
    assert c.fraicheur_jours == 730


def test_contraintes_pour_type_etude_marche_730():
    c = contraintes_pour("point sur le marché", "etude_marche")
    assert c.fraicheur_jours == 730


def test_contraintes_pour_type_synthese_executive_730():
    c = contraintes_pour("point sur le marché", "synthese_executive")
    assert c.fraicheur_jours == 730


def test_contraintes_pour_type_cartographie_investisseurs_730():
    c = contraintes_pour("point sur le marché", "cartographie_investisseurs")
    assert c.fraicheur_jours == 730


def test_contraintes_pour_conversation_aucun_filtre_par_defaut():
    c = contraintes_pour("qui sont les investisseurs deeptech ?", None)
    assert c.fraicheur_jours is None
    assert c.domaines_inclus == ()


def test_contraintes_pour_domaines_exclus_toujours_presents():
    for t in (None, "analyse_reglementaire", "etude_marche"):
        c = contraintes_pour("question quelconque", t)
        assert set(DOMAINES_EXCLUS_DEFAUT) <= set(c.domaines_exclus)


# --- contraintes_pour : mots de la question ----------------------------------

def test_contraintes_pour_mot_actualite_recente_90j():
    c = contraintes_pour("Quelles sont les dernières nouvelles du secteur ?")
    assert c.fraicheur_jours == 90


def test_contraintes_pour_mot_latest_news_en_90j():
    c = contraintes_pour("What is the latest news on this market?")
    assert c.fraicheur_jours == 90


def test_contraintes_pour_mot_cette_annee_365j():
    c = contraintes_pour("Quelles levées de fonds en 2026 ?")
    assert c.fraicheur_jours == 365


def test_contraintes_pour_mot_reglementation_365j_et_domaines_officiels():
    c = contraintes_pour("Quelle réglementation RGPD s'applique ?", None)
    assert c.fraicheur_jours == 365
    assert "legifrance.gouv.fr" in c.domaines_inclus
    assert "cnil.fr" in c.domaines_inclus


def test_contraintes_pour_mot_ai_act_365j_domaines_officiels():
    c = contraintes_pour("Quel est l'impact de l'AI Act ?", None)
    assert c.fraicheur_jours == 365
    assert set(DOMAINES_OFFICIELS_FR_UE) <= set(c.domaines_inclus)


def test_contraintes_pour_mot_historique_seul_aucun_filtre():
    c = contraintes_pour("Quelle est l'évolution sur ce marché ?", None)
    assert c.fraicheur_jours is None


def test_contraintes_pour_mot_historique_annule_le_defaut_du_type():
    # « historique » doit neutraliser la fraîcheur même quand le type de
    # rapport en pose une par défaut (etude_marche → 730 j sinon).
    c = contraintes_pour(
        "Quelle est l'évolution sur ce marché depuis 2015 ?", "etude_marche")
    assert c.fraicheur_jours is None


def test_contraintes_pour_mot_historique_annule_le_defaut_reglementaire():
    c = contraintes_pour("Historique du secteur", "analyse_reglementaire")
    assert c.fraicheur_jours is None
    # Les domaines officiels restent posés par le type — seule la fraîcheur
    # est neutralisée.
    assert set(DOMAINES_OFFICIELS_FR_UE) <= set(c.domaines_inclus)


def test_contraintes_pour_mot_historique_gagne_sur_les_autres_mots():
    # « récente » (90j) et « évolution sur » (aucun filtre) matchent tous
    # les deux : historique l'emporte sur les autres règles de mots.
    c = contraintes_pour(
        "Quelle est l'actualité récente et l'évolution sur ce marché ?", None)
    assert c.fraicheur_jours is None


def test_contraintes_pour_regle_plus_restrictive_gagne_type_vs_mot():
    # Défaut du type (730j) vs mot de la question (90j) : le plus restrictif
    # (90j) l'emporte.
    c = contraintes_pour("Actualité récente du marché", "etude_marche")
    assert c.fraicheur_jours == 90


def test_contraintes_pour_insensible_a_la_casse():
    c = contraintes_pour("DERNIÈRE actualité du secteur")
    assert c.fraicheur_jours == 90


def test_contraintes_pour_fonction_pure():
    q = "Quelle réglementation récente en 2026 ?"
    c1 = contraintes_pour(q, "analyse_reglementaire")
    c2 = contraintes_pour(q, "analyse_reglementaire")
    assert c1 == c2


# --- Propagation : fournisseurs (Exa / Tavily / Linkup) ----------------------

def _contraintes_test(**kw):
    base = dict(fraicheur_jours=90,
                domaines_inclus=("legifrance.gouv.fr",),
                domaines_exclus=("pinterest.com",))
    base.update(kw)
    return Contraintes(**base)


def test_propagation_exa_transmet_fraicheur_et_domaines(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "cle-test")
    get_settings.cache_clear()
    captured = {}

    def _fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"results": []}
        return R()

    import app.shared.search.providers as P
    monkeypatch.setattr(P.httpx, "post", _fake_post)
    ExaProvider().search("marché IA", 10, contraintes=_contraintes_test())
    body = captured["json"]
    assert "startPublishedDate" in body
    assert re.match(r"\d{4}-\d{2}-\d{2}T00:00:00\.000Z", body["startPublishedDate"])
    assert body["includeDomains"] == ["legifrance.gouv.fr"]
    # domaines_inclus posé : l'exclusion n'est pas envoyée (certains
    # fournisseurs refusent la combinaison des deux listes).
    assert "excludeDomains" not in body
    get_settings.cache_clear()


def test_propagation_exa_exclut_seulement_sans_domaines_inclus(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "cle-test")
    get_settings.cache_clear()
    captured = {}

    def _fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"results": []}
        return R()

    import app.shared.search.providers as P
    monkeypatch.setattr(P.httpx, "post", _fake_post)
    ExaProvider().search("marché IA", 10,
                         contraintes=_contraintes_test(domaines_inclus=()))
    body = captured["json"]
    assert "includeDomains" not in body
    assert body["excludeDomains"] == ["pinterest.com"]
    get_settings.cache_clear()


def test_propagation_exa_sans_fraicheur_pas_de_date(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "cle-test")
    get_settings.cache_clear()
    captured = {}

    def _fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"results": []}
        return R()

    import app.shared.search.providers as P
    monkeypatch.setattr(P.httpx, "post", _fake_post)
    ExaProvider().search("marché IA", 10, contraintes=Contraintes())
    assert "startPublishedDate" not in captured["json"]
    assert "includeDomains" not in captured["json"]
    get_settings.cache_clear()


def test_propagation_exa_contraintes_none_comportement_actuel(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "cle-test")
    get_settings.cache_clear()
    captured = {}

    def _fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"results": []}
        return R()

    import app.shared.search.providers as P
    monkeypatch.setattr(P.httpx, "post", _fake_post)
    ExaProvider().search("marché IA", 10)
    assert "startPublishedDate" not in captured["json"]
    assert set(captured["json"].keys()) == {"query", "numResults", "contents"}
    get_settings.cache_clear()


def test_propagation_tavily_time_range_month_si_fraicheur_31j(monkeypatch):
    """Décision du 14/09 (validation prod) : Tavily ignore `include_domains`
    quand `days` est envoyé dans le même appel — `days` n'est donc plus
    jamais utilisé, uniquement `time_range`."""
    monkeypatch.setenv("TAVILY_API_KEY", "cle-test")
    get_settings.cache_clear()
    captured = {}

    def _fake_post(url, json=None, timeout=None):
        captured["json"] = json

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"results": []}
        return R()

    import app.shared.search.providers as P
    monkeypatch.setattr(P.httpx, "post", _fake_post)
    TavilyProvider().search("marché IA", 10, contraintes=_contraintes_test(fraicheur_jours=31))
    body = captured["json"]
    assert body["time_range"] == "month"
    assert "days" not in body
    assert body["include_domains"] == ["legifrance.gouv.fr"]
    assert "exclude_domains" not in body
    get_settings.cache_clear()


def test_propagation_tavily_time_range_day_si_fraicheur_1j(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "cle-test")
    get_settings.cache_clear()
    captured = {}

    def _fake_post(url, json=None, timeout=None):
        captured["json"] = json

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"results": []}
        return R()

    import app.shared.search.providers as P
    monkeypatch.setattr(P.httpx, "post", _fake_post)
    TavilyProvider().search("marché IA", 10, contraintes=_contraintes_test(fraicheur_jours=1))
    assert captured["json"]["time_range"] == "day"
    assert "days" not in captured["json"]
    get_settings.cache_clear()


def test_propagation_tavily_time_range_week_si_fraicheur_7j(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "cle-test")
    get_settings.cache_clear()
    captured = {}

    def _fake_post(url, json=None, timeout=None):
        captured["json"] = json

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"results": []}
        return R()

    import app.shared.search.providers as P
    monkeypatch.setattr(P.httpx, "post", _fake_post)
    TavilyProvider().search("marché IA", 10, contraintes=_contraintes_test(fraicheur_jours=7))
    assert captured["json"]["time_range"] == "week"
    assert "days" not in captured["json"]
    get_settings.cache_clear()


def test_propagation_tavily_exclut_seulement_sans_domaines_inclus(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "cle-test")
    get_settings.cache_clear()
    captured = {}

    def _fake_post(url, json=None, timeout=None):
        captured["json"] = json

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"results": []}
        return R()

    import app.shared.search.providers as P
    monkeypatch.setattr(P.httpx, "post", _fake_post)
    TavilyProvider().search("marché IA", 10,
                            contraintes=_contraintes_test(domaines_inclus=()))
    body = captured["json"]
    assert "include_domains" not in body
    assert body["exclude_domains"] == ["pinterest.com"]
    get_settings.cache_clear()


def test_propagation_tavily_time_range_year_si_fraicheur_superieure_365(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "cle-test")
    get_settings.cache_clear()
    captured = {}

    def _fake_post(url, json=None, timeout=None):
        captured["json"] = json

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"results": []}
        return R()

    import app.shared.search.providers as P
    monkeypatch.setattr(P.httpx, "post", _fake_post)
    TavilyProvider().search("marché IA", 10, contraintes=_contraintes_test(fraicheur_jours=730))
    body = captured["json"]
    assert body["time_range"] == "year"
    assert "days" not in body
    get_settings.cache_clear()


def test_propagation_tavily_time_range_year_si_fraicheur_365j(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "cle-test")
    get_settings.cache_clear()
    captured = {}

    def _fake_post(url, json=None, timeout=None):
        captured["json"] = json

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"results": []}
        return R()

    import app.shared.search.providers as P
    monkeypatch.setattr(P.httpx, "post", _fake_post)
    TavilyProvider().search("marché IA", 10, contraintes=_contraintes_test(fraicheur_jours=365))
    assert captured["json"]["time_range"] == "year"
    assert "days" not in captured["json"]
    get_settings.cache_clear()


def test_propagation_linkup_fromdate_et_domaines(monkeypatch):
    monkeypatch.setenv("LINKUP_API_KEY", "cle-test")
    get_settings.cache_clear()
    captured = {}

    def _fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"results": []}
        return R()

    import app.shared.search.providers as P
    monkeypatch.setattr(P.httpx, "post", _fake_post)
    LinkupProvider().search("marché IA", 10, contraintes=_contraintes_test())
    body = captured["json"]
    assert re.match(r"\d{4}-\d{2}-\d{2}$", body["fromDate"])
    assert body["includeDomains"] == ["legifrance.gouv.fr"]
    assert "excludeDomains" not in body
    get_settings.cache_clear()


def test_propagation_linkup_exclut_seulement_sans_domaines_inclus(monkeypatch):
    monkeypatch.setenv("LINKUP_API_KEY", "cle-test")
    get_settings.cache_clear()
    captured = {}

    def _fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"results": []}
        return R()

    import app.shared.search.providers as P
    monkeypatch.setattr(P.httpx, "post", _fake_post)
    LinkupProvider().search("marché IA", 10,
                            contraintes=_contraintes_test(domaines_inclus=()))
    body = captured["json"]
    assert "includeDomains" not in body
    assert body["excludeDomains"] == ["pinterest.com"]
    get_settings.cache_clear()


def test_propagation_linkup_sans_contraintes_pas_de_champs_ajoutes(monkeypatch):
    monkeypatch.setenv("LINKUP_API_KEY", "cle-test")
    get_settings.cache_clear()
    captured = {}

    def _fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"results": []}
        return R()

    import app.shared.search.providers as P
    monkeypatch.setattr(P.httpx, "post", _fake_post)
    LinkupProvider().search("marché IA", 10)
    assert set(captured["json"].keys()) == {"q", "depth", "outputType"}
    get_settings.cache_clear()


# --- Filtre de pertinence (rerank) -------------------------------------------

def _resultats(n):
    return [SearchResult(title=f"t{i}", url=f"https://ex{i}.com/a", snippet="s",
                          provider="exa") for i in range(n)]


def test_pertinence_filtre_sous_seuil_avec_cohere(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "cle-test")
    get_settings.cache_clear()
    results = _resultats(5)
    scores = [0.9, 0.8, 0.5, 0.1, 0.05]  # indices 3,4 sous 0.30

    def _fake_post(url, headers=None, json=None, timeout=None):
        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"results": [{"index": i, "relevance_score": s}
                                     for i, s in enumerate(scores)]}
        return R()

    monkeypatch.setattr(rerank.httpx, "post", _fake_post)
    compteur = {}
    out = rerank.rerank("q", results, top_k=5, compteur=compteur)
    assert [r.score for r in out] == [0.9, 0.8, 0.5]
    assert compteur["_ecartes"] == 2
    get_settings.cache_clear()


def test_pertinence_garde_minimale_meme_sous_seuil(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "cle-test")
    get_settings.cache_clear()
    results = _resultats(5)
    scores = [0.05, 0.04, 0.03, 0.02, 0.01]  # tout sous le seuil

    def _fake_post(url, headers=None, json=None, timeout=None):
        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"results": [{"index": i, "relevance_score": s}
                                     for i, s in enumerate(scores)]}
        return R()

    monkeypatch.setattr(rerank.httpx, "post", _fake_post)
    compteur = {}
    out = rerank.rerank("q", results, top_k=5, compteur=compteur)
    assert len(out) == 3  # garde_minimale par défaut
    assert compteur["_ecartes"] == 2
    get_settings.cache_clear()


def test_pertinence_garde_minimale_personnalisee(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "cle-test")
    get_settings.cache_clear()
    results = _resultats(5)
    scores = [0.05, 0.04, 0.03, 0.02, 0.01]

    def _fake_post(url, headers=None, json=None, timeout=None):
        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"results": [{"index": i, "relevance_score": s}
                                     for i, s in enumerate(scores)]}
        return R()

    monkeypatch.setattr(rerank.httpx, "post", _fake_post)
    out = rerank.rerank("q", results, top_k=5,
                        contraintes=Contraintes(garde_minimale=1))
    assert len(out) == 1
    get_settings.cache_clear()


def test_pertinence_sans_cohere_aucun_filtre(monkeypatch):
    monkeypatch.delenv("COHERE_API_KEY", raising=False)
    get_settings.cache_clear()
    results = _resultats(5)
    compteur = {}
    out = rerank.rerank("q", results, top_k=5, compteur=compteur)
    assert len(out) == 5
    assert compteur.get("_ecartes", 0) == 0
    get_settings.cache_clear()


def test_pertinence_panne_cohere_aucun_filtre_malgre_la_cle(monkeypatch):
    """Clé Cohere posée mais appel en échec (timeout/429/503) : repli
    identité, scores à 0.0 — ne doit PAS être traité comme « tout est sous le
    seuil ». Les 10 résultats doivent survivre, pas seulement la garde
    minimale."""
    monkeypatch.setenv("COHERE_API_KEY", "cle-test")
    get_settings.cache_clear()
    results = _resultats(10)

    def _fake_post(url, headers=None, json=None, timeout=None):
        raise RuntimeError("503 Service Unavailable")

    monkeypatch.setattr(rerank.httpx, "post", _fake_post)
    compteur = {}
    out = rerank.rerank("q", results, top_k=10, compteur=compteur)
    assert len(out) == 10
    assert compteur.get("_ecartes", 0) == 0
    get_settings.cache_clear()


def test_pertinence_cohere_sans_resultat_exploitable_aucun_filtre(monkeypatch):
    """Appel Cohere réussi mais `results` vide dans la réponse : pas de score
    réel non plus, même comportement que le repli."""
    monkeypatch.setenv("COHERE_API_KEY", "cle-test")
    get_settings.cache_clear()
    results = _resultats(5)

    def _fake_post(url, headers=None, json=None, timeout=None):
        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"results": []}
        return R()

    monkeypatch.setattr(rerank.httpx, "post", _fake_post)
    out = rerank.rerank("q", results, top_k=5)
    assert len(out) == 5
    get_settings.cache_clear()


def test_pertinence_seuil_contraintes_explicite_l_emporte(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "cle-test")
    get_settings.cache_clear()
    results = _resultats(5)
    scores = [0.9, 0.8, 0.7, 0.6, 0.5]

    def _fake_post(url, headers=None, json=None, timeout=None):
        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"results": [{"index": i, "relevance_score": s}
                                     for i, s in enumerate(scores)]}
        return R()

    monkeypatch.setattr(rerank.httpx, "post", _fake_post)
    # Seuil explicite très haut : ne garde que la garde minimale.
    out = rerank.rerank("q", results, top_k=5,
                        contraintes=Contraintes(seuil_pertinence=0.95, garde_minimale=2))
    assert len(out) == 2
    get_settings.cache_clear()


def test_pertinence_seuil_par_defaut_vient_des_settings(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "cle-test")
    monkeypatch.setenv("SEUIL_PERTINENCE_RECHERCHE", "0.6")
    get_settings.cache_clear()
    results = _resultats(5)
    scores = [0.9, 0.7, 0.5, 0.3, 0.1]

    def _fake_post(url, headers=None, json=None, timeout=None):
        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"results": [{"index": i, "relevance_score": s}
                                     for i, s in enumerate(scores)]}
        return R()

    monkeypatch.setattr(rerank.httpx, "post", _fake_post)
    out = rerank.rerank("q", results, top_k=5)
    # 0.9 et 0.7 >= 0.6 ; les 3 suivants sous le seuil mais garde_minimale=3
    # couvre déjà les deux premiers + 1 de plus.
    assert len(out) == 3
    get_settings.cache_clear()


# --- Propagation : orchestrateur ---------------------------------------------

class _FauxProvider:
    def __init__(self, name, resultats_par_appel):
        self.name = name
        self._resultats_par_appel = list(resultats_par_appel)
        self.appels = []

    def available(self):
        return True

    def search(self, query, limit, contraintes=None):
        self.appels.append(contraintes)
        if self._resultats_par_appel:
            return self._resultats_par_appel.pop(0)
        return []


def test_propagation_search_transmet_contraintes_au_fournisseur(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "")
    get_settings.cache_clear()
    fake = _FauxProvider("exa", [_resultats(3)])
    monkeypatch.setattr(orchestrator, "get_provider", lambda n: fake if n == "exa" else None)
    monkeypatch.setenv("SEARCH_PROVIDERS", "exa")
    get_settings.cache_clear()
    c = Contraintes(fraicheur_jours=90)
    orchestrator.search("q", top_k=3, contraintes=c)
    assert fake.appels[0] is c
    get_settings.cache_clear()


def test_propagation_search_multi_transmet_contraintes_au_fournisseur(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "")
    monkeypatch.setenv("SEARCH_PROVIDERS", "exa")
    get_settings.cache_clear()
    fake = _FauxProvider("exa", [_resultats(3), _resultats(3)])
    monkeypatch.setattr(orchestrator, "get_provider", lambda n: fake if n == "exa" else None)
    c = Contraintes(fraicheur_jours=90)
    orchestrator.search_multi(["q1", "q2"], top_k=3, contraintes=c)
    assert all(a is c for a in fake.appels)
    get_settings.cache_clear()


def test_propagation_search_contraintes_none_comportement_actuel(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "")
    monkeypatch.setenv("SEARCH_PROVIDERS", "exa")
    get_settings.cache_clear()
    fake = _FauxProvider("exa", [_resultats(3)])
    monkeypatch.setattr(orchestrator, "get_provider", lambda n: fake if n == "exa" else None)
    out = orchestrator.search("q", top_k=3)
    assert fake.appels[0] is None
    assert len(out) == 3
    get_settings.cache_clear()


def test_propagation_relance_sans_domaines_inclus_si_pool_vide(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "")
    monkeypatch.setenv("SEARCH_PROVIDERS", "exa")
    get_settings.cache_clear()
    # 1er appel (avec domaines inclus) : rien. 2e appel (relance) : des résultats.
    fake = _FauxProvider("exa", [[], _resultats(3)])
    monkeypatch.setattr(orchestrator, "get_provider", lambda n: fake if n == "exa" else None)
    c = Contraintes(domaines_inclus=("legifrance.gouv.fr",))
    out = orchestrator.search("q", top_k=3, contraintes=c)
    assert len(fake.appels) == 2
    assert fake.appels[0].domaines_inclus == ("legifrance.gouv.fr",)
    assert fake.appels[1].domaines_inclus == ()
    assert len(out) == 3
    get_settings.cache_clear()


def test_propagation_relance_une_seule_fois(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "")
    monkeypatch.setenv("SEARCH_PROVIDERS", "exa")
    get_settings.cache_clear()
    fake = _FauxProvider("exa", [[], []])  # toujours vide
    monkeypatch.setattr(orchestrator, "get_provider", lambda n: fake if n == "exa" else None)
    c = Contraintes(domaines_inclus=("legifrance.gouv.fr",))
    out = orchestrator.search("q", top_k=3, contraintes=c)
    assert len(fake.appels) == 2  # pas de 3e tentative
    assert out == []
    get_settings.cache_clear()


def test_propagation_pas_de_relance_sans_domaines_inclus(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "")
    monkeypatch.setenv("SEARCH_PROVIDERS", "exa")
    get_settings.cache_clear()
    fake = _FauxProvider("exa", [[]])
    monkeypatch.setattr(orchestrator, "get_provider", lambda n: fake if n == "exa" else None)
    c = Contraintes()  # pas de domaines inclus
    out = orchestrator.search("q", top_k=3, contraintes=c)
    assert len(fake.appels) == 1
    assert out == []
    get_settings.cache_clear()


def test_propagation_relance_sans_domaines_inclus_search_multi(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "")
    monkeypatch.setenv("SEARCH_PROVIDERS", "exa")
    get_settings.cache_clear()
    fake = _FauxProvider("exa", [[], [], _resultats(2), _resultats(2)])
    monkeypatch.setattr(orchestrator, "get_provider", lambda n: fake if n == "exa" else None)
    c = Contraintes(domaines_inclus=("legifrance.gouv.fr",))
    out = orchestrator.search_multi(["q1", "q2"], top_k=3, contraintes=c)
    assert len(fake.appels) == 4  # 2 angles x (1 initial + 1 relance)
    assert fake.appels[-1].domaines_inclus == ()
    assert len(out) > 0
    get_settings.cache_clear()


def test_propagation_compteur_ecartes_rempli_par_orchestrateur(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "cle-test")
    monkeypatch.setenv("SEARCH_PROVIDERS", "exa")
    get_settings.cache_clear()
    fake = _FauxProvider("exa", [_resultats(5)])
    monkeypatch.setattr(orchestrator, "get_provider", lambda n: fake if n == "exa" else None)
    scores = [0.9, 0.8, 0.1, 0.05, 0.01]

    def _fake_post(url, headers=None, json=None, timeout=None):
        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"results": [{"index": i, "relevance_score": s}
                                     for i, s in enumerate(scores)]}
        return R()

    monkeypatch.setattr(rerank.httpx, "post", _fake_post)
    compteur = {}
    orchestrator.search("q", top_k=5, compteur=compteur)
    assert compteur["_ecartes"] == 2
    get_settings.cache_clear()


# --- Cas limites (R9, revue tour 1) ------------------------------------------

def test_pertinence_top_k_inferieur_a_la_garde_minimale(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "cle-test")
    get_settings.cache_clear()
    results = _resultats(5)
    scores = [0.01, 0.01]

    def _fake_post(url, headers=None, json=None, timeout=None):
        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"results": [{"index": i, "relevance_score": s}
                                     for i, s in enumerate(scores)]}
        return R()

    monkeypatch.setattr(rerank.httpx, "post", _fake_post)
    out = rerank.rerank("q", results, top_k=2)  # top_k < garde_minimale (3)
    assert len(out) == 2
    get_settings.cache_clear()


def test_contraintes_pour_domaines_exclus_vide_si_override():
    c = Contraintes(domaines_exclus=())
    assert c.domaines_exclus == ()


def test_contraintes_pour_type_inconnu_aucun_filtre():
    c = contraintes_pour("question quelconque", "type_qui_n_existe_pas")
    assert c.fraicheur_jours is None
    assert c.domaines_inclus == ()


# --- Task 2 : Perplexity et cascade à niveaux --------------------------------
# Voir `docs/superpowers/specs/2026-09-14-sources-v2.md` §2 et
# `.superpowers/sdd/2026-09-14-sources-v2/task-2-brief.md`.

from app.shared.search.providers import PerplexityProvider


# --- settings.search_tier_list -----------------------------------------------

def test_tiers_defaut_deux_niveaux(monkeypatch):
    monkeypatch.delenv("SEARCH_TIERS", raising=False)
    get_settings.cache_clear()
    s = get_settings()
    assert s.search_tiers == "perplexity,exa|tavily,linkup"
    assert s.search_tier_list == [["perplexity", "exa"], ["tavily", "linkup"]]
    get_settings.cache_clear()


def test_tiers_vide_replie_sur_search_providers(monkeypatch):
    monkeypatch.setenv("SEARCH_TIERS", "")
    monkeypatch.setenv("SEARCH_PROVIDERS", "exa,tavily")
    get_settings.cache_clear()
    assert get_settings().search_tier_list == [["exa", "tavily"]]
    get_settings.cache_clear()


def test_tiers_niveau_vide_saute(monkeypatch):
    monkeypatch.setenv("SEARCH_TIERS", "exa,|tavily")
    get_settings.cache_clear()
    assert get_settings().search_tier_list == [["exa"], ["tavily"]]
    get_settings.cache_clear()


def test_tiers_un_seul_niveau(monkeypatch):
    monkeypatch.setenv("SEARCH_TIERS", "exa,tavily,linkup")
    get_settings.cache_clear()
    assert get_settings().search_tier_list == [["exa", "tavily", "linkup"]]
    get_settings.cache_clear()


# --- Perplexity : requête -----------------------------------------------------

def _fake_post_perplexity(monkeypatch, captured, data):
    def _fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return data
        return R()

    import app.shared.search.providers as P
    monkeypatch.setattr(P.httpx, "post", _fake_post)


def test_perplexity_available_avec_cle(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "cle-test")
    get_settings.cache_clear()
    assert PerplexityProvider().available() is True
    get_settings.cache_clear()


def test_perplexity_available_sans_cle(monkeypatch):
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    get_settings.cache_clear()
    assert PerplexityProvider().available() is False
    get_settings.cache_clear()


def test_perplexity_transmet_modele_et_prompt(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "cle-test")
    get_settings.cache_clear()
    captured = {}
    _fake_post_perplexity(monkeypatch, captured, {"choices": [{"message": {"content": ""}}]})
    PerplexityProvider().search("réglementation IA en France", 10)
    body = captured["json"]
    assert body["model"] == get_settings().perplexity_model_chat
    assert body["messages"][0]["role"] == "system"
    assert "moteur de recherche" in body["messages"][0]["content"]
    assert body["messages"][1] == {"role": "user", "content": "réglementation IA en France"}
    assert body["return_related_questions"] is False
    assert captured["headers"]["Authorization"] == "Bearer cle-test"
    assert captured["timeout"] == 20.0
    assert captured["url"] == "https://api.perplexity.ai/chat/completions"
    get_settings.cache_clear()


def test_perplexity_recency_filter_month_si_fraicheur_31j(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "cle-test")
    get_settings.cache_clear()
    captured = {}
    _fake_post_perplexity(monkeypatch, captured, {"choices": [{"message": {"content": ""}}]})
    PerplexityProvider().search("q", 10, contraintes=Contraintes(fraicheur_jours=31))
    assert captured["json"]["search_recency_filter"] == "month"
    get_settings.cache_clear()


def test_perplexity_recency_filter_year_si_fraicheur_365j(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "cle-test")
    get_settings.cache_clear()
    captured = {}
    _fake_post_perplexity(monkeypatch, captured, {"choices": [{"message": {"content": ""}}]})
    PerplexityProvider().search("q", 10, contraintes=Contraintes(fraicheur_jours=365))
    assert captured["json"]["search_recency_filter"] == "year"
    get_settings.cache_clear()


def test_perplexity_recency_filter_absent_si_fraicheur_superieure_365j(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "cle-test")
    get_settings.cache_clear()
    captured = {}
    _fake_post_perplexity(monkeypatch, captured, {"choices": [{"message": {"content": ""}}]})
    PerplexityProvider().search("q", 10, contraintes=Contraintes(fraicheur_jours=730))
    assert "search_recency_filter" not in captured["json"]
    get_settings.cache_clear()


def test_perplexity_recency_filter_absent_sans_contraintes(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "cle-test")
    get_settings.cache_clear()
    captured = {}
    _fake_post_perplexity(monkeypatch, captured, {"choices": [{"message": {"content": ""}}]})
    PerplexityProvider().search("q", 10)
    assert "search_recency_filter" not in captured["json"]
    assert "search_domain_filter" not in captured["json"]
    get_settings.cache_clear()


def test_perplexity_domain_filter_inclus(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "cle-test")
    get_settings.cache_clear()
    captured = {}
    _fake_post_perplexity(monkeypatch, captured, {"choices": [{"message": {"content": ""}}]})
    c = Contraintes(domaines_inclus=("legifrance.gouv.fr",), domaines_exclus=("pinterest.com",))
    PerplexityProvider().search("q", 10, contraintes=c)
    assert captured["json"]["search_domain_filter"] == ["legifrance.gouv.fr"]
    get_settings.cache_clear()


def test_perplexity_domain_filter_exclus_prefixe_moins_sans_inclus(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "cle-test")
    get_settings.cache_clear()
    captured = {}
    _fake_post_perplexity(monkeypatch, captured, {"choices": [{"message": {"content": ""}}]})
    c = Contraintes(domaines_exclus=("pinterest.com", "facebook.com"))
    PerplexityProvider().search("q", 10, contraintes=c)
    assert captured["json"]["search_domain_filter"] == ["-pinterest.com", "-facebook.com"]
    get_settings.cache_clear()


# --- Perplexity : réponse -----------------------------------------------------

def test_perplexity_search_results_avec_snippet(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "cle-test")
    get_settings.cache_clear()
    captured = {}
    data = {
        "choices": [{"message": {"content": "Sans rapport avec le snippet."}}],
        "search_results": [
            {"title": "T1", "url": "https://a.com", "snippet": "Résumé A", "date": "2026-01-01"},
        ],
    }
    _fake_post_perplexity(monkeypatch, captured, data)
    out = PerplexityProvider().search("q", 10)
    assert len(out) == 1
    assert out[0].title == "T1"
    assert out[0].url == "https://a.com"
    assert out[0].snippet == "Résumé A"
    assert out[0].published_at == "2026-01-01"
    assert out[0].provider == "perplexity"
    get_settings.cache_clear()


def test_perplexity_search_results_sans_snippet_utilise_citation(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "cle-test")
    get_settings.cache_clear()
    captured = {}
    data = {
        "choices": [{"message": {"content":
            "Le marché croît de 10% [1]. Autre phrase sans marqueur."}}],
        "search_results": [{"title": "T1", "url": "https://a.com"}],
    }
    _fake_post_perplexity(monkeypatch, captured, data)
    out = PerplexityProvider().search("q", 10)
    assert out[0].snippet == "Le marché croît de 10% [1]."
    get_settings.cache_clear()


def test_perplexity_search_results_sans_snippet_ni_citation_utilise_titre(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "cle-test")
    get_settings.cache_clear()
    captured = {}
    data = {
        "choices": [{"message": {"content": "Contenu sans marqueur de citation."}}],
        "search_results": [{"title": "T1", "url": "https://a.com"}],
    }
    _fake_post_perplexity(monkeypatch, captured, data)
    out = PerplexityProvider().search("q", 10)
    assert out[0].snippet == "T1"
    get_settings.cache_clear()


def test_perplexity_fallback_citations_sans_search_results(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "cle-test")
    get_settings.cache_clear()
    captured = {}
    data = {
        "choices": [{"message": {"content": "Fait un [1]. Fait deux [2]."}}],
        "citations": ["https://a.com", "https://b.com"],
    }
    _fake_post_perplexity(monkeypatch, captured, data)
    out = PerplexityProvider().search("q", 10)
    assert len(out) == 2
    assert out[0].url == "https://a.com"
    assert out[0].snippet == "Fait un [1]."
    assert out[1].snippet == "Fait deux [2]."
    get_settings.cache_clear()


def test_perplexity_limit_tronque_resultats(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "cle-test")
    get_settings.cache_clear()
    captured = {}
    data = {
        "choices": [{"message": {"content": ""}}],
        "search_results": [{"title": f"T{i}", "url": f"https://ex{i}.com"} for i in range(5)],
    }
    _fake_post_perplexity(monkeypatch, captured, data)
    out = PerplexityProvider().search("q", 2)
    assert len(out) == 2
    get_settings.cache_clear()


def test_perplexity_echec_renvoie_liste_vide(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "cle-test")
    get_settings.cache_clear()

    def _fake_post(url, headers=None, json=None, timeout=None):
        raise RuntimeError("503 Service Unavailable")

    import app.shared.search.providers as P
    monkeypatch.setattr(P.httpx, "post", _fake_post)
    out = PerplexityProvider().search("q", 10)
    assert out == []
    get_settings.cache_clear()


def test_perplexity_sans_cle_renvoie_liste_vide(monkeypatch):
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    get_settings.cache_clear()
    assert PerplexityProvider().search("q", 10) == []
    get_settings.cache_clear()


# --- Cascade à niveaux (orchestrateur) ----------------------------------------

def _cohere_scores_croissants(monkeypatch, seuil_ok=True):
    """Bouchonne Cohere : tous les documents reçoivent un score au-dessus du
    seuil par défaut (0.30), pour simuler « tout est pertinent »."""
    def _fake_post(url, headers=None, json=None, timeout=None):
        docs = json["documents"]
        n = min(json["top_n"], len(docs))
        score = 0.9 if seuil_ok else 0.05

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"results": [{"index": i, "relevance_score": score}
                                     for i in range(n)]}
        return R()
    monkeypatch.setattr(rerank.httpx, "post", _fake_post)


def test_cascade_niveau1_suffit_pas_de_niveau2(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "cle-test")
    monkeypatch.setenv("SEARCH_TIERS", "exa|tavily")
    get_settings.cache_clear()
    _cohere_scores_croissants(monkeypatch, seuil_ok=True)
    exa = _FauxProvider("exa", [_resultats(3)])
    tavily = _FauxProvider("tavily", [_resultats(3)])
    monkeypatch.setattr(orchestrator, "get_provider",
                        lambda n: {"exa": exa, "tavily": tavily}.get(n))
    compteur = {}
    out = orchestrator.search("q", top_k=2, compteur=compteur)
    assert len(out) == 2
    assert compteur["_niveaux"] == 1
    assert len(tavily.appels) == 0
    get_settings.cache_clear()


def test_cascade_niveau2_ajoute_si_niveau1_insuffisant(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "cle-test")
    monkeypatch.setenv("SEARCH_TIERS", "exa|tavily")
    get_settings.cache_clear()
    _cohere_scores_croissants(monkeypatch, seuil_ok=True)
    exa = _FauxProvider("exa", [_resultats(2)])
    tavily_resultats = [SearchResult(title=f"t{i}", url=f"https://tav.com/{i}", snippet="s",
                                     provider="tavily") for i in range(2)]
    tavily = _FauxProvider("tavily", [tavily_resultats])
    monkeypatch.setattr(orchestrator, "get_provider",
                        lambda n: {"exa": exa, "tavily": tavily}.get(n))
    compteur = {}
    out = orchestrator.search("q", top_k=3, compteur=compteur)
    assert compteur["_niveaux"] == 2
    assert len(tavily.appels) == 1
    assert len(out) == 3
    get_settings.cache_clear()


def test_cascade_sans_cohere_arrete_niveau1_si_pool_atteint_top_k(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "")
    monkeypatch.setenv("SEARCH_TIERS", "exa|tavily")
    get_settings.cache_clear()
    exa = _FauxProvider("exa", [_resultats(3)])
    tavily = _FauxProvider("tavily", [_resultats(3)])
    monkeypatch.setattr(orchestrator, "get_provider",
                        lambda n: {"exa": exa, "tavily": tavily}.get(n))
    compteur = {}
    out = orchestrator.search("q", top_k=3, compteur=compteur)
    assert compteur["_niveaux"] == 1
    assert len(tavily.appels) == 0
    assert len(out) == 3
    get_settings.cache_clear()


def test_cascade_sans_cohere_continue_si_pool_insuffisant(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "")
    monkeypatch.setenv("SEARCH_TIERS", "exa|tavily")
    get_settings.cache_clear()
    exa = _FauxProvider("exa", [_resultats(1)])
    tavily_resultats = [SearchResult(title=f"t{i}", url=f"https://tav.com/{i}", snippet="s",
                                     provider="tavily") for i in range(2)]
    tavily = _FauxProvider("tavily", [tavily_resultats])
    monkeypatch.setattr(orchestrator, "get_provider",
                        lambda n: {"exa": exa, "tavily": tavily}.get(n))
    compteur = {}
    out = orchestrator.search("q", top_k=3, compteur=compteur)
    assert compteur["_niveaux"] == 2
    assert len(tavily.appels) == 1
    assert len(out) == 3
    get_settings.cache_clear()


def test_cascade_fournisseur_inconnu_ignore(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "")
    monkeypatch.setenv("SEARCH_TIERS", "exa,fournisseur_fantome|tavily")
    get_settings.cache_clear()
    exa = _FauxProvider("exa", [_resultats(3)])
    monkeypatch.setattr(orchestrator, "get_provider",
                        lambda n: exa if n == "exa" else None)
    compteur = {}
    out = orchestrator.search("q", top_k=3, compteur=compteur)
    assert len(out) == 3
    assert compteur["_niveaux"] == 1
    get_settings.cache_clear()


def test_cascade_niveau_vide_saute(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "")
    monkeypatch.setenv("SEARCH_TIERS", "fournisseur_fantome|exa")
    get_settings.cache_clear()
    exa = _FauxProvider("exa", [_resultats(3)])
    monkeypatch.setattr(orchestrator, "get_provider",
                        lambda n: exa if n == "exa" else None)
    compteur = {}
    out = orchestrator.search("q", top_k=3, compteur=compteur)
    assert len(out) == 3
    # Un seul niveau non vide au total (le premier a été sauté).
    assert compteur["_niveaux"] == 1
    assert len(exa.appels) == 1
    get_settings.cache_clear()


def test_cascade_tous_niveaux_epuises_sans_atteindre_top_k(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "")
    monkeypatch.setenv("SEARCH_TIERS", "exa|tavily")
    get_settings.cache_clear()
    exa = _FauxProvider("exa", [_resultats(1)])
    tavily = _FauxProvider("tavily", [[]])
    monkeypatch.setattr(orchestrator, "get_provider",
                        lambda n: {"exa": exa, "tavily": tavily}.get(n))
    compteur = {}
    out = orchestrator.search("q", top_k=5, compteur=compteur)
    assert compteur["_niveaux"] == 2
    assert len(out) == 1
    get_settings.cache_clear()


def test_cascade_search_multi_interroge_tous_les_angles_par_niveau(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "")
    monkeypatch.setenv("SEARCH_TIERS", "exa|tavily")
    get_settings.cache_clear()
    exa = _FauxProvider("exa", [_resultats(1), _resultats(1)])
    tavily_r1 = [SearchResult(title="tA", url="https://tav.com/a", snippet="s",
                              provider="tavily")]
    tavily_r2 = [SearchResult(title="tB", url="https://tav.com/b", snippet="s",
                              provider="tavily")]
    tavily = _FauxProvider("tavily", [tavily_r1, tavily_r2])
    monkeypatch.setattr(orchestrator, "get_provider",
                        lambda n: {"exa": exa, "tavily": tavily}.get(n))
    compteur = {}
    out = orchestrator.search_multi(["angle1", "angle2"], top_k=3, compteur=compteur)
    assert compteur["_niveaux"] == 2
    # Niveau 1 (exa) interrogé sur les 2 angles, niveau 2 (tavily) aussi.
    assert len(exa.appels) == 2
    assert len(tavily.appels) == 2
    assert len(out) == 3
    get_settings.cache_clear()


# --- Tarif Perplexity (billing) -----------------------------------------------

def test_tiers_tarif_recherche_perplexity(monkeypatch):
    """Le tarif Perplexity vit dans `config.py`
    (`tarif_recherche_perplexity_micro_eur`) et est lu génériquement par
    `couts.cout_recherche_micro_eur`, comme pour exa/tavily/linkup/serper —
    aucun ajout de code n'est nécessaire dans `couts.py` lui-même."""
    from app.modules.billing.couts import cout_recherche_micro_eur
    get_settings.cache_clear()
    assert get_settings().tarif_recherche_perplexity_micro_eur == 5_000
    assert cout_recherche_micro_eur({"perplexity": 2}) == 10_000
    get_settings.cache_clear()


# --- Tour 1 (revue) : pertinents réels (C1), clés de compteur (Q1/Q2) --------

def test_cascade_c1_pertinents_reels_pas_la_garde_minimale(monkeypatch):
    """Revue Task 2, constat C1 : niveau 1 rend 10 sources toutes notées
    0.05, bien sous le seuil (0.30 par défaut). Avant le correctif, la
    condition d'arrêt comptait `len(resultats)` (3, la garde minimale) — ce
    qui arrêtait la cascade alors qu'AUCUNE source n'est réellement
    pertinente. Après correctif (compte des scores ≥ seuil, hors garde), le
    niveau 2 doit être appelé."""
    monkeypatch.setenv("COHERE_API_KEY", "cle-test")
    monkeypatch.setenv("SEARCH_TIERS", "exa|tavily")
    get_settings.cache_clear()
    _cohere_scores_croissants(monkeypatch, seuil_ok=False)  # tout à 0.05
    exa = _FauxProvider("exa", [_resultats(10)])
    tavily_resultats = [SearchResult(title=f"t{i}", url=f"https://tav.com/{i}", snippet="s",
                                     provider="tavily") for i in range(3)]
    tavily = _FauxProvider("tavily", [tavily_resultats])
    monkeypatch.setattr(orchestrator, "get_provider",
                        lambda n: {"exa": exa, "tavily": tavily}.get(n))
    compteur = {}
    orchestrator.search("q", top_k=3, compteur=compteur)
    assert len(tavily.appels) == 1  # niveau 2 appelé malgré 3 résultats rendus au niveau 1
    assert compteur["_niveaux"] == 2
    get_settings.cache_clear()


def test_cascade_search_multi_niveau1_suffit_pas_de_niveau2(monkeypatch):
    """Symétrique de `test_cascade_niveau1_suffit_pas_de_niveau2` pour
    `search_multi` — signalé manquant par la revue."""
    monkeypatch.setenv("COHERE_API_KEY", "cle-test")
    monkeypatch.setenv("SEARCH_TIERS", "exa|tavily")
    get_settings.cache_clear()
    _cohere_scores_croissants(monkeypatch, seuil_ok=True)
    exa = _FauxProvider("exa", [_resultats(3), _resultats(3)])
    tavily = _FauxProvider("tavily", [_resultats(3), _resultats(3)])
    monkeypatch.setattr(orchestrator, "get_provider",
                        lambda n: {"exa": exa, "tavily": tavily}.get(n))
    compteur = {}
    out = orchestrator.search_multi(["angle1", "angle2"], top_k=2, compteur=compteur)
    assert compteur["_niveaux"] == 1
    assert len(tavily.appels) == 0
    assert len(out) == 2
    get_settings.cache_clear()


def test_q1_cle_meta_non_facturee_par_couts(monkeypatch):
    """Revue Task 2, constat Q1 : un compteur `{"exa": 4, "_niveaux": 2,
    "_ecartes": 12}` coûte exactement 4 appels Exa — les clés de métadonnées
    (préfixe `_`) ne sont pas facturées au tarif de repli comme un
    fournisseur inconnu."""
    from app.modules.billing.couts import cout_recherche_micro_eur
    get_settings.cache_clear()
    compteur = {"exa": 4, "_niveaux": 2, "_ecartes": 12}
    attendu = get_settings().tarif_recherche_exa_micro_eur * 4
    assert cout_recherche_micro_eur(compteur) == attendu
    # Non-régression explicite : même montant qu'un compteur sans les clés
    # méta, ce qui est le comportement attendu (elles ne doivent rien changer).
    assert cout_recherche_micro_eur(compteur) == cout_recherche_micro_eur({"exa": 4})
    get_settings.cache_clear()


def test_q1_cle_meta_non_comptee_appels_intelligence():
    """Même correctif côté `intelligence.service._appels` (compteur d'appels
    affiché/persisté par tour de conversation) — grep `compteur` demandé par
    la revue."""
    from app.modules.intelligence.service import _appels
    compteur = {"exa": 4, "_niveaux": 2, "_ecartes": 12}
    assert _appels(compteur) == 4


def test_cascade_q2_ecartes_final_seulement_pas_accumule(monkeypatch):
    """Revue Task 2, constat Q2 : `_ecartes` doit refléter le rerank FINAL
    sur le pool cumulé (niveau 2), pas la somme des écartés de chaque niveau
    (7 au niveau 1 + 3 au niveau 2 ne doit jamais donner 10)."""
    monkeypatch.setenv("COHERE_API_KEY", "cle-test")
    monkeypatch.setenv("SEARCH_TIERS", "exa|tavily")
    get_settings.cache_clear()

    appel = {"n": 0}

    def _fake_post(url, headers=None, json=None, timeout=None):
        appel["n"] += 1
        n = appel["n"]

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                if n == 1:
                    # Niveau 1 : 10 docs, 2 pertinents (rangs 0-1), 7 écartés
                    # (rangs 3-9 ; rangs 0-2 protégés par la garde minimale).
                    scores = [0.9, 0.8] + [0.05] * 8
                else:
                    # Niveau 2 (pool cumulé, rerank final) : 7 pertinents,
                    # 3 écartés (rangs 7-9).
                    scores = [0.9] * 7 + [0.05] * 3
                return {"results": [{"index": i, "relevance_score": s}
                                     for i, s in enumerate(scores)]}
        return R()

    monkeypatch.setattr(rerank.httpx, "post", _fake_post)
    exa = _FauxProvider("exa", [_resultats(10)])
    tavily_resultats = [SearchResult(title=f"t{i}", url=f"https://tav.com/{i}", snippet="s",
                                     provider="tavily") for i in range(10)]
    tavily = _FauxProvider("tavily", [tavily_resultats])
    monkeypatch.setattr(orchestrator, "get_provider",
                        lambda n: {"exa": exa, "tavily": tavily}.get(n))
    compteur = {}
    orchestrator.search("q", top_k=10, compteur=compteur)
    assert compteur["_niveaux"] == 2
    assert compteur["_ecartes"] == 3  # pas 7 + 3 = 10
    get_settings.cache_clear()


def test_rerank_avec_etat_expose_pertinents(monkeypatch):
    """`rerank_avec_etat` doit exposer le nombre de résultats réellement
    pertinents (score ≥ seuil), distinct de `len(résultats rendus)` qui
    inclut la garde minimale même à score nul."""
    monkeypatch.setenv("COHERE_API_KEY", "cle-test")
    get_settings.cache_clear()
    results = _resultats(5)
    scores = [0.9, 0.8, 0.05, 0.05, 0.05]  # 2 pertinents, garde=3 protège l'indice 2

    def _fake_post(url, headers=None, json=None, timeout=None):
        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"results": [{"index": i, "relevance_score": s}
                                     for i, s in enumerate(scores)]}
        return R()

    monkeypatch.setattr(rerank.httpx, "post", _fake_post)
    resultats, reel, pertinents = rerank.rerank_avec_etat("q", results, top_k=5)
    assert reel is True
    assert pertinents == 2
    assert len(resultats) == 3  # garde minimale : 2 pertinents + 1 protégé
    get_settings.cache_clear()


def test_rerank_avec_etat_pertinents_zero_sans_scores_reels(monkeypatch):
    monkeypatch.delenv("COHERE_API_KEY", raising=False)
    get_settings.cache_clear()
    results = _resultats(5)
    resultats, reel, pertinents = rerank.rerank_avec_etat("q", results, top_k=5)
    assert reel is False
    assert pertinents == 0
    get_settings.cache_clear()


# ============================================================
# Task 3 — Pappers et sources par type de rapport
# Voir docs/superpowers/specs/2026-09-14-sources-v2.md §3 et §7.
# ============================================================

from app.modules.analysis import prompts as analysis_prompts
from app.modules.analysis import service as analysis_service
from app.shared.enrich import pappers


# --- sources_de : champ `sources` des directives ----------------------------

def test_sources_directive_toutes_les_cinq_cles():
    for cle in analysis_prompts.ANALYSIS_DIRECTIVES:
        sources = analysis_prompts.sources_de(cle)
        assert set(sources) == {"web", "rag", "notion", "investisseurs", "pappers"}, cle


def test_sources_directive_etude_marche_pappers_true():
    sources = analysis_prompts.sources_de("etude_marche")
    assert sources["pappers"] is True
    assert sources["web"] is True and sources["rag"] is True and sources["notion"] is True
    assert sources["investisseurs"] is False


def test_sources_directive_analyse_concurrentielle_pappers_true():
    sources = analysis_prompts.sources_de("analyse_concurrentielle")
    assert sources["pappers"] is True


def test_sources_directive_cartographie_investisseurs_investisseurs_true():
    sources = analysis_prompts.sources_de("cartographie_investisseurs")
    assert sources["investisseurs"] is True
    assert sources["pappers"] is False


def test_sources_directive_autres_types_pappers_et_investisseurs_false():
    for cle in ("synthese_executive", "veille_technologique",
                "analyse_risques", "analyse_reglementaire"):
        sources = analysis_prompts.sources_de(cle)
        assert sources["pappers"] is False
        assert sources["investisseurs"] is False
        assert sources["web"] is True and sources["rag"] is True and sources["notion"] is True


def test_sources_directive_alias_resolu():
    # `market_study` est un alias legacy de `etude_marche` (_ALIASES) : même
    # champ `sources` que le canonique, pas un défaut générique.
    assert analysis_prompts.sources_de("market_study") == analysis_prompts.sources_de("etude_marche")


def test_sources_directive_type_inconnu_defaut():
    sources = analysis_prompts.sources_de("type_qui_nexiste_pas")
    assert sources == {"web": True, "rag": True, "notion": True,
                       "investisseurs": False, "pappers": False}


def test_sources_directive_prompts_inchanges():
    # Décision explicite : le champ `sources` s'ajoute, il ne touche à aucun
    # autre champ des directives (objectif, angles, instructions, volumes).
    d = analysis_prompts.ANALYSIS_DIRECTIVES["etude_marche"]
    assert d["target_words"] == "8000-10000"
    assert d["min_sources"] == 40
    assert "Chiffrer tout ce qui peut l'être" in d["special_instructions"]


# --- Pappers : disponible() -------------------------------------------------

def test_pappers_disponible_sans_cle(monkeypatch):
    monkeypatch.delenv("PAPPERS_API_KEY", raising=False)
    get_settings.cache_clear()
    assert pappers.disponible() is False
    get_settings.cache_clear()


def test_pappers_disponible_avec_cle(monkeypatch):
    monkeypatch.setenv("PAPPERS_API_KEY", "cle-test")
    get_settings.cache_clear()
    assert pappers.disponible() is True
    get_settings.cache_clear()


# --- Pappers : rechercher() --------------------------------------------------

def test_pappers_rechercher_ok(monkeypatch):
    monkeypatch.setenv("PAPPERS_API_KEY", "cle-test")
    get_settings.cache_clear()
    appels = []

    def _fake_get(url, params=None, timeout=None):
        appels.append((url, params))

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"resultats": [{"siren": "123456789", "nom_entreprise": "Ma Société"}]}
        return R()

    monkeypatch.setattr(pappers.httpx, "get", _fake_get)
    trouve = pappers.rechercher("Ma Société")
    assert trouve == {"siren": "123456789", "nom_entreprise": "Ma Société"}
    assert appels[0][0] == "https://api.pappers.fr/v2/recherche"
    assert appels[0][1] == {"q": "Ma Société", "api_token": "cle-test", "par_page": 5}
    get_settings.cache_clear()


def test_pappers_rechercher_aucun_resultat(monkeypatch):
    monkeypatch.setenv("PAPPERS_API_KEY", "cle-test")
    get_settings.cache_clear()

    def _fake_get(url, params=None, timeout=None):
        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"resultats": []}
        return R()

    monkeypatch.setattr(pappers.httpx, "get", _fake_get)
    assert pappers.rechercher("Société inconnue") is None
    get_settings.cache_clear()


def test_pappers_rechercher_sans_cle_retourne_none(monkeypatch):
    monkeypatch.delenv("PAPPERS_API_KEY", raising=False)
    get_settings.cache_clear()
    assert pappers.rechercher("Ma Société") is None
    get_settings.cache_clear()


def test_pappers_rechercher_echec_httpx_retourne_none_et_alerte(monkeypatch):
    monkeypatch.setenv("PAPPERS_API_KEY", "cle-test")
    get_settings.cache_clear()

    def _fake_get(url, params=None, timeout=None):
        raise RuntimeError("panne réseau")

    monkeypatch.setattr(pappers.httpx, "get", _fake_get)
    alertes = []
    import app.shared.notifier as notifier_mod
    monkeypatch.setattr(notifier_mod, "notifier_fournisseur",
                        lambda **kw: alertes.append(kw))
    assert pappers.rechercher("Ma Société") is None
    assert len(alertes) == 1
    assert alertes[0]["fournisseur"] == "pappers"
    assert alertes[0]["bascule"] is True
    get_settings.cache_clear()


# --- Pappers : fiche() et cache 24h -----------------------------------------

def _fiche_brute():
    return {
        "nom_entreprise": "Ma Société",
        "forme_juridique": "SAS",
        "date_creation": "2019-03-01",
        "code_naf": "62.01Z",
        "libelle_code_naf": "Programmation informatique",
        "effectif": 45,
        "siege": {"ville": "Paris"},
        "finances": [{"annee": 2024, "chiffre_affaires": 3_200_000, "resultat": 400_000}],
        "representants": [{"nom_complet": "Jean Dupont", "qualite": "Président"}],
    }


def test_pappers_fiche_ok(monkeypatch):
    monkeypatch.setenv("PAPPERS_API_KEY", "cle-test")
    get_settings.cache_clear()
    pappers._cache.clear()
    appels = []

    def _fake_get(url, params=None, timeout=None):
        appels.append((url, params))

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return _fiche_brute()
        return R()

    monkeypatch.setattr(pappers.httpx, "get", _fake_get)
    compteur = {}
    data = pappers.fiche("123456789", compteur=compteur)
    assert data["nom_entreprise"] == "Ma Société"
    assert appels[0][0] == "https://api.pappers.fr/v2/entreprise"
    assert appels[0][1] == {"siren": "123456789", "api_token": "cle-test"}
    assert compteur["pappers"] == 1
    get_settings.cache_clear()
    pappers._cache.clear()


def test_pappers_fiche_cache_24h_evite_un_second_appel(monkeypatch):
    monkeypatch.setenv("PAPPERS_API_KEY", "cle-test")
    get_settings.cache_clear()
    pappers._cache.clear()
    appels = []

    def _fake_get(url, params=None, timeout=None):
        appels.append(1)

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return _fiche_brute()
        return R()

    monkeypatch.setattr(pappers.httpx, "get", _fake_get)
    horloge = {"t": 0.0}
    monkeypatch.setattr(pappers, "_horloge", lambda: horloge["t"])

    pappers.fiche("123456789")
    horloge["t"] = 3600.0  # 1h plus tard, toujours dans le cache (< 24h)
    pappers.fiche("123456789")
    assert len(appels) == 1
    get_settings.cache_clear()
    pappers._cache.clear()


def test_pappers_fiche_cache_expire_apres_24h(monkeypatch):
    monkeypatch.setenv("PAPPERS_API_KEY", "cle-test")
    get_settings.cache_clear()
    pappers._cache.clear()
    appels = []

    def _fake_get(url, params=None, timeout=None):
        appels.append(1)

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return _fiche_brute()
        return R()

    monkeypatch.setattr(pappers.httpx, "get", _fake_get)
    horloge = {"t": 0.0}
    monkeypatch.setattr(pappers, "_horloge", lambda: horloge["t"])

    pappers.fiche("123456789")
    horloge["t"] = 24 * 3600.0 + 1.0  # juste après 24h
    pappers.fiche("123456789")
    assert len(appels) == 2
    get_settings.cache_clear()
    pappers._cache.clear()


def test_pappers_fiche_echec_retourne_none_et_alerte(monkeypatch):
    monkeypatch.setenv("PAPPERS_API_KEY", "cle-test")
    get_settings.cache_clear()
    pappers._cache.clear()

    def _fake_get(url, params=None, timeout=None):
        raise RuntimeError("timeout")

    monkeypatch.setattr(pappers.httpx, "get", _fake_get)
    alertes = []
    import app.shared.notifier as notifier_mod
    monkeypatch.setattr(notifier_mod, "notifier_fournisseur",
                        lambda **kw: alertes.append(kw))
    assert pappers.fiche("123456789") is None
    assert len(alertes) == 1
    get_settings.cache_clear()
    pappers._cache.clear()


def test_pappers_fiche_sans_cle_retourne_none(monkeypatch):
    monkeypatch.delenv("PAPPERS_API_KEY", raising=False)
    get_settings.cache_clear()
    pappers._cache.clear()
    assert pappers.fiche("123456789") is None
    get_settings.cache_clear()


# --- Pappers : slug et snippet ----------------------------------------------

def test_pappers_slug_retire_accents_et_ponctuation():
    assert pappers._slug("Café & Cie S.A.S.") == "cafe-cie-s-a-s"


def test_pappers_snippet_phrase_structuree_complete():
    snippet = pappers._snippet(_fiche_brute())
    assert "SAS créée en 2019" in snippet
    assert "NAF 62.01Z" in snippet
    assert "45 salariés" in snippet
    assert "siège à Paris" in snippet
    assert "CA 2024 3,2 M€" in snippet
    assert "résultat 0,4 M€" in snippet
    assert "Jean Dupont (Président)" in snippet


def test_pappers_snippet_champs_absents_omis():
    snippet = pappers._snippet({"forme_juridique": "SAS"})
    assert snippet == "SAS."
    assert "NAF" not in snippet
    assert "CA" not in snippet


# --- Pappers : sources_pappers() --------------------------------------------

def test_pappers_sources_pappers_sans_cle_retourne_vide(monkeypatch):
    monkeypatch.delenv("PAPPERS_API_KEY", raising=False)
    get_settings.cache_clear()
    assert pappers.sources_pappers(["Ma Société"]) == []
    get_settings.cache_clear()


def test_pappers_sources_pappers_url_et_provider(monkeypatch):
    monkeypatch.setenv("PAPPERS_API_KEY", "cle-test")
    get_settings.cache_clear()
    pappers._cache.clear()

    monkeypatch.setattr(pappers, "rechercher",
                        lambda nom, compteur=None: {"siren": "123456789",
                                                     "nom_entreprise": "Ma Société"})
    monkeypatch.setattr(pappers, "fiche",
                        lambda siren, compteur=None: _fiche_brute())

    resultats = pappers.sources_pappers(["Ma Société"])
    assert len(resultats) == 1
    r = resultats[0]
    assert r.provider == "pappers"
    assert r.url == "https://www.pappers.fr/entreprise/ma-societe-123456789"
    assert r.title == "Ma Société"
    assert "SAS créée en 2019" in r.snippet
    get_settings.cache_clear()
    pappers._cache.clear()


def test_pappers_sources_pappers_max_huit(monkeypatch):
    monkeypatch.setenv("PAPPERS_API_KEY", "cle-test")
    get_settings.cache_clear()
    pappers._cache.clear()

    def _rechercher(nom, compteur=None):
        return {"siren": f"{abs(hash(nom)) % 900000000 + 100000000}", "nom_entreprise": nom}

    monkeypatch.setattr(pappers, "rechercher", _rechercher)
    monkeypatch.setattr(pappers, "fiche",
                        lambda siren, compteur=None: {"nom_entreprise": "x"})

    noms = [f"Société {i}" for i in range(12)]
    resultats = pappers.sources_pappers(noms)
    assert len(resultats) == 8
    get_settings.cache_clear()
    pappers._cache.clear()


def test_pappers_sources_pappers_deduplique_insensible_a_la_casse(monkeypatch):
    monkeypatch.setenv("PAPPERS_API_KEY", "cle-test")
    get_settings.cache_clear()
    pappers._cache.clear()
    appels = {"n": 0}

    def _rechercher(nom, compteur=None):
        appels["n"] += 1
        return {"siren": "123456789", "nom_entreprise": "Ma Société"}

    monkeypatch.setattr(pappers, "rechercher", _rechercher)
    monkeypatch.setattr(pappers, "fiche",
                        lambda siren, compteur=None: _fiche_brute())

    pappers.sources_pappers(["Ma Société", "ma société", "MA SOCIÉTÉ"])
    assert appels["n"] == 1
    get_settings.cache_clear()
    pappers._cache.clear()


def test_pappers_sources_pappers_societe_non_trouvee_ignoree(monkeypatch):
    monkeypatch.setenv("PAPPERS_API_KEY", "cle-test")
    get_settings.cache_clear()
    pappers._cache.clear()
    monkeypatch.setattr(pappers, "rechercher", lambda nom, compteur=None: None)
    assert pappers.sources_pappers(["Société inconnue"]) == []
    get_settings.cache_clear()
    pappers._cache.clear()


# --- run_analysis : lecture du champ `sources` ------------------------------

def test_run_analysis_sources_toutes_a_faux_aucun_appel(monkeypatch):
    """Une source à False n'est pas appelée du tout (méthode du brief Task 3)."""
    monkeypatch.setattr(analysis_service.llm_client, "generation_available",
                        lambda: True)
    monkeypatch.setattr(analysis_service, "sources_de",
                        lambda t: {"web": False, "rag": False, "notion": False,
                                   "investisseurs": False, "pappers": False})
    monkeypatch.setattr(analysis_service, "_evaluer_couverture", lambda q, c: "non")

    def _explose(*a, **kw):
        raise AssertionError("ne doit pas être appelé : source désactivée")

    import app.shared.search as web_search_mod
    monkeypatch.setattr(web_search_mod, "search_multi", _explose)
    monkeypatch.setattr(analysis_service, "_retrieve_context", _explose)

    import app.modules.integrations.notion_context as notion_context_mod
    monkeypatch.setattr(notion_context_mod, "passages_pour", _explose)

    import app.modules.investors.service as investors_mod
    monkeypatch.setattr(investors_mod, "map_for_profile", _explose)

    import app.shared.enrich.pappers as pappers_mod
    monkeypatch.setattr(pappers_mod, "disponible", _explose)

    resultat = analysis_service.run_analysis(
        query="analyse marché X", analysis_type="etude_marche",
        user_id="11111111-2222-3333-4444-555555555555",
        db_pour_notion="db-factice",
    )
    assert resultat.degraded is True
    assert resultat.sources == []


def test_run_analysis_sources_web_true_les_autres_faux(monkeypatch):
    """`web=True` seul : search_multi est appelé, RAG/Notion/investisseurs/
    Pappers ne le sont pas."""
    monkeypatch.setattr(analysis_service.llm_client, "generation_available",
                        lambda: True)
    monkeypatch.setattr(analysis_service, "sources_de",
                        lambda t: {"web": True, "rag": False, "notion": False,
                                   "investisseurs": False, "pappers": False})
    monkeypatch.setattr(analysis_service, "_evaluer_couverture", lambda q, c: "non")

    appels = {"search_multi": 0}

    def _fake_search_multi(angles, top_k=None, requete_de_rang=None,
                           contraintes=None, compteur=None):
        appels["search_multi"] += 1
        assert contraintes is not None  # Task 1 : contraintes transmises
        return []

    import app.shared.search as web_search_mod
    monkeypatch.setattr(web_search_mod, "search_multi", _fake_search_multi)

    def _explose(*a, **kw):
        raise AssertionError("ne doit pas être appelé : source désactivée")

    monkeypatch.setattr(analysis_service, "_retrieve_context", _explose)
    import app.modules.investors.service as investors_mod
    monkeypatch.setattr(investors_mod, "map_for_profile", _explose)
    import app.shared.enrich.pappers as pappers_mod
    monkeypatch.setattr(pappers_mod, "disponible", _explose)

    analysis_service.run_analysis(
        query="analyse marché X", analysis_type="etude_marche",
        user_id="11111111-2222-3333-4444-555555555555",
    )
    assert appels["search_multi"] == 1


def test_run_analysis_sources_investisseurs_true_appelle_la_base(monkeypatch):
    monkeypatch.setattr(analysis_service.llm_client, "generation_available",
                        lambda: True)
    monkeypatch.setattr(analysis_service, "sources_de",
                        lambda t: {"web": False, "rag": False, "notion": False,
                                   "investisseurs": True, "pappers": False})

    appels = {"map": 0}

    import app.modules.investors.service as investors_mod

    def _fake_map(profile, **kw):
        appels["map"] += 1
        return {"fonds": []}

    monkeypatch.setattr(investors_mod, "map_for_profile", _fake_map)
    monkeypatch.setattr(investors_mod, "format_context", lambda m: "")
    monkeypatch.setattr(investors_mod, "citations", lambda m: [])

    resultat = analysis_service.run_analysis(
        query="qui pourrait investir", analysis_type="cartographie_investisseurs",
        user_id="11111111-2222-3333-4444-555555555555", profile={},
    )
    assert appels["map"] == 1
    # Sans citations investisseurs, le rapport n'est pas produit (spec) :
    assert resultat.degraded is True
    assert resultat.status_note == "investors_unavailable"


# --- run_analysis : Pappers entre dans le pool AVANT le rerank final --------

def test_run_analysis_pappers_entre_dans_le_pool_avant_rerank(monkeypatch):
    monkeypatch.setattr(analysis_service.llm_client, "generation_available",
                        lambda: True)
    monkeypatch.setattr(analysis_service, "sources_de",
                        lambda t: {"web": True, "rag": False, "notion": False,
                                   "investisseurs": False, "pappers": True})
    monkeypatch.setattr(analysis_service, "_evaluer_couverture", lambda q, c: "non")

    web_resultat = SearchResult(title="Un article", url="https://presse.fr/a",
                                snippet="Un extrait web.", provider="exa")

    import app.shared.search as web_search_mod
    monkeypatch.setattr(web_search_mod, "search_multi",
                        lambda *a, **kw: [web_resultat])

    monkeypatch.setattr(analysis_service, "_noms_de_societes",
                        lambda q, profile, web_results: ["Ma Société"])

    pappers_resultat = SearchResult(
        title="Ma Société", url="https://www.pappers.fr/entreprise/ma-societe-123456789",
        snippet="SAS créée en 2019.", provider="pappers",
    )
    appels_pappers = []

    import app.shared.enrich.pappers as pappers_mod
    monkeypatch.setattr(pappers_mod, "disponible", lambda: True)

    def _fake_sources_pappers(noms, compteur=None):
        appels_pappers.append(noms)
        if compteur is not None:
            compteur["pappers"] = compteur.get("pappers", 0) + 1
        return [pappers_resultat]

    monkeypatch.setattr(pappers_mod, "sources_pappers", _fake_sources_pappers)

    resultat = analysis_service.run_analysis(
        query="étude du marché X", analysis_type="etude_marche",
        user_id="11111111-2222-3333-4444-555555555555",
    )
    assert appels_pappers == [["Ma Société"]]
    urls = [c.get("url") for c in resultat.sources]
    assert any(u and "pappers.fr" in u for u in urls)
    # Les deux pools (web + Pappers) sont présents : le rerank a vu les deux.
    assert any(u == "https://presse.fr/a" for u in urls)


def test_run_analysis_pappers_desactive_pas_dappel(monkeypatch):
    monkeypatch.setattr(analysis_service.llm_client, "generation_available",
                        lambda: True)
    monkeypatch.setattr(analysis_service, "sources_de",
                        lambda t: {"web": False, "rag": False, "notion": False,
                                   "investisseurs": False, "pappers": False})
    monkeypatch.setattr(analysis_service, "_evaluer_couverture", lambda q, c: "non")

    import app.shared.enrich.pappers as pappers_mod

    def _explose():
        raise AssertionError("pappers ne doit pas être consulté")

    monkeypatch.setattr(pappers_mod, "disponible", _explose)

    resultat = analysis_service.run_analysis(
        query="étude du marché X", analysis_type="synthese_executive",
        user_id="11111111-2222-3333-4444-555555555555",
    )
    assert resultat.degraded is True


# ============================================================
# Task 3 — Tour de correction 1 (14/09)
# Secrets masqués, parse des noms LLM, dédup SIREN, compteur par fiche,
# reprise de main (Stop) autour de l'enrichissement Pappers.
# ============================================================

import inspect

from app.shared.secrets import sans_secret


# --- Secrets : masquage partagé ---------------------------------------------

def test_sans_secret_masque_api_token():
    msg = "https://api.pappers.fr/v2/recherche?q=Doctolib&api_token=abc123&par_page=3"
    assert "abc123" not in sans_secret(msg)
    assert "api_token=<masqué>" in sans_secret(msg)


def test_sans_secret_masque_api_key_et_token_generique():
    assert "s3cr3t" not in sans_secret("https://x/y?api_key=s3cr3t")
    assert "s3cr3t" not in sans_secret("https://x/y?token=s3cr3t")
    assert "s3cr3t" not in sans_secret("https://x/y?key=s3cr3t")


def test_llm_client_sans_secret_reste_importable():
    # `app.shared.notifier` importe `_sans_secret` depuis `app.shared.llm_client`
    # (import paresseux) — la fonction doit rester exposée sous ce nom après le
    # déplacement vers `app.shared.secrets`.
    from app.shared.llm_client import _sans_secret

    assert "abc123" not in _sans_secret("https://x/y?api_token=abc123")


def test_pappers_masque_le_jeton_dans_le_journal_recherche(monkeypatch, caplog):
    monkeypatch.setenv("PAPPERS_API_KEY", "cle-test")
    get_settings.cache_clear()

    def _fake_get(url, params=None, timeout=None):
        raise RuntimeError(
            "Client error '401 Unauthorized' for url "
            "'https://api.pappers.fr/v2/recherche?q=Doctolib&api_token=abc123&par_page=3'"
        )

    monkeypatch.setattr(pappers.httpx, "get", _fake_get)
    import app.shared.notifier as notifier_mod
    monkeypatch.setattr(notifier_mod, "notifier_fournisseur", lambda **kw: None)
    with caplog.at_level("WARNING", logger="axial.pappers"):
        assert pappers.rechercher("Doctolib") is None
    assert "abc123" not in caplog.text
    get_settings.cache_clear()


def test_pappers_masque_le_jeton_dans_le_journal_fiche(monkeypatch, caplog):
    monkeypatch.setenv("PAPPERS_API_KEY", "cle-test")
    get_settings.cache_clear()
    pappers._cache.clear()

    def _fake_get(url, params=None, timeout=None):
        raise RuntimeError(
            "Client error '401 Unauthorized' for url "
            "'https://api.pappers.fr/v2/entreprise?siren=123456789&api_token=abc123'"
        )

    monkeypatch.setattr(pappers.httpx, "get", _fake_get)
    import app.shared.notifier as notifier_mod
    monkeypatch.setattr(notifier_mod, "notifier_fournisseur", lambda **kw: None)
    with caplog.at_level("WARNING", logger="axial.pappers"):
        assert pappers.fiche("123456789") is None
    assert "abc123" not in caplog.text
    get_settings.cache_clear()
    pappers._cache.clear()


# --- Parse des noms LLM : _noms_de_societes ---------------------------------

class _ReponseLLM:
    def __init__(self, texte):
        self.text = texte


def test_noms_de_societes_reponse_numerotee(monkeypatch):
    monkeypatch.setattr(analysis_service.llm_client, "generate",
                        lambda **kw: _ReponseLLM("1. Doctolib\n2. Alan\n3. Qonto"))
    noms = analysis_service._noms_de_societes("qui investit dans la santé", None, [])
    assert noms == ["Doctolib", "Alan", "Qonto"]


def test_noms_de_societes_reponse_a_puces(monkeypatch):
    monkeypatch.setattr(analysis_service.llm_client, "generate",
                        lambda **kw: _ReponseLLM("- Doctolib\n• Alan\n* Qonto"))
    noms = analysis_service._noms_de_societes("qui investit dans la santé", None, [])
    assert noms == ["Doctolib", "Alan", "Qonto"]


def test_noms_de_societes_numerotation_parenthese_et_guillemets(monkeypatch):
    monkeypatch.setattr(analysis_service.llm_client, "generate",
                        lambda **kw: _ReponseLLM('1) "Doctolib"\n2) « Alan »'))
    noms = analysis_service._noms_de_societes("qui investit dans la santé", None, [])
    assert noms == ["Doctolib", "Alan"]


def test_noms_de_societes_company_name_en_tete_et_deduplique(monkeypatch):
    monkeypatch.setattr(analysis_service.llm_client, "generate",
                        lambda **kw: _ReponseLLM("1. Doctolib\n2. doctolib\n3. Alan"))
    noms = analysis_service._noms_de_societes(
        "étude du marché", {"company_name": "Doctolib"}, [])
    assert noms == ["Doctolib", "Alan"]


def test_noms_de_societes_llm_echec_replie_sur_company_name(monkeypatch):
    def _explose(**kw):
        raise RuntimeError("panne")

    monkeypatch.setattr(analysis_service.llm_client, "generate", _explose)
    noms = analysis_service._noms_de_societes(
        "étude du marché", {"company_name": "Doctolib"}, [])
    assert noms == ["Doctolib"]


def test_noms_de_societes_llm_echec_et_profil_vide_retourne_liste_vide(monkeypatch):
    def _explose(**kw):
        raise RuntimeError("panne")

    monkeypatch.setattr(analysis_service.llm_client, "generate", _explose)
    assert analysis_service._noms_de_societes("étude du marché", None, []) == []
    assert analysis_service._noms_de_societes("étude du marché", {}, []) == []


def test_noms_de_societes_plafond_huit(monkeypatch):
    lignes = "\n".join(f"{i}. Société {i}" for i in range(1, 15))
    monkeypatch.setattr(analysis_service.llm_client, "generate",
                        lambda **kw: _ReponseLLM(lignes))
    noms = analysis_service._noms_de_societes("étude du marché", None, [])
    assert len(noms) == 8
    assert noms[0] == "Société 1"


def test_noms_de_societes_ignore_lignes_vides_et_trop_longues(monkeypatch):
    ligne_longue = "Une raison sociale improbablement longue " * 3  # > 80 caractères
    texte = f"1. Doctolib\n\n2. {ligne_longue}\n3. Alan"
    monkeypatch.setattr(analysis_service.llm_client, "generate",
                        lambda **kw: _ReponseLLM(texte))
    noms = analysis_service._noms_de_societes("étude du marché", None, [])
    assert noms == ["Doctolib", "Alan"]


def test_nettoyer_nom_societe_ignore_phrase_damorce():
    assert analysis_service._nettoyer_nom_societe("Voici les entreprises mentionnées :") is None


def test_nettoyer_nom_societe_retire_guillemets_et_numerotation():
    assert analysis_service._nettoyer_nom_societe('1. "Doctolib"') == "Doctolib"
    assert analysis_service._nettoyer_nom_societe("2) « Alan »") == "Alan"
    assert analysis_service._nettoyer_nom_societe("- Qonto") == "Qonto"


# --- Pappers : compteur par fiche, pas par recherche ------------------------

def test_pappers_rechercher_naccepte_plus_de_compteur():
    assert "compteur" not in inspect.signature(pappers.rechercher).parameters


def test_pappers_sources_pappers_compteur_egal_au_nombre_de_fiches(monkeypatch):
    monkeypatch.setenv("PAPPERS_API_KEY", "cle-test")
    get_settings.cache_clear()
    pappers._cache.clear()

    sirens = {"Société A": "111111111", "Société B": "222222222"}
    monkeypatch.setattr(pappers, "rechercher",
                        lambda nom: {"siren": sirens[nom], "nom_entreprise": nom})

    def _fake_get(url, params=None, timeout=None):
        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"nom_entreprise": "x"}
        return R()

    monkeypatch.setattr(pappers.httpx, "get", _fake_get)

    compteur = {}
    resultats = pappers.sources_pappers(["Société A", "Société B"], compteur=compteur)
    assert len(resultats) == 2
    assert compteur["pappers"] == 2  # une fiche par société, la recherche n'est pas comptée
    get_settings.cache_clear()
    pappers._cache.clear()


# --- Pappers : dédup par SIREN -----------------------------------------------

def test_pappers_sources_pappers_deduplique_par_siren(monkeypatch):
    monkeypatch.setenv("PAPPERS_API_KEY", "cle-test")
    get_settings.cache_clear()
    pappers._cache.clear()

    # Deux noms distincts, mais le même SIREN (le LLM a listé le nom usuel et
    # la raison sociale complète).
    monkeypatch.setattr(pappers, "rechercher",
                        lambda nom: {"siren": "123456789", "nom_entreprise": "Doctolib"})
    appels_fiche = {"n": 0}

    def _fiche(siren, compteur=None):
        appels_fiche["n"] += 1
        if compteur is not None:
            compteur["pappers"] = compteur.get("pappers", 0) + 1
        return _fiche_brute()

    monkeypatch.setattr(pappers, "fiche", _fiche)

    compteur = {}
    resultats = pappers.sources_pappers(["Doctolib", "Doctolib SAS"], compteur=compteur)
    assert len(resultats) == 1
    assert appels_fiche["n"] == 1
    assert compteur["pappers"] == 1
    get_settings.cache_clear()
    pappers._cache.clear()


# --- run_analysis : Stop autour de l'enrichissement Pappers -----------------

class _SuiviFactice:
    def __init__(self):
        self.appels = []

    def verifier(self):
        self.appels.append("verifier")

    def etape(self, nom, progression, **detail):
        self.appels.append(("etape", nom, progression))


def test_run_analysis_suivi_verifie_avant_et_apres_pappers(monkeypatch):
    monkeypatch.setattr(analysis_service.llm_client, "generation_available",
                        lambda: True)
    monkeypatch.setattr(analysis_service, "sources_de",
                        lambda t: {"web": True, "rag": False, "notion": False,
                                   "investisseurs": False, "pappers": True})
    monkeypatch.setattr(analysis_service, "_evaluer_couverture", lambda q, c: "non")

    import app.shared.search as web_search_mod
    monkeypatch.setattr(web_search_mod, "search_multi", lambda *a, **kw: [])

    import app.shared.enrich.pappers as pappers_mod
    monkeypatch.setattr(pappers_mod, "disponible", lambda: True)
    monkeypatch.setattr(pappers_mod, "sources_pappers", lambda noms, compteur=None: [])
    monkeypatch.setattr(analysis_service, "_noms_de_societes", lambda q, p, w: [])

    suivi = _SuiviFactice()
    analysis_service.run_analysis(
        query="étude du marché X", analysis_type="etude_marche",
        user_id="11111111-2222-3333-4444-555555555555", suivi=suivi,
    )
    idx = suivi.appels.index(("etape", "recherche", 22))
    assert suivi.appels[idx - 1] == "verifier"
    assert suivi.appels[idx + 1] == "verifier"


def test_run_analysis_pappers_desactive_aucun_appel_de_suivi_dedie(monkeypatch):
    """Sans Pappers actif, pas d'étape « recherche/22 » (celle du bloc 1bis)."""
    monkeypatch.setattr(analysis_service.llm_client, "generation_available",
                        lambda: True)
    monkeypatch.setattr(analysis_service, "sources_de",
                        lambda t: {"web": True, "rag": False, "notion": False,
                                   "investisseurs": False, "pappers": False})
    monkeypatch.setattr(analysis_service, "_evaluer_couverture", lambda q, c: "non")

    import app.shared.search as web_search_mod
    monkeypatch.setattr(web_search_mod, "search_multi", lambda *a, **kw: [])

    suivi = _SuiviFactice()
    analysis_service.run_analysis(
        query="synthèse X", analysis_type="synthese_executive",
        user_id="11111111-2222-3333-4444-555555555555", suivi=suivi,
    )
    assert ("etape", "recherche", 22) not in suivi.appels


# ============================================================
# Task 4 — Base investisseurs en conversation, étiquette Pappers dans
# `grounding`, fournisseurs réellement annoncés. Spec §4.
# ============================================================

import uuid as _uuidlib

from sqlalchemy import create_engine as _create_engine
from sqlalchemy.orm import Session as _Session

from app.modules.investors import service as investors_service


# --- question_de_levee : regex FR/EN, fonction pure -------------------------

@pytest.mark.parametrize("texte", [
    "Comment lever des fonds pour ma startup ?",
    "On prépare notre levée de série A",
    "Quels investisseurs cibler en seed ?",
    "On cherche un fonds VC generaliste",
    "Qui contacter côté business angels ?",
    # `financement` seulement en combinaison (review Q-1, décision Tour 1) —
    # exactement les deux formes citées par le contrôleur.
    "Le financement de la startup est notre priorité",
    "On discute du financement par des fonds étrangers",
    "What's a fair valuation for our term sheet?",
    "We are fundraising a Series B round",
    "Looking for venture investors",
    "On doit émettre des BSA pour ce tour",
    "How to structure our seed round?",
    # Faux négatifs testés explicitement par le contrôleur (Tour 1).
    "comment lever 2 M€ en seed ?",
    "quels VC cibler ?",
    "préparer notre série A",
    "how much to raise for a Series A",
    # `ticket`/`valorisation` seulement en forme composée, jamais nus.
    "Quel est le bon ticket d'investissement pour ce tour ?",
    "On vise une valorisation post-money de 20M",
])
def test_levee_detecte_les_formulations_fr_en(texte):
    assert investors_service.question_de_levee(texte) is True


@pytest.mark.parametrize("texte", [
    "Quelle est la météo à Paris demain ?",
    "Peux-tu résumer ce document ?",
    "Comment améliorer notre taux de conversion produit ?",
    "",
    None,
    # Tour de correction 1 (review Q-1) : faux positifs constatés sur la
    # première version, vocabulaire courant sans rapport avec le financement.
    "Notre marge est élevée sur ce segment",
    "Comment relever ce défi organisationnel ?",
    "Des changements profonds dans notre organisation",
    "Nous voulons céder un fonds de commerce",
    "Quel est notre ticket moyen sur le e-commerce ?",
    "Améliorer la valorisation de notre marque employeur ?",
    "Peut-on prélever un échantillon ?",
    "Faut-il enlever cette fonctionnalité ?",
])
def test_levee_ignore_les_questions_hors_sujet(texte):
    assert investors_service.question_de_levee(texte) is False


def test_levee_insensible_a_la_casse():
    assert investors_service.question_de_levee("ON VEUT LEVER DES FONDS") is True


# --- grounding.assemble : étiquette Pappers ---------------------------------

def test_grounding_pappers_etiquette_le_registre():
    from app.shared import grounding

    pappers_result = SearchResult(
        title="ACME SAS", url="https://www.pappers.fr/entreprise/acme-123456789",
        snippet="SAS créée en 2019, NAF 62.01Z, 12 salariés.", provider="pappers")
    context, citations = grounding.assemble("ACME", [pappers_result], [], top_k=5)
    assert "(registre : pappers.fr)" in context
    assert citations[0]["source"] == "pappers"


def test_grounding_pappers_laisse_le_web_normal_intact():
    from app.shared import grounding

    web_result = SearchResult(title="Article marché", url="https://lesechos.fr/x",
                              snippet="Analyse du marché.", provider="exa")
    context, citations = grounding.assemble("marché", [web_result], [], top_k=5)
    assert "(web : lesechos.fr)" in context
    assert citations[0]["source"] == "web"


def test_grounding_pappers_et_web_coexistent_dans_le_meme_pool():
    from app.shared import grounding

    web_result = SearchResult(title="Article marché", url="https://lesechos.fr/x",
                              snippet="Analyse du marché.", provider="exa")
    pappers_result = SearchResult(
        title="ACME SAS", url="https://www.pappers.fr/entreprise/acme-123456789",
        snippet="SAS créée en 2019.", provider="pappers")
    context, citations = grounding.assemble("ACME marché", [web_result, pappers_result], [],
                                            top_k=5)
    sources = {c["source"] for c in citations}
    assert sources == {"web", "pappers"}


# --- _fournisseurs_recherche : fournisseurs réellement disponibles ---------

def test_fournisseurs_annonces_aplati_dans_l_ordre_des_niveaux(monkeypatch):
    from app.modules.intelligence import service as intel

    monkeypatch.setenv("SEARCH_TIERS", "perplexity,exa|tavily,linkup")
    get_settings.cache_clear()

    class _P:
        def __init__(self, ok):
            self._ok = ok

        def available(self):
            return self._ok

    dispo = {"perplexity": True, "exa": False, "tavily": True, "linkup": True}
    monkeypatch.setattr("app.shared.search.providers.get_provider",
                        lambda n: _P(dispo.get(n, False)))
    assert intel._fournisseurs_recherche() == ["perplexity", "tavily", "linkup"]
    get_settings.cache_clear()


def test_fournisseurs_annonces_deduplique(monkeypatch):
    from app.modules.intelligence import service as intel

    # Un même fournisseur listé dans deux niveaux ne doit apparaître qu'une fois.
    monkeypatch.setenv("SEARCH_TIERS", "exa,tavily|exa,linkup")
    get_settings.cache_clear()

    class _P:
        def available(self):
            return True

    monkeypatch.setattr("app.shared.search.providers.get_provider",
                        lambda n: _P())
    assert intel._fournisseurs_recherche() == ["exa", "tavily", "linkup"]
    get_settings.cache_clear()


def test_fournisseurs_annonces_ignore_les_non_configures(monkeypatch):
    from app.modules.intelligence import service as intel

    monkeypatch.setenv("SEARCH_TIERS", "perplexity,exa|tavily,linkup")
    get_settings.cache_clear()

    def _get_provider(n):
        if n in ("perplexity", "linkup"):
            return None  # pas de clé configurée
        class _P:
            def available(self):
                return True
        return _P()

    monkeypatch.setattr("app.shared.search.providers.get_provider", _get_provider)
    assert intel._fournisseurs_recherche() == ["exa", "tavily"]
    get_settings.cache_clear()


# --- Base investisseurs en conversation (_rechercher) -----------------------

def _base_profils():
    import app.modules.memory.models  # noqa: F401 — company_profiles

    engine = _create_engine("sqlite://", future=True)
    from app.db import Base as _Base

    _Base.metadata.create_all(engine, tables=[
        _Base.metadata.tables["company_profiles"],
    ])
    return engine


def _profil(db, *, sector=None, funding_stage=None):
    from app.modules.memory.models import CompanyProfile

    uid = str(_uuidlib.uuid4())
    profil = CompanyProfile(user_id=_uuidlib.UUID(uid), company_name="ACME",
                            sector=sector, funding_stage=funding_stage)
    db.add(profil)
    db.commit()
    return uid


class _ConvFactice:
    """Objet minimal portant `.title` — tout ce que `requete_de_recherche` lit
    sur `ctx.conv`."""
    def __init__(self, title):
        self.title = title


def _ctx_conversation(*, user_id: str, trivial: bool = False, titre: str | None = None,
                      history=None):
    from app.modules.intelligence import service as intel

    return intel._Contexte(conv=_ConvFactice(titre), agent_key="axial_conseil",
                           redirect_note=None, persona=None, conversation_libre=True,
                           company_context="", attached_context="",
                           history=history or [], trivial=trivial,
                           user_id=user_id, conv_id=None, user_msg_id=None)


def _neutraliser_reseau(monkeypatch, *, web_results=None, doc_passages=None):
    from app.modules.integrations import notion_context
    from app.modules.intelligence import service as intel
    from app.shared import search as web_search

    appels_web: list[dict] = []

    def _search(query, top_k=6, contraintes=None, compteur=None):
        appels_web.append({"query": query, "contraintes": contraintes})
        return list(web_results or [])

    monkeypatch.setattr(web_search, "search", _search)
    monkeypatch.setattr(intel, "_retrieve_context",
                        lambda *a, **k: ("", list(doc_passages or [])))
    monkeypatch.setattr(notion_context, "passages_pour", lambda *a, **k: [])
    return appels_web


def test_conversation_investisseurs_numerotees_en_tete(monkeypatch):
    """Spec §4 : la base investisseurs, quand elle répond, occupe les premiers
    numéros — le web reprend la numérotation après elle (comme le rapport de
    cartographie investisseurs)."""
    from app.modules.intelligence import service as intel

    engine = _base_profils()
    with _Session(engine) as db:
        uid = _profil(db, sector="Fintech", funding_stage="Seed")

        web = [SearchResult(title="Actu marché", url="https://lesechos.fr/z",
                            snippet="Contexte marché.", provider="exa")]
        appels_web = _neutraliser_reseau(monkeypatch, web_results=web)

        mapping = {"funds": [{"nom": "Fonds Alpha", "site_web": "https://alpha.vc",
                              "score": 0.9, "n_vehicules": 2, "zone": "France",
                              "secteurs": ["Fintech"], "stades": ["Seed"]}],
                  "networks": [], "note": None}
        appels_mapping: list[dict] = []

        def _map(profile, *, limit):
            appels_mapping.append({"profile": profile, "limit": limit})
            return mapping

        monkeypatch.setattr(investors_service, "map_for_profile", _map)

        ctx = _ctx_conversation(user_id=uid)
        rech = intel._rechercher(db, uid, "Comment lever des fonds en seed ?", ctx)

    assert appels_mapping and appels_mapping[0]["limit"] == 10
    assert appels_web  # la recherche web tourne EN PARALLÈLE, pas à la place
    assert rech.citations[0]["source"] == "investisseurs"
    assert rech.citations[0]["title"] == "Fonds Alpha"
    assert rech.citations[1]["source"] == "web"
    assert rech.combined_context.index("[1]") < rech.combined_context.index("[2]")
    assert "Fonds Alpha" in rech.combined_context.split("[2]")[0]


def test_conversation_investisseurs_numerotation_ne_decale_pas_off_by_one(monkeypatch):
    """Tour de correction 1 (review Q-3) : le cas à une seule citation
    investisseur ne peut pas attraper un off-by-one (`len(...)` vs
    `len(...)+1`, ou un oubli des `networks`). Ici : 3 fonds + 2 réseaux (5
    citations investisseurs) + 2 web + 1 RAG (3 citations restantes) = 8 au
    total. `[6]` doit être la PREMIÈRE source non-investisseur, et
    `citations[5]` (index 5, la 6ᵉ) doit lui correspondre."""
    from app.modules.rag.vector_store import Passage
    from app.modules.intelligence import service as intel

    engine = _base_profils()
    with _Session(engine) as db:
        uid = _profil(db, sector="Fintech", funding_stage="Seed")

        web = [
            SearchResult(title="Article marché A", url="https://a.fr/x",
                        snippet="Contexte marché A.", provider="exa"),
            SearchResult(title="Article marché B", url="https://b.fr/y",
                        snippet="Contexte marché B.", provider="exa"),
        ]
        rag = [Passage(text="Note interne financement", score=0.9, doc_id="d1",
                       source="user", meta={"filename": "note.pdf"})]
        _neutraliser_reseau(monkeypatch, web_results=web, doc_passages=rag)

        mapping = {
            "funds": [
                {"nom": f"Fonds {n}", "site_web": f"https://{n.lower()}.vc",
                 "score": 0.9, "n_vehicules": 1, "zone": "France",
                 "secteurs": ["Fintech"], "stades": ["Seed"]}
                for n in ("Alpha", "Beta", "Gamma")
            ],
            "networks": [
                {"nom": f"Réseau {n}", "nature": "business angels", "score": 0.8,
                 "secteurs": ["Fintech"], "stades": ["Seed"]}
                for n in ("Un", "Deux")
            ],
            "note": None,
        }
        monkeypatch.setattr(investors_service, "map_for_profile",
                            lambda *a, **k: mapping)

        ctx = _ctx_conversation(user_id=uid)
        rech = intel._rechercher(db, uid, "Comment lever des fonds en seed ?", ctx)

    assert len(rech.citations) == 8
    # [1]..[5] = investisseurs (3 fonds + 2 réseaux), dans l'ordre du mapping.
    for i, titre in enumerate(["Fonds Alpha", "Fonds Beta", "Fonds Gamma",
                               "Réseau Un", "Réseau Deux"]):
        assert rech.citations[i]["source"] == "investisseurs"
        assert rech.citations[i]["title"] == titre
    # [6] = la PREMIÈRE source non-investisseur — citations[5], index 5.
    assert rech.citations[5]["source"] != "investisseurs"
    assert rech.citations[6]["source"] != "investisseurs"
    assert rech.citations[7]["source"] != "investisseurs"
    # Numérotation strictement continue 1..8 dans le contexte, sans trou ni
    # doublon — le seul test qui verrouille réellement le contrat de la spec §4.
    numeros = re.findall(r"^\[(\d+)\]", rech.combined_context, re.M)
    assert numeros == [str(n) for n in range(1, 9)]
    # Le bloc « [6] » (première source web) suit immédiatement le dernier
    # bloc investisseur : aucun numéro investisseur ne réapparaît après lui.
    bloc_apres_investisseurs = rech.combined_context.split("[6]", 1)[1]
    assert "Fonds" not in bloc_apres_investisseurs
    assert "Réseau" not in bloc_apres_investisseurs


def test_conversation_investisseurs_propage_les_contraintes(monkeypatch):
    """`_rechercher` passe `contraintes_pour(question, None)` à `web_search.search`
    (spec §1) — pas de filtre de type de rapport, seulement les mots de la
    question."""
    from app.modules.intelligence import service as intel
    from app.shared.search.contraintes import Contraintes

    engine = _base_profils()
    with _Session(engine) as db:
        uid = _profil(db, sector=None, funding_stage=None)
        appels_web = _neutraliser_reseau(monkeypatch)
        ctx = _ctx_conversation(user_id=uid)
        intel._rechercher(db, uid, "Actualité réglementaire RGPD cette semaine", ctx)

    assert len(appels_web) == 1
    c = appels_web[0]["contraintes"]
    assert isinstance(c, Contraintes)
    # « RGPD » + « cette semaine » : la règle la plus restrictive gagne (90 j).
    assert c.fraicheur_jours == 90


def test_conversation_investisseurs_contraintes_sur_la_question_brute(monkeypatch):
    """Tour de correction 1 (review Q-5) : les contraintes viennent de
    `content` (la question BRUTE de ce tour), pas de `requete` (préfixée du
    titre du fil dès le deuxième message) — sinon un fil intitulé « Actualité
    réglementaire RGPD » imposerait sa fraîcheur de 90 j à toutes les
    questions suivantes, même sans rapport."""
    from app.modules.intelligence import service as intel
    from app.shared.search.contraintes import Contraintes

    engine = _base_profils()
    with _Session(engine) as db:
        uid = _profil(db, sector=None, funding_stage=None)
        appels_web = _neutraliser_reseau(monkeypatch)
        # Fil avec historique (`requete` sera préfixée du titre) et une
        # question SUIVANTE sans rapport avec l'actualité/la réglementation.
        ctx = _ctx_conversation(user_id=uid, titre="Actualité réglementaire RGPD",
                                history=[{"role": "user", "content": "1ère question"}])
        intel._rechercher(db, uid, "Comment structurer notre équipe ?", ctx)

    assert len(appels_web) == 1
    # La requête envoyée au web PORTE le titre (comportement inchangé)…
    assert "Actualité réglementaire RGPD" in appels_web[0]["query"]
    # … mais les CONTRAINTES ne doivent pas hériter de sa fraîcheur : la
    # question de ce tour, seule, ne contient aucun mot déclencheur.
    c = appels_web[0]["contraintes"]
    assert isinstance(c, Contraintes)
    assert c.fraicheur_jours is None


def test_conversation_investisseurs_ignoree_si_pas_de_levee(monkeypatch):
    """Une question sans rapport avec le financement ne déclenche jamais la
    base investisseurs, même avec un profil complet."""
    from app.modules.intelligence import service as intel

    engine = _base_profils()
    with _Session(engine) as db:
        uid = _profil(db, sector="Fintech", funding_stage="Seed")
        _neutraliser_reseau(monkeypatch)

        appele = []
        monkeypatch.setattr(investors_service, "map_for_profile",
                            lambda *a, **k: appele.append(1) or {})

        ctx = _ctx_conversation(user_id=uid)
        rech = intel._rechercher(db, uid, "Comment améliorer notre roadmap produit ?", ctx)

    assert not appele
    assert not any(c.get("source") == "investisseurs" for c in rech.citations)


def test_conversation_investisseurs_ignoree_si_profil_incomplet(monkeypatch):
    """Question de levée mais profil sans secteur ni stade : `map_for_profile`
    ne serait qu'une note d'échec, on ne l'appelle pas (spec §4)."""
    from app.modules.intelligence import service as intel

    engine = _base_profils()
    with _Session(engine) as db:
        uid = _profil(db, sector=None, funding_stage=None)
        _neutraliser_reseau(monkeypatch)

        appele = []
        monkeypatch.setattr(investors_service, "map_for_profile",
                            lambda *a, **k: appele.append(1) or {})

        ctx = _ctx_conversation(user_id=uid)
        rech = intel._rechercher(db, uid, "On veut lever des fonds", ctx)

    assert not appele
    assert not any(c.get("source") == "investisseurs" for c in rech.citations)


def test_conversation_investisseurs_echec_silencieux(monkeypatch, caplog):
    """`map_for_profile` qui explose ne bloque jamais la réponse — journal
    seulement, jamais d'erreur utilisateur (spec §4)."""
    from app.modules.intelligence import service as intel

    engine = _base_profils()
    with _Session(engine) as db:
        uid = _profil(db, sector="Fintech", funding_stage="Seed")
        _neutraliser_reseau(monkeypatch)

        def _boom(*a, **k):
            raise RuntimeError("base investisseurs indisponible")

        monkeypatch.setattr(investors_service, "map_for_profile", _boom)

        ctx = _ctx_conversation(user_id=uid)
        with caplog.at_level("WARNING", logger="axial.intelligence"):
            rech = intel._rechercher(db, uid, "On veut lever des fonds en seed", ctx)

    assert not any(c.get("source") == "investisseurs" for c in rech.citations)
    # Assertion stricte (review Q-9) : le logger ET le message précis, pas une
    # disjonction sur un mot qui apparaît dans d'autres avertissements du module.
    messages = [r.getMessage() for r in caplog.records if r.name == "axial.intelligence"]
    assert any("Base investisseurs indisponible en conversation" in m and
              "base investisseurs indisponible" in m  # le texte de l'exception
              for m in messages), messages


def test_conversation_investisseurs_delai_depasse_reste_silencieux(monkeypatch, caplog):
    """Tour de correction 1 (review Q-2) : `map_for_profile` qui dépasse le
    délai (plusieurs allers-retours LLM possibles) ne bloque pas le tour —
    `f_inv.result(timeout=...)` abandonne, journal seulement, pas
    d'investisseurs. Le délai est raccourci ici pour ne pas ralentir la suite."""
    import time as _time

    from app.modules.intelligence import service as intel

    monkeypatch.setattr(intel, "TIMEOUT_INVESTISSEURS_CONVERSATION_S", 0.05)

    engine = _base_profils()
    with _Session(engine) as db:
        uid = _profil(db, sector="Fintech", funding_stage="Seed")
        _neutraliser_reseau(monkeypatch)

        def _lent(profile, *, limit):
            _time.sleep(0.3)  # dépasse largement le délai raccourci
            return {"funds": [], "networks": [], "note": None}

        monkeypatch.setattr(investors_service, "map_for_profile", _lent)

        ctx = _ctx_conversation(user_id=uid)
        debut = _time.monotonic()
        with caplog.at_level("WARNING", logger="axial.intelligence"):
            rech = intel._rechercher(db, uid, "On veut lever des fonds en seed", ctx)
        duree = _time.monotonic() - debut

    # Le tour n'attend PAS la fin de `map_for_profile` (pas de `with` qui
    # `shutdown(wait=True)` sur le thread encore en cours) : nettement sous
    # les 0.3 s que le mapping simulé met à répondre.
    assert duree < 0.25
    assert not any(c.get("source") == "investisseurs" for c in rech.citations)
    messages = [r.getMessage() for r in caplog.records if r.name == "axial.intelligence"]
    assert any("délai" in m and "dépassé" in m for m in messages), messages


def test_conversation_investisseurs_mapping_vide_reste_silencieux(monkeypatch):
    """Mapping renvoyé mais sans fonds ni réseaux (secteur non couvert) : rien
    n'est ajouté au contexte, pas d'entrée factice."""
    from app.modules.intelligence import service as intel

    engine = _base_profils()
    with _Session(engine) as db:
        uid = _profil(db, sector="Fintech", funding_stage="Seed")
        _neutraliser_reseau(monkeypatch)

        monkeypatch.setattr(investors_service, "map_for_profile",
                            lambda *a, **k: {"funds": [], "networks": [],
                                             "note": "aucun investisseur couvrant ce secteur"})

        ctx = _ctx_conversation(user_id=uid)
        rech = intel._rechercher(db, uid, "On veut lever des fonds en seed", ctx)

    assert not any(c.get("source") == "investisseurs" for c in rech.citations)


def test_conversation_investisseurs_pas_de_recherche_si_message_trivial(monkeypatch):
    """Message trivial (« merci ») : ni web, ni RAG, ni base investisseurs."""
    from app.modules.intelligence import service as intel

    engine = _base_profils()
    with _Session(engine) as db:
        uid = _profil(db, sector="Fintech", funding_stage="Seed")
        _neutraliser_reseau(monkeypatch)

        appele = []
        monkeypatch.setattr(investors_service, "map_for_profile",
                            lambda *a, **k: appele.append(1) or {})

        ctx = _ctx_conversation(user_id=uid, trivial=True)
        rech = intel._rechercher(db, uid, "merci", ctx)

    assert not appele
    assert rech.citations == []


# ===========================================================================
# Task 5 — base de connaissance Axial (app/modules/kb/)
# ===========================================================================
#
# `embed_texts` est bouchonné (vecteurs factices de la bonne dimension) :
# aucun test d'ingestion n'appelle Cohere. Qdrant tourne en mémoire
# (`QDRANT_URL=:memory:`, voir `.env` — même fixture que le reste de la
# suite) ; le client est mis en cache par processus (`vector_store._client`
# est `@lru_cache`), donc la collection `knowledge_base` est PARTAGÉE entre
# tous les tests de ce fichier : chaque test choisit un nom/URL unique
# (uuid4) pour ne jamais collisionner avec un autre test sur `doc_id`.

import io as _io_kb


@pytest.fixture(autouse=True)
def _kb_cache_propre():
    """Le cache du scroll Qdrant (10 min, spec §5) est un dict de module —
    partagé entre tests s'il n'est pas remis à zéro."""
    from app.modules.kb import service as kb_service

    kb_service._scroll_cache["docs"] = None
    kb_service._scroll_cache["at"] = 0.0
    yield
    kb_service._scroll_cache["docs"] = None
    kb_service._scroll_cache["at"] = 0.0


def _kb_engine():
    import app.modules.kb.models  # noqa: F401 — enregistre `kb_documents`
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    from app.db import Base as _Base

    engine = create_engine("sqlite://", future=True,
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    _Base.metadata.create_all(engine, tables=[_Base.metadata.tables["kb_documents"]])
    return engine


def _kb_stub_embeddings(monkeypatch):
    """Vecteurs factices, tous identiques : suffisant pour que la recherche
    par similarité retrouve n'importe quel chunk indexé par ces tests."""
    from app.modules.rag import embeddings as _emb

    monkeypatch.setattr(
        _emb, "embed_texts",
        lambda textes, **kw: [[0.01] * _emb.embedding_dim() for _ in textes],
    )


def _kb_nom(prefixe: str) -> str:
    """Nom de fichier/URL unique par test — `doc_id` en dérive (uuid5)."""
    import uuid as _uuid

    return f"{prefixe}-{_uuid.uuid4().hex}.txt"


def _kb_texte(mots: int = 400) -> str:
    return " ".join(f"mot{i}" for i in range(mots))


# --- table, routes montées --------------------------------------------------

def test_kb_table_colonnes_presentes():
    import app.modules.kb.models  # noqa: F401

    from app.db import Base as _Base

    cols = _Base.metadata.tables["kb_documents"].c
    for nom in ("id", "doc_id", "titre", "source", "type", "categorie",
                "mime_type", "nb_chunks", "taille_octets", "cree_par",
                "created_at", "statut", "erreur"):
        assert nom in cols, f"kb_documents.{nom} manquant"
    assert not cols["doc_id"].nullable
    assert not cols["titre"].nullable
    assert not cols["statut"].nullable


def test_kb_routes_montees_et_reservees_admin():
    from fastapi.testclient import TestClient

    from app.main import app as _app

    client = TestClient(_app)
    chemins = client.get("/openapi.json").json()["paths"]
    assert "/admin/kb" in chemins
    assert "/admin/kb/fichiers" in chemins
    assert "/admin/kb/urls" in chemins
    assert "/admin/kb/{doc_id}" in chemins
    # Sans jeton : 401/403, jamais un 200 qui exposerait la base.
    assert client.get("/admin/kb").status_code in (401, 403)
    assert client.delete("/admin/kb/x").status_code in (401, 403)


# --- ingerer_fichier ---------------------------------------------------------

def test_kb_ingerer_fichier_ok(monkeypatch):
    from app.modules.kb import service as kb

    _kb_stub_embeddings(monkeypatch)
    engine = _kb_engine()
    nom = _kb_nom("rapport")
    with Session(engine) as db:
        ligne = kb.ingerer_fichier(db, str(uuid.uuid4()), nom,
                                   _kb_texte().encode("utf-8"), "text/plain")
        assert ligne.statut == "indexe"
        assert ligne.nb_chunks > 0
        assert ligne.categorie == kb.DEFAULT_CATEGORIE
        assert ligne.type == "fichier"
        assert ligne.titre == nom
        assert ligne.source == nom
        assert ligne.erreur is None


def test_kb_ingerer_fichier_categorie_invalide(monkeypatch):
    from app.errors import AppError
    from app.modules.kb import service as kb

    _kb_stub_embeddings(monkeypatch)
    engine = _kb_engine()
    with Session(engine) as db:
        with pytest.raises(AppError) as e:
            kb.ingerer_fichier(db, str(uuid.uuid4()), _kb_nom("x"),
                               _kb_texte().encode("utf-8"), "text/plain",
                               categorie="99_nimporte-quoi")
    assert e.value.code == "categorie_invalide"


def test_kb_ingerer_fichier_format_non_supporte():
    from app.errors import AppError
    from app.modules.kb import service as kb

    engine = _kb_engine()
    with Session(engine) as db:
        with pytest.raises(AppError) as e:
            kb.ingerer_fichier(db, str(uuid.uuid4()), "virus.exe", b"x", None)
    assert e.value.code == "unsupported_format"


def test_kb_ingerer_fichier_vide():
    from app.errors import AppError
    from app.modules.kb import service as kb

    engine = _kb_engine()
    with Session(engine) as db:
        with pytest.raises(AppError) as e:
            kb.ingerer_fichier(db, str(uuid.uuid4()), _kb_nom("vide"), b"", None)
    assert e.value.code == "empty_file"


def test_kb_ingerer_fichier_trop_volumineux(monkeypatch):
    """Tour 1, Q1 : `ingerer_fichier` réutilise `MAX_UPLOAD_BYTES` de
    `documents.service` (pas une nouvelle constante) — un fichier au-delà
    est refusé avant extraction/embeddings, jamais un 500 OOM."""
    from app.errors import AppError
    from app.modules.documents.service import MAX_UPLOAD_BYTES
    from app.modules.kb import service as kb

    engine = _kb_engine()
    with Session(engine) as db:
        with pytest.raises(AppError) as e:
            kb.ingerer_fichier(db, str(uuid.uuid4()), _kb_nom("gros"),
                               b"0" * (MAX_UPLOAD_BYTES + 1), "text/plain")
    assert e.value.code == "fichier_trop_volumineux"
    assert e.value.status_code == 413


def test_kb_ingerer_fichier_deja_indexe(monkeypatch):
    from app.errors import AppError
    from app.modules.kb import service as kb

    _kb_stub_embeddings(monkeypatch)
    engine = _kb_engine()
    nom = _kb_nom("doublon")
    with Session(engine) as db:
        kb.ingerer_fichier(db, str(uuid.uuid4()), nom,
                           _kb_texte().encode("utf-8"), "text/plain")
        with pytest.raises(AppError) as e:
            kb.ingerer_fichier(db, str(uuid.uuid4()), nom,
                               _kb_texte().encode("utf-8"), "text/plain")
    assert e.value.code == "deja_indexe"


def test_kb_ingerer_fichier_reprise_apres_echec(monkeypatch):
    """Un premier essai en échec (panne d'embeddings) laisse une ligne
    `statut="echec"` réutilisée par le second essai — pas de `deja_indexe`."""
    from app.errors import AppError
    from app.modules.kb import service as kb
    from app.modules.rag import embeddings as _emb

    engine = _kb_engine()
    nom = _kb_nom("reprise")

    def _casse(*a, **k):
        raise RuntimeError("Cohere indisponible")

    monkeypatch.setattr(_emb, "embed_texts", _casse)
    with Session(engine) as db:
        with pytest.raises(AppError) as e1:
            kb.ingerer_fichier(db, str(uuid.uuid4()), nom,
                               _kb_texte().encode("utf-8"), "text/plain")
        assert e1.value.code == "indexing_failed"

        lignes = list(db.scalars(select(KbDocument)))
        assert len(lignes) == 1
        assert lignes[0].statut == "echec"
        assert lignes[0].erreur

        _kb_stub_embeddings(monkeypatch)
        ligne2 = kb.ingerer_fichier(db, str(uuid.uuid4()), nom,
                                    _kb_texte().encode("utf-8"), "text/plain")
        assert ligne2.statut == "indexe"
        assert ligne2.erreur is None
        # même ligne réutilisée, pas une deuxième
        assert list(db.scalars(select(KbDocument))) == [ligne2]


# --- ingerer_url --------------------------------------------------------------

class _FauxFluxHTTP:
    """Fake pour `httpx.stream(...)` (tour 1, Q1 : téléchargement en flux) —
    context manager + `iter_bytes()`, comme la vraie réponse streamée."""

    def __init__(self, *, text="", content=b"", headers=None, status_code=200):
        self.content = content or text.encode("utf-8")
        self.headers = headers or {}
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError("erreur", request=None, response=self)

    def iter_bytes(self):
        pas = 4096
        for i in range(0, len(self.content), pas):
            yield self.content[i:i + pas]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_kb_ingerer_url_ok_extrait_titre_html(monkeypatch):
    from app.modules.kb import service as kb

    _kb_stub_embeddings(monkeypatch)
    engine = _kb_engine()
    url = f"https://exemple.fr/{uuid.uuid4().hex}"
    html = (f"<html><head><title>Le titre de la page</title></head><body>"
           f"<nav>menu ignoré</nav><script>alert(1)</script>"
           f"<p>{_kb_texte(600)}</p></body></html>")

    monkeypatch.setattr(
        "app.modules.kb.service.httpx.stream",
        lambda *a, **k: _FauxFluxHTTP(text=html, headers={"content-type": "text/html"}),
    )
    with Session(engine) as db:
        ligne = kb.ingerer_url(db, str(uuid.uuid4()), url)
        assert ligne.statut == "indexe"
        assert ligne.titre == "Le titre de la page"
        assert ligne.source == url
        assert ligne.type == "url"
        assert "menu ignoré" not in (kb._extraire_html(html)[1])
        assert "alert(1)" not in (kb._extraire_html(html)[1])


def test_kb_decoder_html_utilise_le_charset_de_l_entete():
    from app.modules.kb import service as kb

    brut = "Résumé économique".encode("iso-8859-1")
    assert kb._decoder_html(brut, "text/html; charset=iso-8859-1") == "Résumé économique"


def test_kb_decoder_html_utf8_sans_entete():
    from app.modules.kb import service as kb

    brut = "Réglementation européenne".encode("utf-8")
    assert kb._decoder_html(brut, "text/html") == "Réglementation européenne"


def test_kb_decoder_html_repli_cp1252_si_utf8_invalide_sans_entete():
    """Tour 2 : pas d'en-tête charset ET pas de l'UTF-8 valide (page
    réellement Latin-1/CP1252 mal servie) → repli `cp1252`, jamais une purge
    silencieuse des accents (l'ancien `errors="ignore"`)."""
    from app.modules.kb import service as kb

    brut = "Prévisions confirmées".encode("cp1252")
    assert kb._decoder_html(brut, "text/html") == "Prévisions confirmées"


def test_kb_ingerer_url_charset_iso_8859_1_respecte(monkeypatch):
    """Tour 2 : une page servie en `charset=iso-8859-1` (fréquent sur les
    sites institutionnels FR) ne doit plus perdre ses accents — l'ancien
    `data.decode("utf-8", errors="ignore")` purgeait silencieusement le
    `é` (0xE9 en Latin-1, invalide comme suite d'octet UTF-8 isolé)."""
    from app.modules.kb import service as kb

    _kb_stub_embeddings(monkeypatch)
    engine = _kb_engine()
    url = f"https://exemple.fr/{uuid.uuid4().hex}"
    html_unicode = (f"<html><head><title>Résumé économique détaillé</title></head>"
                    f"<body><p>Étude générale : {_kb_texte(600)}</p></body></html>")
    monkeypatch.setattr(
        "app.modules.kb.service.httpx.stream",
        lambda *a, **k: _FauxFluxHTTP(
            content=html_unicode.encode("iso-8859-1"),
            headers={"content-type": "text/html; charset=iso-8859-1"}),
    )
    with Session(engine) as db:
        ligne = kb.ingerer_url(db, str(uuid.uuid4()), url)
    assert ligne.titre == "Résumé économique détaillé"
    assert "�" not in ligne.titre


def test_kb_ingerer_url_utf8_sans_entete_charset_reste_correct(monkeypatch):
    """Une page UTF-8 sans `charset` dans l'en-tête (cas courant) reste
    décodée correctement — non-régression du repli utf-8 strict."""
    from app.modules.kb import service as kb

    _kb_stub_embeddings(monkeypatch)
    engine = _kb_engine()
    url = f"https://exemple.fr/{uuid.uuid4().hex}"
    html_unicode = (f"<html><head><title>Réglementation européenne</title></head>"
                    f"<body><p>{_kb_texte(600)}</p></body></html>")
    monkeypatch.setattr(
        "app.modules.kb.service.httpx.stream",
        lambda *a, **k: _FauxFluxHTTP(content=html_unicode.encode("utf-8"),
                                      headers={"content-type": "text/html"}),
    )
    with Session(engine) as db:
        ligne = kb.ingerer_url(db, str(uuid.uuid4()), url)
    assert ligne.titre == "Réglementation européenne"


def test_kb_ingerer_url_pdf_distant(monkeypatch):
    from app.modules.kb import service as kb

    _kb_stub_embeddings(monkeypatch)
    engine = _kb_engine()
    url = f"https://exemple.fr/{uuid.uuid4().hex}.pdf"

    monkeypatch.setattr(
        "app.modules.kb.service.httpx.stream",
        lambda *a, **k: _FauxFluxHTTP(content=b"%PDF-fake",
                                         headers={"content-type": "application/pdf"}),
    )
    monkeypatch.setattr("app.modules.kb.service.extract_text",
                        lambda filename, data: _kb_texte(600))
    with Session(engine) as db:
        ligne = kb.ingerer_url(db, str(uuid.uuid4()), url)
        assert ligne.statut == "indexe"
        assert ligne.mime_type == "application/pdf"
        assert ligne.source == url


def test_kb_ingerer_url_pdf_distant_illisible(monkeypatch):
    """Tour 1, Q4 : un PDF distant tronqué/chiffré doit sortir en
    `contenu_illisible` (422), jamais en 500 — même garantie que le chemin
    fichier (`extraction_failed`), le chemin URL avait l'appel non enveloppé."""
    from app.errors import AppError
    from app.modules.kb import service as kb

    engine = _kb_engine()
    url = f"https://exemple.fr/{uuid.uuid4().hex}.pdf"
    monkeypatch.setattr(
        "app.modules.kb.service.httpx.stream",
        lambda *a, **k: _FauxFluxHTTP(content=b"%PDF-fake-corrompu",
                                      headers={"content-type": "application/pdf"}),
    )

    def _casse(filename, data):
        raise ValueError("PDF corrompu")

    monkeypatch.setattr("app.modules.kb.service.extract_text", _casse)
    with Session(engine) as db:
        with pytest.raises(AppError) as e:
            kb.ingerer_url(db, str(uuid.uuid4()), url)
    assert e.value.code == "contenu_illisible"
    assert e.value.status_code == 422


def test_kb_ingerer_url_trop_volumineuse(monkeypatch):
    """Tour 1, Q1 : le téléchargement d'URL est coupé en flux au-delà de
    `MAX_UPLOAD_BYTES` — jamais chargé entier en mémoire avant vérification."""
    from app.errors import AppError
    from app.modules.documents.service import MAX_UPLOAD_BYTES
    from app.modules.kb import service as kb

    engine = _kb_engine()
    url = f"https://exemple.fr/{uuid.uuid4().hex}"
    gros_contenu = b"x" * (MAX_UPLOAD_BYTES + 1)
    monkeypatch.setattr(
        "app.modules.kb.service.httpx.stream",
        lambda *a, **k: _FauxFluxHTTP(content=gros_contenu,
                                      headers={"content-type": "text/html"}),
    )
    with Session(engine) as db:
        with pytest.raises(AppError) as e:
            kb.ingerer_url(db, str(uuid.uuid4()), url)
    assert e.value.code == "fichier_trop_volumineux"
    assert e.value.status_code == 413
    with Session(engine) as db:
        assert list(db.scalars(select(KbDocument))) == []


def test_kb_ingerer_url_contenu_insuffisant(monkeypatch):
    from app.errors import AppError
    from app.modules.kb import service as kb

    engine = _kb_engine()
    url = f"https://exemple.fr/{uuid.uuid4().hex}"
    html = "<html><head><title>Court</title></head><body><p>Trop court.</p></body></html>"
    monkeypatch.setattr(
        "app.modules.kb.service.httpx.stream",
        lambda *a, **k: _FauxFluxHTTP(text=html, headers={"content-type": "text/html"}),
    )
    with Session(engine) as db:
        with pytest.raises(AppError) as e:
            kb.ingerer_url(db, str(uuid.uuid4()), url)
        assert e.value.code == "contenu_insuffisant"
        # Aucune ligne créée pour un contenu refusé.
        assert list(db.scalars(select(KbDocument))) == []


def test_kb_ingerer_url_inaccessible(monkeypatch):
    from app.errors import AppError
    from app.modules.kb import service as kb

    engine = _kb_engine()
    url = f"https://exemple.fr/{uuid.uuid4().hex}"

    def _echec(*a, **k):
        raise OSError("connexion refusée")

    monkeypatch.setattr("app.modules.kb.service.httpx.stream", _echec)
    with Session(engine) as db:
        with pytest.raises(AppError) as e:
            kb.ingerer_url(db, str(uuid.uuid4()), url)
    assert e.value.code == "url_inaccessible"


def test_kb_ingerer_url_deja_indexe(monkeypatch):
    from app.errors import AppError
    from app.modules.kb import service as kb

    _kb_stub_embeddings(monkeypatch)
    engine = _kb_engine()
    url = f"https://exemple.fr/{uuid.uuid4().hex}"
    html = f"<html><head><title>T</title></head><body><p>{_kb_texte(600)}</p></body></html>"
    monkeypatch.setattr(
        "app.modules.kb.service.httpx.stream",
        lambda *a, **k: _FauxFluxHTTP(text=html, headers={"content-type": "text/html"}),
    )
    with Session(engine) as db:
        kb.ingerer_url(db, str(uuid.uuid4()), url)
        with pytest.raises(AppError) as e:
            kb.ingerer_url(db, str(uuid.uuid4()), url)
    assert e.value.code == "deja_indexe"


# --- lister / backfill ---------------------------------------------------------

def test_kb_lister_backfill_depuis_qdrant(monkeypatch):
    """Un point déposé directement dans Qdrant (comme le script de lot) sans
    ligne `kb_documents` apparaît au premier `lister()`."""
    from app.modules.kb import service as kb
    from app.modules.rag import embeddings as _emb
    from app.modules.rag import vector_store

    _kb_stub_embeddings(monkeypatch)
    engine = _kb_engine()
    doc_id = str(uuid.uuid4())
    vecteurs = _emb.embed_texts(["chunk un", "chunk deux"])
    vector_store.upsert_chunks(
        doc_id, "__kb__", ["chunk un", "chunk deux"], vecteurs,
        collection=vector_store.KB_COLLECTION,
        extra_payload={"title": "Rapport BCE", "filename": "bce.pdf",
                      "category": "01_macro-institutionnel",
                      "category_fallback_marker": "01_macro-institutionnel",
                      "source": "01_macro-institutionnel", "sector": ""},
    )
    with Session(engine) as db:
        items = kb.lister(db)
        ligne = next(i for i in items if i.doc_id == doc_id)
        assert ligne.titre == "Rapport BCE"
        assert ligne.categorie == "01_macro-institutionnel"
        # source == category (repli du script de lot) → pas « distincte »
        assert ligne.source == "ingestion initiale 08/2026"
        assert ligne.cree_par is None
        assert ligne.type == "fichier"
        assert ligne.statut == "indexe"
        assert ligne.nb_chunks == 2


def test_kb_lister_backfill_source_distincte_conservee(monkeypatch):
    from app.modules.kb import service as kb
    from app.modules.rag import embeddings as _emb
    from app.modules.rag import vector_store

    _kb_stub_embeddings(monkeypatch)
    engine = _kb_engine()
    doc_id = str(uuid.uuid4())
    vecteurs = _emb.embed_texts(["chunk un"])
    vector_store.upsert_chunks(
        doc_id, "__kb__", ["chunk un"], vecteurs,
        collection=vector_store.KB_COLLECTION,
        extra_payload={"title": "Étude INSEE", "filename": "insee.pdf",
                      "category": "02_sectoriel", "source": "INSEE", "sector": ""},
    )
    with Session(engine) as db:
        items = kb.lister(db)
        ligne = next(i for i in items if i.doc_id == doc_id)
        assert ligne.source == "INSEE"


def test_kb_lister_pas_de_doublon_au_second_appel(monkeypatch):
    from app.modules.kb import service as kb
    from app.modules.rag import embeddings as _emb
    from app.modules.rag import vector_store

    _kb_stub_embeddings(monkeypatch)
    engine = _kb_engine()
    doc_id = str(uuid.uuid4())
    vector_store.upsert_chunks(
        doc_id, "__kb__", ["x"], _emb.embed_texts(["x"]),
        collection=vector_store.KB_COLLECTION,
        extra_payload={"title": "T", "filename": "t.pdf",
                      "category": "01_macro-institutionnel", "source": "s", "sector": ""},
    )
    with Session(engine) as db:
        kb.lister(db)
        kb.lister(db)
        lignes = [i for i in db.scalars(select(KbDocument)) if i.doc_id == doc_id]
        assert len(lignes) == 1


def test_kb_backfill_ignore_une_ligne_en_conflit_sans_casser_les_autres(monkeypatch):
    """Tour 1, Q2 : simule deux passes de backfill concurrentes sur le même
    lot — la ligne d'un `doc_id` lève une `IntegrityError` au moment de son
    `flush()` (comme si une autre requête venait de l'écrire entre le SELECT
    `existants` et cette insertion). `_backfill` doit l'avaler via un
    SAVEPOINT par ligne et continuer : ni 500, ni perte des AUTRES lignes du
    même lot."""
    from sqlalchemy.exc import IntegrityError

    from app.modules.kb import service as kb
    from app.modules.rag import embeddings as _emb
    from app.modules.rag import vector_store

    _kb_stub_embeddings(monkeypatch)
    engine = _kb_engine()
    doc_id_en_conflit = str(uuid.uuid4())
    doc_id_normal = str(uuid.uuid4())
    for doc_id, titre in ((doc_id_en_conflit, "En conflit"), (doc_id_normal, "Normal")):
        vector_store.upsert_chunks(
            doc_id, "__kb__", ["x"], _emb.embed_texts(["x"]),
            collection=vector_store.KB_COLLECTION,
            extra_payload={"title": titre, "filename": "t.pdf",
                          "category": "01_macro-institutionnel", "source": "s", "sector": ""},
        )

    reel_flush = Session.flush
    deja_leve = {"fait": False}

    def _flush_avec_course(self, *a, **k):
        if not deja_leve["fait"]:
            for obj in list(self.new):
                if isinstance(obj, KbDocument) and obj.doc_id == doc_id_en_conflit:
                    deja_leve["fait"] = True
                    raise IntegrityError("insert", {}, Exception("unique constraint failed"))
        return reel_flush(self, *a, **k)

    monkeypatch.setattr(Session, "flush", _flush_avec_course)
    with Session(engine) as db:
        kb.lister(db)  # ne doit PAS lever malgré l'IntegrityError simulée
        lignes = {i.doc_id: i for i in db.scalars(select(KbDocument))}

    assert deja_leve["fait"]
    assert doc_id_normal in lignes
    assert lignes[doc_id_normal].titre == "Normal"
    # Aucune trace de la ligne en conflit ICI — soit l'autre requête
    # concurrente l'a bien écrite ailleurs, soit le prochain `lister()` la
    # rattrape. Dans les deux cas : jamais deux lignes, jamais une 500.
    assert doc_id_en_conflit not in lignes


def test_kb_lister_scroll_mis_en_cache(monkeypatch):
    """Deux appels rapprochés ne rescannent Qdrant qu'une fois (cache 10 min)."""
    from app.modules.kb import service as kb

    engine = _kb_engine()
    appels = []
    reel = kb._scroll_qdrant

    def _compte():
        appels.append(1)
        return reel()

    monkeypatch.setattr(kb, "_scroll_qdrant", _compte)
    with Session(engine) as db:
        kb.lister(db)
        kb.lister(db)
    assert len(appels) == 1


def test_kb_lister_cache_expire_apres_ttl(monkeypatch):
    from app.modules.kb import service as kb

    engine = _kb_engine()
    appels = []
    reel = kb._scroll_qdrant

    def _compte():
        appels.append(1)
        return reel()

    monkeypatch.setattr(kb, "_scroll_qdrant", _compte)
    with Session(engine) as db:
        kb.lister(db)
        kb._scroll_cache["at"] -= (kb._SCROLL_TTL_SECONDES + 1)
        kb.lister(db)
    assert len(appels) == 2


def test_kb_categories_disponibles_inclut_les_defauts(monkeypatch):
    from app.modules.kb import service as kb

    engine = _kb_engine()
    with Session(engine) as db:
        cats = kb.categories_disponibles(db)
    for c in kb.CATEGORIES:
        assert c in cats


# --- supprimer -----------------------------------------------------------------

def test_kb_supprimer_retire_vecteurs_et_ligne(monkeypatch):
    from app.modules.kb import service as kb
    from app.modules.rag import vector_store

    _kb_stub_embeddings(monkeypatch)
    engine = _kb_engine()
    nom = _kb_nom("a-supprimer")
    with Session(engine) as db:
        ligne = kb.ingerer_fichier(db, str(uuid.uuid4()), nom,
                                   _kb_texte().encode("utf-8"), "text/plain")
        doc_id = ligne.doc_id
        assert vector_store.has_document(doc_id, collection=vector_store.KB_COLLECTION)

        kb.supprimer(db, doc_id)

        assert not vector_store.has_document(doc_id, collection=vector_store.KB_COLLECTION)
        assert db.scalars(select(KbDocument).where(KbDocument.doc_id == doc_id)).first() is None


def test_kb_supprimer_invalide_le_cache_pas_de_ligne_fantome(monkeypatch):
    """Tour 1, Q3 : sans invalidation, le scroll caché (10 min) contient
    encore le `doc_id` supprimé — le `lister()` suivant le recrée en ligne
    fantôme (vecteurs partis, ligne `statut="indexe"`). Le cache doit être
    invalidé par `supprimer` pour que ce `lister()` revoie l'état réel."""
    from app.modules.kb import service as kb
    from app.modules.rag import embeddings as _emb
    from app.modules.rag import vector_store

    _kb_stub_embeddings(monkeypatch)
    engine = _kb_engine()
    doc_id = str(uuid.uuid4())
    vector_store.upsert_chunks(
        doc_id, "__kb__", ["x"], _emb.embed_texts(["x"]),
        collection=vector_store.KB_COLLECTION,
        extra_payload={"title": "T", "filename": "t.pdf",
                      "category": "01_macro-institutionnel", "source": "s", "sector": ""},
    )
    with Session(engine) as db:
        # Premier listage : backfille la ligne ET met le scroll en cache.
        items = kb.lister(db)
        assert any(i.doc_id == doc_id for i in items)
        assert kb._scroll_cache["docs"] is not None

        kb.supprimer(db, doc_id)
        assert kb._scroll_cache["docs"] is None  # invalidé, pas seulement expiré

        items_apres = kb.lister(db)
        assert not any(i.doc_id == doc_id for i in items_apres)
        assert db.scalars(select(KbDocument).where(KbDocument.doc_id == doc_id)).first() is None


def test_kb_supprimer_introuvable():
    from app.errors import AppError
    from app.modules.kb import service as kb

    engine = _kb_engine()
    with Session(engine) as db:
        with pytest.raises(AppError) as e:
            kb.supprimer(db, str(uuid.uuid4()))
    assert e.value.code == "not_found"


# --- routes HTTP admin -----------------------------------------------------

def _http_kb(engine, *, is_admin):
    from fastapi.testclient import TestClient

    from app.db import get_db
    from app.main import app as _app
    from app.modules.auth.schemas import AuthUser
    from app.modules.auth.security import get_current_admin

    def _db():
        with Session(engine) as s:
            yield s

    admin = AuthUser(id=str(uuid.uuid4()), email="admin@axial-ia.fr", is_admin=is_admin)

    def _admin_dep():
        if not is_admin:
            from app.errors import AppError

            raise AppError("Accès réservé aux administrateurs.", 403, code="forbidden")
        return admin

    _app.dependency_overrides[get_db] = _db
    _app.dependency_overrides[get_current_admin] = _admin_dep
    return _app, TestClient(_app)


def test_kb_route_liste_refusee_a_un_non_admin():
    engine = _kb_engine()
    app_, client = _http_kb(engine, is_admin=False)
    try:
        r = client.get("/admin/kb")
        assert r.status_code == 403
    finally:
        app_.dependency_overrides.clear()


def test_kb_route_upload_fichier_admin(monkeypatch):
    from app.modules.rag import embeddings as _emb

    monkeypatch.setattr(_emb, "embed_texts",
                        lambda textes, **kw: [[0.01] * _emb.embedding_dim() for _ in textes])
    engine = _kb_engine()
    app_, client = _http_kb(engine, is_admin=True)
    try:
        nom = _kb_nom("upload")
        r = client.post(
            "/admin/kb/fichiers",
            files={"fichier": (nom, _io_kb.BytesIO(_kb_texte().encode("utf-8")), "text/plain")},
        )
        assert r.status_code == 200, r.text
        corps = r.json()
        assert corps["statut"] == "indexe"
        assert corps["nb_chunks"] > 0
        assert corps["categorie"] == "07_ajouts-admin"

        r2 = client.get("/admin/kb")
        assert r2.status_code == 200
        liste = r2.json()
        assert any(i["doc_id"] == corps["doc_id"] for i in liste["items"])
        assert "07_ajouts-admin" in liste["categories"]
    finally:
        app_.dependency_overrides.clear()


def test_kb_route_ajouter_url_admin(monkeypatch):
    monkeypatch.setattr(
        "app.modules.kb.service.httpx.stream",
        lambda *a, **k: _FauxFluxHTTP(
            text=(f"<html><head><title>Page test</title></head>"
                 f"<body><p>{_kb_texte(600)}</p></body></html>"),
            headers={"content-type": "text/html"},
        ),
    )
    from app.modules.rag import embeddings as _emb

    monkeypatch.setattr(_emb, "embed_texts",
                        lambda textes, **kw: [[0.01] * _emb.embedding_dim() for _ in textes])
    engine = _kb_engine()
    app_, client = _http_kb(engine, is_admin=True)
    try:
        url = f"https://exemple.fr/{uuid.uuid4().hex}"
        r = client.post("/admin/kb/urls", json={"url": url})
        assert r.status_code == 200, r.text
        corps = r.json()
        assert corps["titre"] == "Page test"
        assert corps["type"] == "url"
    finally:
        app_.dependency_overrides.clear()


def test_kb_route_supprimer_admin(monkeypatch):
    from app.modules.rag import embeddings as _emb

    monkeypatch.setattr(_emb, "embed_texts",
                        lambda textes, **kw: [[0.01] * _emb.embedding_dim() for _ in textes])
    engine = _kb_engine()
    app_, client = _http_kb(engine, is_admin=True)
    try:
        nom = _kb_nom("a-effacer")
        r = client.post(
            "/admin/kb/fichiers",
            files={"fichier": (nom, _io_kb.BytesIO(_kb_texte().encode("utf-8")), "text/plain")},
        )
        doc_id = r.json()["doc_id"]
        r2 = client.delete(f"/admin/kb/{doc_id}")
        assert r2.status_code == 204
        r3 = client.delete(f"/admin/kb/{doc_id}")
        assert r3.status_code == 404
    finally:
        app_.dependency_overrides.clear()


# --- rag.service / grounding : intégration (pas de nouveau code ici) --------
#
# `rag.service.retrieve` et `grounding.assemble` gèrent déjà `Passage.source
# == "kb"` (méta `title`, tag « réf. interne », citation sans jamais nommer
# « base Axial ») — vérifié ci-dessous plutôt que redupliqué.

def test_kb_passage_source_kb_et_titre_apres_ingestion(monkeypatch):
    from app.modules.kb import service as kb
    from app.modules.rag import embeddings as _emb
    from app.modules.rag import vector_store

    _kb_stub_embeddings(monkeypatch)
    engine = _kb_engine()
    nom = _kb_nom("passage")
    with Session(engine) as db:
        ligne = kb.ingerer_fichier(db, str(uuid.uuid4()), nom,
                                   _kb_texte().encode("utf-8"), "text/plain")

    vecteur = _emb.embed_texts(["mot0"])[0]
    passages = vector_store.search(vecteur, user_id=None, top_k=50,
                                   collection=vector_store.KB_COLLECTION)
    trouve = next(p for p in passages if p.doc_id == ligne.doc_id)
    assert trouve.source == "kb"
    assert trouve.meta.get("title") == nom


def test_kb_grounding_contexte_modele_etiquette_base_axial():
    """Tour 1, décision C2 : le CONTEXTE MODÈLE (jamais vu par l'utilisateur)
    étiquette « (base Axial : <titre>) » pour un passage KB."""
    from app.modules.rag.vector_store import Passage
    from app.shared import grounding

    passage = Passage(text="contenu interne", score=0.9, doc_id="d1", source="kb",
                      meta={"title": "Guide interne", "source": "Guide interne"})
    contexte, _ = grounding.assemble("question", [], [passage])
    assert "(base Axial : Guide interne)" in contexte


def test_kb_grounding_citation_source_interne_fige(monkeypatch):
    """Tour 1, décision C1 : le backend garde `source="interne"` — contrat
    existant, figé ici pour que Task 6 (front) puisse s'appuyer dessus sans
    surprise. Aucun libellé « base Axial »/« base de connaissance » ne fuit
    dans la citation elle-même (titre, référence, extrait) : c'est le FRONT,
    pas ce backend, qui choisit le libellé neutre affiché à l'utilisateur."""
    from app.modules.rag.vector_store import Passage
    from app.shared import grounding

    passage = Passage(text="contenu interne", score=0.9, doc_id="d1", source="kb",
                      meta={"title": "Guide interne", "category": "03_reglementaire"})
    _, citations = grounding.assemble("question", [], [passage])
    assert citations[0]["source"] == "interne"
    assert citations[0]["title"] == "Guide interne"
    for valeur in (citations[0]["title"], citations[0].get("reference") or "",
                  citations[0].get("excerpt") or ""):
        assert "axial" not in valeur.lower()
        assert "base de connaissance" not in valeur.lower()


def test_kb_format_context_rag_etiquette_base_axial():
    """`rag.service.format_context` (le SEUL bloc vu par le modèle) porte la
    même étiquette que `grounding.assemble` — décision C2, les deux endroits
    nommés par le contrôleur."""
    from app.modules.rag import service as rag_service
    from app.modules.rag.vector_store import Passage

    passage = Passage(text="contenu interne", score=0.9, doc_id="d1", source="kb",
                      meta={"title": "Guide interne", "source": "Guide interne"})
    contexte = rag_service.format_context([passage])
    assert "(base Axial : Guide interne)" in contexte


# --- Task 8 : santé réelle des fournisseurs ---------------------------------
#
# `health.providers_summary(reel=True)` : un appel de test court par
# fournisseur CONFIGURÉ, en parallèle, timeout 8 s chacun. Jamais
# d'exception hors de la fonction. Voir spec §8.

_CLES_REEL = ("EXA_API_KEY", "TAVILY_API_KEY", "LINKUP_API_KEY",
             "PERPLEXITY_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY",
             "COHERE_API_KEY", "PAPPERS_API_KEY")


def _isoler_cles_reel(monkeypatch, *actives):
    """Décharge TOUTES les clés touchées par le mode réel, puis n'active que
    celles données. Sans ça, une vraie clé Doppler déjà présente dans
    l'environnement de dev ferait un vrai appel réseau et rendrait ces tests
    non déterministes (voire lents/flaky selon la connectivité)."""
    for var in _CLES_REEL:
        monkeypatch.delenv(var, raising=False)
    for var in actives:
        monkeypatch.setenv(var, "cle-test")
    get_settings.cache_clear()


def test_health_reel_tous_fournisseurs_configures_succes(monkeypatch):
    """Chaque fournisseur configuré est vérifié : moteurs de recherche
    (search non vide), LLM chat/report (generate ne lève pas), rerank
    (score réel), Pappers (fiche trouvée). `ok` global reste vrai."""
    from app.shared import health

    _isoler_cles_reel(monkeypatch, *_CLES_REEL)
    try:
        from app.shared.search import providers as search_providers
        for moteur in ("exa", "tavily", "linkup", "perplexity"):
            monkeypatch.setattr(search_providers.get_provider(moteur), "search",
                                lambda *a, **k: [object()])

        from app.shared import llm_client
        monkeypatch.setattr(llm_client, "generate", lambda **k: object())

        from app.shared.search import rerank as rerank_mod
        monkeypatch.setattr(rerank_mod, "rerank_indices_avec_etat",
                            lambda *a, **k: ([(0, 0.9)], True))

        from app.shared.enrich import pappers as pappers_mod
        monkeypatch.setattr(pappers_mod, "rechercher", lambda nom: {"siren": "123456789"})

        corps = health.providers_summary(reel=True)
        assert corps["ok"] is True
        par_nom = {p["name"]: p for p in corps["providers"]}
        for nom in ("exa", "tavily", "linkup", "perplexity", "llm_chat_gemini",
                   "llm_report_claude", "rerank_cohere", "pappers"):
            assert par_nom[nom]["ok"] is True, par_nom[nom]
            assert par_nom[nom]["erreur"] is None
            assert isinstance(par_nom[nom]["latence_ms"], int)
            assert par_nom[nom]["latence_ms"] >= 0
    finally:
        get_settings.cache_clear()


def test_health_reel_echec_fournisseur_masque_le_secret_et_tronque(monkeypatch):
    from app.shared import health

    _isoler_cles_reel(monkeypatch, "EXA_API_KEY")
    try:
        from app.shared.search import providers as search_providers

        def _echoue(*a, **k):
            raise RuntimeError("échec appel https://api.exa.ai/search?key=abc " + "x" * 300)

        monkeypatch.setattr(search_providers.get_provider("exa"), "search", _echoue)

        corps = health.providers_summary(reel=True)
        exa = next(p for p in corps["providers"] if p["name"] == "exa")
        assert exa["ok"] is False
        assert "abc" not in exa["erreur"]
        assert "masqué" in exa["erreur"]
        assert len(exa["erreur"]) <= 200
    finally:
        get_settings.cache_clear()


def test_health_reel_timeout_devient_ok_false(monkeypatch):
    import time as time_mod

    from app.shared import health

    _isoler_cles_reel(monkeypatch, "EXA_API_KEY")
    monkeypatch.setattr(health, "TIMEOUT_REEL_SECONDES", 0.05)
    try:
        from app.shared.search import providers as search_providers

        def _dort(*a, **k):
            time_mod.sleep(0.2)
            return [object()]

        monkeypatch.setattr(search_providers.get_provider("exa"), "search", _dort)

        corps = health.providers_summary(reel=True)
        exa = next(p for p in corps["providers"] if p["name"] == "exa")
        assert exa["ok"] is False
        assert "délai dépassé" in exa["erreur"]
        assert exa["latence_ms"] is None
    finally:
        get_settings.cache_clear()


def test_health_reel_ne_retient_pas_la_reponse_au_dela_du_delai(monkeypatch):
    """Tour 1, revue Task 8 : `_verifications_reelles` ne doit pas attendre
    la fin réelle d'un thread bloqué au-delà de `TIMEOUT_REEL_SECONDES` — un
    `with ThreadPoolExecutor(...)` attendrait sa sortie que le thread
    dormant se termine. Bouchon qui dort 1 s, timeout patché à 0,1 s :
    `providers_summary(reel=True)` doit rendre la main bien avant 1 s."""
    import time as time_mod

    from app.shared import health

    _isoler_cles_reel(monkeypatch, "EXA_API_KEY")
    monkeypatch.setattr(health, "TIMEOUT_REEL_SECONDES", 0.1)
    try:
        from app.shared.search import providers as search_providers

        def _dort_longtemps(*a, **k):
            time_mod.sleep(1)
            return [object()]

        monkeypatch.setattr(search_providers.get_provider("exa"), "search",
                            _dort_longtemps)

        debut = time_mod.monotonic()
        corps = health.providers_summary(reel=True)
        duree = time_mod.monotonic() - debut

        assert duree < 0.5, f"a attendu {duree:.2f} s — retient la réponse au thread bloqué"
        exa = next(p for p in corps["providers"] if p["name"] == "exa")
        assert exa["ok"] is False
        assert "délai dépassé" in exa["erreur"]
    finally:
        get_settings.cache_clear()


def test_health_reel_fournisseur_non_configure_pas_appele(monkeypatch):
    """Un fournisseur non configuré reste statique : `ok=None`, jamais
    appelé (spec §8 : « par fournisseur CONFIGURÉ »)."""
    from app.shared import health

    _isoler_cles_reel(monkeypatch)
    try:
        from app.shared.search import providers as search_providers

        def _jamais_appele(*a, **k):
            raise AssertionError("ne doit pas être appelé : exa non configuré")

        if search_providers.get_provider("exa") is not None:
            monkeypatch.setattr(search_providers.get_provider("exa"), "search",
                                _jamais_appele)

        corps = health.providers_summary(reel=True)
        exa = next(p for p in corps["providers"] if p["name"] == "exa")
        assert exa["configured"] is False
        assert exa["ok"] is None
        assert exa["latence_ms"] is None
        assert exa["erreur"] is None
    finally:
        get_settings.cache_clear()


def test_health_reel_statiques_gardent_ok_none(monkeypatch):
    """stripe/presidio/analytics/embeddings_cohere ne sont jamais réellement
    testés (spec §8) : `ok=None`, même en mode réel, même configurés."""
    from app.shared import health

    _isoler_cles_reel(monkeypatch)
    corps = health.providers_summary(reel=True)
    par_nom = {p["name"]: p for p in corps["providers"]}
    for nom in ("stripe", "presidio", "analytics", "embeddings_cohere", "serper"):
        assert par_nom[nom]["ok"] is None
        assert par_nom[nom]["latence_ms"] is None
        assert par_nom[nom]["erreur"] is None


def test_health_reel_ok_global_false_si_requis_en_echec(monkeypatch):
    from app.shared import health

    _isoler_cles_reel(monkeypatch, "GEMINI_API_KEY")
    try:
        from app.shared import llm_client

        def _echoue(**k):
            raise RuntimeError("panne Gemini")

        monkeypatch.setattr(llm_client, "generate", _echoue)

        corps = health.providers_summary(reel=True)
        assert corps["ok"] is False
        chat = next(p for p in corps["providers"] if p["name"] == "llm_chat_gemini")
        assert chat["ok"] is False
    finally:
        get_settings.cache_clear()


def test_health_reel_ok_global_vrai_si_seul_non_requis_en_echec(monkeypatch):
    """`exa` n'est pas `required` individuellement (l'agrégat web_search
    l'est en mode statique) : son échec seul ne fait pas basculer `ok`
    global, tant que tous les fournisseurs `required` (ici configurés et
    en succès) restent au vert."""
    from app.shared import health

    _isoler_cles_reel(monkeypatch, *_CLES_REEL)
    try:
        from app.shared.search import providers as search_providers

        def _echoue(*a, **k):
            raise RuntimeError("panne Exa")

        monkeypatch.setattr(search_providers.get_provider("exa"), "search", _echoue)
        for moteur in ("tavily", "linkup", "perplexity"):
            monkeypatch.setattr(search_providers.get_provider(moteur), "search",
                                lambda *a, **k: [object()])

        from app.shared import llm_client
        monkeypatch.setattr(llm_client, "generate", lambda **k: object())

        from app.shared.search import rerank as rerank_mod
        monkeypatch.setattr(rerank_mod, "rerank_indices_avec_etat",
                            lambda *a, **k: ([(0, 0.9)], True))

        from app.shared.enrich import pappers as pappers_mod
        monkeypatch.setattr(pappers_mod, "rechercher", lambda nom: {"siren": "123456789"})

        corps = health.providers_summary(reel=True)
        assert corps["missing_required"] == []
        exa = next(p for p in corps["providers"] if p["name"] == "exa")
        assert exa["ok"] is False
        assert exa["required"] is False
        assert corps["ok"] is True
    finally:
        get_settings.cache_clear()


def test_health_reel_sans_reel_comportement_inchange():
    """`providers_summary()` (sans `reel`) reste la vue statique actuelle :
    pas de clés `ok`/`latence_ms`/`erreur`, `web_search` toujours présent."""
    from app.shared import health

    corps = health.providers_summary()
    noms = {p["name"] for p in corps["providers"]}
    assert "web_search" in noms
    assert "exa" not in noms
    for p in corps["providers"]:
        assert "ok" not in p
        assert "latence_ms" not in p
        assert "erreur" not in p


def _http_health(*, is_admin: bool | None):
    """`TestClient` sur l'app réelle, avec ou sans utilisateur admin.

    `is_admin=None` simule l'absence de jeton (utilisateur anonyme) ;
    `is_admin=True/False` simule un jeton valide pour un compte
    admin/non-admin — les deux doivent être refusés pour `reel=1`."""
    from fastapi.testclient import TestClient

    from app.main import app as _app
    from app.modules.auth.schemas import AuthUser
    from app.modules.auth.security import get_current_user_optionnel

    utilisateur = (None if is_admin is None
                  else AuthUser(id=str(uuid.uuid4()), email="u@axial-ia.fr",
                                is_admin=is_admin))
    _app.dependency_overrides[get_current_user_optionnel] = lambda: utilisateur
    return _app, TestClient(_app)


def test_health_reel_route_403_sans_jeton():
    app_, client = _http_health(is_admin=None)
    try:
        r = client.get("/health/providers?reel=1")
        assert r.status_code == 403
    finally:
        app_.dependency_overrides.clear()


def test_health_reel_route_403_non_admin():
    app_, client = _http_health(is_admin=False)
    try:
        r = client.get("/health/providers?reel=1")
        assert r.status_code == 403
    finally:
        app_.dependency_overrides.clear()


def test_health_reel_route_admin_ok(monkeypatch):
    """Isole les clés réelles : sans ça, un compte de dev avec de vraies
    clés Doppler déclencherait de vrais appels réseau depuis ce test."""
    _isoler_cles_reel(monkeypatch)
    app_, client = _http_health(is_admin=True)
    try:
        r = client.get("/health/providers?reel=1")
        assert r.status_code == 200
        corps = r.json()
        assert "providers" in corps
        assert all("ok" in p for p in corps["providers"])
    finally:
        app_.dependency_overrides.clear()
        get_settings.cache_clear()


def test_health_route_publique_sans_reel_inchangee():
    """L'appel public sans `reel` (utilisé par la supervision) ne demande
    toujours aucune authentification et garde la forme statique."""
    app_, client = _http_health(is_admin=None)
    try:
        r = client.get("/health/providers")
        assert r.status_code == 200
        corps = r.json()
        assert "ok" in corps
        for p in corps["providers"]:
            assert "ok" not in p
    finally:
        app_.dependency_overrides.clear()


# --- Task 7 : Drive comme source (spec §6) ----------------------------------
# `telecharger_drive` télécharge/exporte un fichier Drive choisi via le
# Picker et le remet dans le même format que `documents.ingest` attend.

import httpx  # noqa: E402

from app.errors import AppError  # noqa: E402


class _RepDrive:
    """Réponse `httpx.stream(...)` bouchonnée (context manager)."""

    def __init__(self, status_code=200, morceaux=(b"contenu",)):
        self.status_code = status_code
        self._morceaux = list(morceaux)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def iter_bytes(self):
        yield from self._morceaux

    def raise_for_status(self):
        if self.status_code >= 300:
            raise httpx.HTTPStatusError("erreur", request=None, response=self)


def _drive_stub_stream(monkeypatch, *, status_code=200, morceaux=(b"contenu",), capture=None):
    def _stream(method, url, headers=None, params=None, timeout=None):
        if capture is not None:
            capture.append({"method": method, "url": url, "headers": headers,
                            "params": params, "timeout": timeout})
        return _RepDrive(status_code=status_code, morceaux=morceaux)

    monkeypatch.setattr(
        "app.modules.integrations.service.httpx.stream", _stream)


def test_drive_sans_jeton_google_non_connecte(monkeypatch):
    from app.modules.integrations import service as integrations

    monkeypatch.setattr(integrations, "jeton_actif", lambda db, uid, provider: None)
    with pytest.raises(AppError) as e:
        integrations.telecharger_drive(None, str(uuid.uuid4()), "file123",
                                       "Pitch deck", "application/pdf")
    assert e.value.code == "google_non_connecte"
    assert e.value.status_code == 400


def test_drive_export_google_doc_devient_txt(monkeypatch):
    from app.modules.integrations import service as integrations

    monkeypatch.setattr(integrations, "jeton_actif", lambda db, uid, provider: "TOKEN")
    capture: list[dict] = []
    _drive_stub_stream(monkeypatch, morceaux=(b"Bonjour ", b"le monde"), capture=capture)

    nom, data, mime = integrations.telecharger_drive(
        None, str(uuid.uuid4()), "doc123", "Notes de réunion",
        "application/vnd.google-apps.document")

    assert nom == "Notes de réunion.txt"
    assert data == b"Bonjour le monde"
    assert mime == "text/plain"
    assert capture[0]["url"] == f"{integrations.DRIVE_API}/files/doc123/export"
    assert capture[0]["params"] == {"mimeType": "text/plain"}
    assert capture[0]["headers"]["Authorization"] == "Bearer TOKEN"


@pytest.mark.parametrize("mime_google,export_mime,suffixe", [
    ("application/vnd.google-apps.spreadsheet", "text/csv", ".csv"),
    ("application/vnd.google-apps.presentation", "application/pdf", ".pdf"),
])
def test_drive_export_sheet_et_slides_passent_par_telecharger_drive(
        monkeypatch, mime_google, export_mime, suffixe):
    """Revue Task 7, bloquant qualité 3 : la constante `GOOGLE_DOC_EXPORTS`
    seule ne prouve rien sur `telecharger_drive` — il faut exercer l'URL
    `/export`, le suffixe du nom et le mime de sortie pour Sheets et Slides
    comme c'est déjà fait pour Docs."""
    from app.modules.integrations import service as integrations

    monkeypatch.setattr(integrations, "jeton_actif", lambda db, uid, provider: "TOKEN")
    capture: list[dict] = []
    _drive_stub_stream(monkeypatch, morceaux=(b"contenu",), capture=capture)

    nom, data, mime = integrations.telecharger_drive(
        None, str(uuid.uuid4()), "fid", "Rapport", mime_google)

    assert nom == f"Rapport{suffixe}"
    assert data == b"contenu"
    assert mime == export_mime
    assert capture[0]["url"] == f"{integrations.DRIVE_API}/files/fid/export"
    assert capture[0]["params"] == {"mimeType": export_mime}


def test_drive_binaire_garde_le_nom_d_origine(monkeypatch):
    from app.modules.integrations import service as integrations

    monkeypatch.setattr(integrations, "jeton_actif", lambda db, uid, provider: "TOKEN")
    capture: list[dict] = []
    _drive_stub_stream(monkeypatch, morceaux=(b"%PDF-1.4 ...",), capture=capture)

    nom, data, mime = integrations.telecharger_drive(
        None, str(uuid.uuid4()), "bin456", "Business plan.pdf", "application/pdf")

    assert nom == "Business plan.pdf"
    assert data == b"%PDF-1.4 ..."
    assert mime == "application/pdf"
    assert capture[0]["url"] == f"{integrations.DRIVE_API}/files/bin456"
    assert capture[0]["params"] == {"alt": "media"}


def test_drive_404_google_devient_erreur_nommee(monkeypatch):
    from app.modules.integrations import service as integrations

    monkeypatch.setattr(integrations, "jeton_actif", lambda db, uid, provider: "TOKEN")
    _drive_stub_stream(monkeypatch, status_code=404)

    with pytest.raises(AppError) as e:
        integrations.telecharger_drive(None, str(uuid.uuid4()), "manquant",
                                       "Fichier disparu.pdf", "application/pdf")
    assert e.value.code == "drive_fichier_inaccessible"


def test_drive_403_google_devient_aussi_inaccessible(monkeypatch):
    from app.modules.integrations import service as integrations

    monkeypatch.setattr(integrations, "jeton_actif", lambda db, uid, provider: "TOKEN")
    _drive_stub_stream(monkeypatch, status_code=403)

    with pytest.raises(AppError) as e:
        integrations.telecharger_drive(None, str(uuid.uuid4()), "interdit",
                                       "Fichier interdit.pdf", "application/pdf")
    assert e.value.code == "drive_fichier_inaccessible"


def test_drive_trop_volumineux_coupe_le_flux(monkeypatch):
    from app.modules.documents.service import MAX_UPLOAD_BYTES
    from app.modules.integrations import service as integrations

    monkeypatch.setattr(integrations, "jeton_actif", lambda db, uid, provider: "TOKEN")
    gros_morceau = b"0" * (MAX_UPLOAD_BYTES // 2 + 1)
    _drive_stub_stream(monkeypatch, morceaux=(gros_morceau, gros_morceau))

    with pytest.raises(AppError) as e:
        integrations.telecharger_drive(None, str(uuid.uuid4()), "gros",
                                       "Trop gros.pdf", "application/pdf")
    assert e.value.code == "fichier_trop_volumineux"
    assert e.value.status_code == 413


def test_drive_nom_trop_long_est_tronque(monkeypatch):
    """Revue Task 7, bloquant conformité 2 : `Document.filename` est
    `String(512)` — un nom non borné avant l'ajout d'un suffixe d'export
    ferait échouer l'insertion Postgres (`DataError` non nommée, 500 brut)
    plutôt que produire un document. `_nettoyer_nom` borne à 200."""
    from app.modules.integrations import service as integrations

    monkeypatch.setattr(integrations, "jeton_actif", lambda db, uid, provider: "TOKEN")
    _drive_stub_stream(monkeypatch, morceaux=(b"contenu",))

    nom_long = "a" * 600
    nom, data, mime = integrations.telecharger_drive(
        None, str(uuid.uuid4()), "fid", nom_long, "application/pdf")

    assert len(nom) == integrations._NOM_LONGUEUR_MAX
    assert nom == "a" * integrations._NOM_LONGUEUR_MAX


def test_drive_nom_nettoye_des_separateurs_et_caracteres_de_controle(monkeypatch):
    from app.modules.integrations import service as integrations

    monkeypatch.setattr(integrations, "jeton_actif", lambda db, uid, provider: "TOKEN")
    _drive_stub_stream(monkeypatch, morceaux=(b"contenu",))

    nom, _, _ = integrations.telecharger_drive(
        None, str(uuid.uuid4()), "fid", "../../etc/passwd\x00\x1b.pdf", "application/pdf")

    assert "/" not in nom
    assert "\x00" not in nom and "\x1b" not in nom


def test_drive_nom_vide_apres_nettoyage_est_inaccessible(monkeypatch):
    from app.modules.integrations import service as integrations

    monkeypatch.setattr(integrations, "jeton_actif", lambda db, uid, provider: "TOKEN")
    with pytest.raises(AppError) as e:
        integrations.telecharger_drive(None, str(uuid.uuid4()), "fid",
                                       "\x00\x01\x02", "application/pdf")
    assert e.value.code == "drive_fichier_inaccessible"


def test_drive_mime_type_borne_a_128(monkeypatch):
    from app.modules.integrations import service as integrations

    monkeypatch.setattr(integrations, "jeton_actif", lambda db, uid, provider: "TOKEN")
    _drive_stub_stream(monkeypatch, morceaux=(b"contenu",))

    _, _, mime = integrations.telecharger_drive(
        None, str(uuid.uuid4()), "fid", "fichier.bin", "x" * 500)
    assert len(mime) == integrations._MIME_LONGUEUR_MAX


def test_drive_route_nom_de_600_caracteres_cree_le_document_tronque(monkeypatch):
    """Bout en bout via la route (contrainte du tour de correction) : un
    `name` de 600 caractères ne doit jamais produire un 500, seulement un
    document créé avec un nom tronqué."""
    import datetime as _dt

    from fastapi.testclient import TestClient

    from app.db import get_db
    from app.main import app as _app
    from app.modules.auth.schemas import AuthUser
    from app.modules.auth.security import get_current_user
    from app.modules.integrations import service as integrations

    user_id = str(uuid.uuid4())
    monkeypatch.setattr(integrations, "jeton_actif", lambda db, uid, provider: "TOKEN")
    _drive_stub_stream(monkeypatch, morceaux=(b"contenu",))

    capture: dict = {}

    class _DocStub:
        id = uuid.uuid4()
        filename = ""
        mime_type = "application/pdf"
        size_bytes = 7
        chunk_count = 1
        created_at = _dt.datetime.now(_dt.timezone.utc)

    def _ingest_stub(db, *, user_id, filename, data, mime_type=None):
        capture.update(filename=filename)
        _DocStub.filename = filename
        return _DocStub()

    monkeypatch.setattr("app.modules.documents.service.ingest", _ingest_stub)

    _app.dependency_overrides[get_current_user] = lambda: AuthUser(
        id=user_id, email="u@axial-ia.fr", is_admin=False)
    _app.dependency_overrides[get_db] = lambda: iter([None])
    client = TestClient(_app)
    try:
        r = client.post("/integrations/google/importer",
                        json={"file_id": "abc", "name": "b" * 600,
                              "mime_type": "application/pdf"})
        assert r.status_code == 200, r.text
        assert len(capture["filename"]) <= 200
    finally:
        _app.dependency_overrides.clear()


def test_drive_etat_expose_selecteur_selon_client_id(monkeypatch):
    """`etat()` expose `google.selecteur` indépendamment de `configure()` :
    le Picker n'a besoin que de l'identifiant client, pas du secret ni de
    `integrations_secret_key` (spec §6)."""
    from app.modules.integrations import service as integrations

    engine = _kb_engine_integrations()
    with Session(engine) as db:
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "abc123")
        monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("INTEGRATIONS_SECRET_KEY", raising=False)
        get_settings.cache_clear()
        try:
            out = integrations.etat(db, str(uuid.uuid4()))
            assert out["google"]["selecteur"] is True
            # Non configuré côté serveur (secret manquant) : le bouton de
            # connexion reste masqué, seul le sélecteur diffère.
            assert out["google"]["configure"] is False
        finally:
            monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
            get_settings.cache_clear()


def test_drive_etat_selecteur_faux_sans_client_id(monkeypatch):
    from app.modules.integrations import service as integrations

    engine = _kb_engine_integrations()
    with Session(engine) as db:
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        get_settings.cache_clear()
        try:
            out = integrations.etat(db, str(uuid.uuid4()))
            assert out["google"]["selecteur"] is False
        finally:
            get_settings.cache_clear()


def _kb_engine_integrations():
    """Base en mémoire suffisante pour `service.get()` (table `user_connections`)."""
    import app.modules.integrations.models  # noqa: F401
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    from app.db import Base as _Base

    engine = create_engine("sqlite://", future=True,
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    _Base.metadata.create_all(engine, tables=[_Base.metadata.tables["user_connections"]])
    return engine


def test_drive_route_importer_appelle_ingest(monkeypatch):
    """`POST /integrations/google/importer` enchaîne `telecharger_drive` puis
    `documents.ingest` et renvoie le document créé, comme l'upload local."""
    import datetime as _dt

    from fastapi.testclient import TestClient

    from app.db import get_db
    from app.main import app as _app
    from app.modules.auth.schemas import AuthUser
    from app.modules.auth.security import get_current_user
    from app.modules.integrations import service as integrations

    user_id = str(uuid.uuid4())
    monkeypatch.setattr(integrations, "telecharger_drive",
                        lambda db, uid, fid, name, mime: ("notes.txt", b"contenu", "text/plain"))

    class _DocStub:
        id = uuid.uuid4()
        filename = "notes.txt"
        mime_type = "text/plain"
        size_bytes = 7
        chunk_count = 1
        created_at = _dt.datetime.now(_dt.timezone.utc)

    capture: dict = {}

    def _ingest_stub(db, *, user_id, filename, data, mime_type=None):
        capture.update(user_id=user_id, filename=filename, data=data, mime_type=mime_type)
        return _DocStub()

    monkeypatch.setattr("app.modules.documents.service.ingest", _ingest_stub)

    _app.dependency_overrides[get_current_user] = lambda: AuthUser(
        id=user_id, email="u@axial-ia.fr", is_admin=False)
    _app.dependency_overrides[get_db] = lambda: iter([None])
    client = TestClient(_app)
    try:
        r = client.post("/integrations/google/importer",
                        json={"file_id": "abc", "name": "Notes", "mime_type": "application/pdf"})
        assert r.status_code == 200
        corps = r.json()
        assert corps["filename"] == "notes.txt"
        assert corps["chunk_count"] == 1
        assert capture["filename"] == "notes.txt"
        assert capture["data"] == b"contenu"
        assert capture["mime_type"] == "text/plain"
    finally:
        _app.dependency_overrides.clear()


def test_drive_route_sans_jeton_renvoie_400(monkeypatch):
    from fastapi.testclient import TestClient

    from app.db import get_db
    from app.main import app as _app
    from app.modules.auth.schemas import AuthUser
    from app.modules.auth.security import get_current_user
    from app.modules.integrations import service as integrations

    user_id = str(uuid.uuid4())
    monkeypatch.setattr(integrations, "jeton_actif", lambda db, uid, provider: None)

    _app.dependency_overrides[get_current_user] = lambda: AuthUser(
        id=user_id, email="u@axial-ia.fr", is_admin=False)
    _app.dependency_overrides[get_db] = lambda: iter([None])
    client = TestClient(_app)
    try:
        r = client.post("/integrations/google/importer",
                        json={"file_id": "abc", "name": "Notes", "mime_type": "application/pdf"})
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "google_non_connecte"
    finally:
        _app.dependency_overrides.clear()


# --- Revue finale : robustesse du listage et bornes de titre -----------------

def test_kb_lister_survit_a_un_qdrant_injoignable(monkeypatch):
    """Un scroll Qdrant qui lève ne rend jamais 500 : la liste en base s'affiche."""
    from app.modules.kb import service as kb

    engine = _kb_engine()

    def _casse():
        raise RuntimeError("timed out key=abc")

    monkeypatch.setattr(kb, "_scroll_qdrant_cache", _casse)
    with Session(engine) as db:
        items = kb.lister(db)
    assert items == []


def test_kb_titre_borne_a_500_caracteres(monkeypatch):
    from app.modules.kb import service as kb

    _kb_stub_embeddings(monkeypatch)
    engine = _kb_engine()
    with Session(engine) as db:
        ligne = kb._indexer(db, ligne=None, doc_id="kb:test-titre-long", titre="x" * 900,
                            source="https://exemple.fr/" + "y" * 900, type_="url",
                            categorie="07_ajouts-admin", mime_type="text/html",
                            taille_octets=10, admin_id=None, text="mot " * 500, filename=None)
        assert len(ligne.titre) == 500


# --- Extraction des noms de sociétés : déterministe + JSON (15/09) ---------

def test_noms_dans_la_question_liste_entre_parentheses():
    from app.modules.analysis.service import _noms_dans_la_question
    q = ("Marché français des logiciels de notes de frais pour PME en 2026 : taille, acteurs "
         "en présence (Expensya, N2F, Spendesk, Jenji, Lucca), dynamique et opportunités (France, PME).")
    assert _noms_dans_la_question(q) == ["Expensya", "N2F", "Spendesk", "Jenji", "Lucca"]


def test_noms_de_societes_json_et_bruit_rejete(monkeypatch):
    from app.modules.analysis import service as A
    from app.shared import llm_client
    monkeypatch.setattr(llm_client, "generate",
                        lambda **k: type("R", (), {"text": '["Doctolib", "Alan", "(France). Highly recognized as a French", "paris"]'})())
    noms = A._noms_de_societes("Quels concurrents de Doctolib ?", {"company_name": "QA CV2 SAS"}, [])
    assert noms == ["QA CV2 SAS", "Doctolib", "Alan"]


def test_noms_de_societes_reponse_en_lignes_toujours_acceptee(monkeypatch):
    from app.modules.analysis import service as A
    from app.shared import llm_client
    monkeypatch.setattr(llm_client, "generate", lambda **k: type("R", (), {"text": "1. Swile\n2. Lydia\n"})())
    assert A._noms_de_societes("Concurrents ?", None, []) == ["Swile", "Lydia"]


def test_pappers_choisit_l_editeur_plutot_que_l_homonyme_sci():
    from app.shared.enrich.pappers import _score_candidat
    sci = {"siren": "1", "code_naf": "68.20B", "forme_juridique": "SCI, société civile immobilière", "effectif": "0 salarié"}
    editeur = {"siren": "2", "code_naf": "58.29C", "forme_juridique": "SAS", "effectif": "Entre 50 et 99 salariés"}
    assert max([sci, editeur], key=_score_candidat) is editeur


def test_grounding_garde_les_fiches_pappers_apres_le_classement(monkeypatch):
    from app.shared import grounding, search as web_search
    from app.shared.search.base import SearchResult
    web = [SearchResult(title=f"Article {i}", url=f"https://ex{i}.fr/a", snippet="texte", provider="exa") for i in range(5)]
    pappers = [SearchResult(title="Jenji", url="https://www.pappers.fr/entreprise/jenji-799321641", snippet="SAS créée en 2013", provider="pappers")]
    # Le reranker ne retient que les 3 premiers articles : la fiche est hors top_k.
    monkeypatch.setattr(web_search, "rerank_indices", lambda q, docs, k: [(0, .9), (1, .8), (2, .7)])
    contexte, citations = grounding.assemble("marché", web + pappers, [], top_k=3)
    assert [c["source"] for c in citations] == ["web", "web", "web", "pappers"]
    assert "(registre : pappers.fr)" in contexte
