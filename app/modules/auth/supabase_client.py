"""Thin Supabase client accessors.

Two clients: a public (anon) client for password sign-in, and an admin
(service-role) client for user creation. Kept lazy so the app boots even when
Supabase is not configured (e.g. unit tests that never call these).
"""
from __future__ import annotations

from functools import lru_cache

from supabase import Client, ClientOptions, create_client

from app.config import get_settings
from app.errors import AppError

# Le serveur ne détient AUCUNE session : il relaie des jetons au navigateur.
# Par défaut, supabase-py garde la dernière session en mémoire et arme un
# minuteur qui la rafraîchit 10 s avant expiration — côté serveur, avec le
# jeton de l'utilisateur. Supabase fait alors tourner ce jeton, celui du
# navigateur devient périmé, et sa prochaine tentative de rafraîchissement
# est refusée : déconnexion sèche au bout d'une heure. Ces deux options
# coupent ce mécanisme ; le client redevient un simple relais sans état.
_SANS_SESSION = ClientOptions(auto_refresh_token=False, persist_session=False)


def oublier_session(client: Client) -> None:
    """Efface la session que supabase-py vient de ranger dans le client.

    `persist_session=False` ne l'empêche pas de garder la dernière session
    « en mémoire » — un client partagé entre toutes les requêtes se souviendrait
    donc du dernier utilisateur connecté. Rien côté serveur n'est révoqué :
    `sign_out` appellerait Supabase et invaliderait le jeton du navigateur.
    """
    retirer = getattr(client.auth, "_remove_session", None)
    if callable(retirer):
        retirer()


@lru_cache
def public_client() -> Client:
    s = get_settings()
    if not (s.supabase_url and s.supabase_anon_key):
        raise AppError("Supabase non configuré (URL/anon key).", 500,
                       code="auth_misconfigured")
    return create_client(s.supabase_url, s.supabase_anon_key, options=_SANS_SESSION)


@lru_cache
def admin_client() -> Client:
    s = get_settings()
    if not (s.supabase_url and s.supabase_service_key):
        raise AppError("Supabase non configuré (URL/service key).", 500,
                       code="auth_misconfigured")
    return create_client(s.supabase_url, s.supabase_service_key, options=_SANS_SESSION)
