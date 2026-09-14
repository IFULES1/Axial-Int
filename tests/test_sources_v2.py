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


def test_propagation_tavily_days_si_fraicheur_inferieure_365(monkeypatch):
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
    TavilyProvider().search("marché IA", 10, contraintes=_contraintes_test(fraicheur_jours=90))
    body = captured["json"]
    assert body["days"] == 90
    assert "time_range" not in body
    assert body["include_domains"] == ["legifrance.gouv.fr"]
    assert "exclude_domains" not in body
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


def test_propagation_tavily_365_jours_utilise_days(monkeypatch):
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
    assert captured["json"]["days"] == 365
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
    assert compteur["ecartes"] == 2
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
    assert compteur["ecartes"] == 2
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
    assert compteur.get("ecartes", 0) == 0
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
    assert compteur.get("ecartes", 0) == 0
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
    assert compteur["ecartes"] == 2
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
