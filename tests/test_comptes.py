"""La frontière « compte interne » sert à deux choses qui doivent rester
d'accord : exclure des statistiques d'activation, et dispenser de l'écran carte.
"""
from app.modules.metrics.service import INTERNES
from app.shared.comptes import DOMAINES_INTERNES, est_interne


def test_les_domaines_maison_sont_internes():
    assert est_interne("miradie.buranturu@axial-ia.fr")
    assert est_interne("tiphanie.doye@axial-ia.fr")
    assert est_interne("carte-check-1@axial-qa.fr")


def test_les_comptes_clients_ne_le_sont_pas():
    assert not est_interne("christian@eqonx.com")
    assert not est_interne("idfinance.conseils@creative-cluster.org")
    assert not est_interne(None)
    assert not est_interne("")


def test_le_domaine_doit_etre_le_domaine_pas_un_suffixe():
    """« axial-ia.fr » collé à un autre nom de domaine reste un tiers.
    Un motif SQL en `%axial-ia.fr` laissait passer ce cas."""
    assert not est_interne("contact@faux-axial-ia.fr")
    assert not est_interne("contact@axial-ia.fr.example.com")


def test_les_motifs_sql_derivent_de_la_meme_liste():
    assert INTERNES == tuple(f"%@{d}" for d in DOMAINES_INTERNES)


def test_le_suivi_des_utilisateurs_est_reserve_a_l_administration():
    """L'onglet Suivi expose l'email et l'activité de chaque compte : un
    utilisateur ordinaire qui appelle la route directement doit être refusé
    avant toute requête en base."""
    from fastapi.testclient import TestClient

    from app.db import get_db
    from app.main import app
    from app.modules.auth.schemas import AuthUser
    from app.modules.auth.security import get_current_user

    class BaseInterdite:
        def execute(self, *a, **k):
            raise AssertionError("la base ne doit pas être interrogée")

    app.dependency_overrides[get_current_user] = lambda: AuthUser(
        id="00000000-0000-0000-0000-000000000001", email="client@exemple.fr", is_admin=False)
    app.dependency_overrides[get_db] = BaseInterdite
    try:
        r = TestClient(app).get("/metrics/suivi")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 403
