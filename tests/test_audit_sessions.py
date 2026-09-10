"""Garde-fous posés lors de l'audit du 04/09.

Trois bugs de session et de journalisation, chacun verrouillé par un test :
le client Supabase du serveur ne doit détenir aucune session, la clé d'API ne
doit jamais atteindre les journaux, et une conversation prend pour titre la
première question posée.
"""
import httpx

from app.modules.auth import supabase_client
from app.modules.intelligence.service import TITRES_GENERIQUES, titre_depuis
from app.shared.llm_client import _sans_secret


def test_le_client_supabase_ne_rafraichit_jamais_de_session_cote_serveur():
    """Sinon supabase-py arme un minuteur qui fait tourner le jeton de
    l'utilisateur côté serveur, et le navigateur se retrouve déconnecté au
    bout d'une heure avec un refresh token déjà consommé."""
    opts = supabase_client._SANS_SESSION
    assert opts.auto_refresh_token is False
    assert opts.persist_session is False


def test_le_client_partage_oublie_la_session_apres_usage():
    """`persist_session=False` ne vide pas la mémoire du client : sans cet
    oubli explicite, le client commun se souviendrait du dernier connecté."""
    class _Auth:
        def __init__(self):
            self._in_memory_session = object()
            self.appels = 0

        def _remove_session(self):
            self._in_memory_session = None
            self.appels += 1

    class _Client:
        auth = _Auth()

    client = _Client()
    supabase_client.oublier_session(client)
    assert client.auth._in_memory_session is None
    assert client.auth.appels == 1


def test_la_cle_api_est_masquee_dans_les_journaux():
    url = "https://generativelanguage.googleapis.com/v1beta/models/x:streamGenerateContent?alt=sse&key=AQ.SECRET123"
    # Message tel que httpx le construit réellement : l'URL, clé comprise, est
    # dans le texte — c'est ce texte qui partait dans le journal.
    err = httpx.HTTPStatusError(f"Server error '503 Service Unavailable' for url '{url}'",
                                request=httpx.Request("POST", url),
                                response=httpx.Response(503))
    texte = _sans_secret(err)
    assert "SECRET123" not in texte
    assert "key=<masqué>" in texte
    assert "alt=sse" in texte  # le reste de l'URL reste lisible pour le diagnostic


def test_les_autres_parametres_ne_sont_pas_masques():
    assert _sans_secret(ValueError("https://x/y?alt=sse&page=2")) == "https://x/y?alt=sse&page=2"


def test_titre_depuis_la_question():
    assert titre_depuis("Quels sont mes concurrents directs ?") == "Quels sont mes concurrents directs ?"
    assert titre_depuis("  plusieurs   espaces \n et retours ") == "plusieurs espaces et retours"
    assert titre_depuis("") == "Conversation"


def test_titre_long_coupe_sur_un_mot():
    long = "Comment préparer ma prochaine levée de fonds en série A avec un fonds européen spécialisé deeptech ?"
    t = titre_depuis(long)
    assert t.endswith("…")
    assert len(t) <= 81
    assert not t[:-1].endswith(" ")  # jamais coupé au milieu d'un mot


def test_les_titres_generiques_sont_reconnus():
    for t in ("Workspace", "workspace", "Nouvelle conversation", "", "  "):
        assert t.strip().lower() in TITRES_GENERIQUES
    assert "Test langue" .lower() not in TITRES_GENERIQUES
