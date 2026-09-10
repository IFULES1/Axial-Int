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
