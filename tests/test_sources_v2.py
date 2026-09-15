"""Sources v2 — Task 1 : contraintes de recherche, propagation, filtre de
pertinence. Voir `docs/superpowers/specs/2026-09-14-sources-v2.md` §1.
"""
from __future__ import annotations

import dataclasses
import re

import pytest

from app.config import get_settings
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
    assert appels[0][1] == {"q": "Ma Société", "api_token": "cle-test", "par_page": 3}
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
