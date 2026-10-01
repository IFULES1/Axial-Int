"""Synchronisation des abonnements via le webhook Stripe.

Jusqu'au 01/10/2026, le webhook ne traitait que les paiements réussis : une
résiliation (Clover, 29/09) ou un échec de paiement ne remontait jamais, et
l'app gardait l'abonnement « en essai ». Ces tests verrouillent la prise en
compte des changements d'état.
"""
from __future__ import annotations

import pytest

from app.modules.billing import stripe_gateway

UID = "5a3c8601-45f3-4b2e-9326-5096475c89b3"


@pytest.fixture
def evenement(monkeypatch):
    """Fait passer `construct_event` pour un événement Stripe signé."""
    import stripe

    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "stripe_webhook_secret", "whsec_test")
    courant = {}

    def construire(payload, signature, secret):
        return courant["evt"]

    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(construire))

    def poser(etype, obj):
        courant["evt"] = {"type": etype, "data": {"object": obj}}
        return stripe_gateway.parse_webhook(b"{}", "sig")

    return poser


@pytest.mark.parametrize("etype", ["customer.subscription.updated",
                                   "customer.subscription.deleted"])
def test_changement_d_abonnement_demande_une_resynchronisation(evenement, etype):
    grant = evenement(etype, {"id": "sub_1", "metadata": {"user_id": UID}})
    assert grant == {"kind": "subscription_state", "user_id": UID, "subscription_id": "sub_1"}


def test_abonnement_sans_utilisateur_ignore(evenement):
    assert evenement("customer.subscription.deleted", {"id": "sub_1", "metadata": {}}) is None


def test_echec_de_paiement_demande_une_resynchronisation(evenement, monkeypatch):
    import stripe

    monkeypatch.setattr(stripe.Subscription, "retrieve",
                        staticmethod(lambda sid: {"id": sid, "metadata": {"user_id": UID}}))
    grant = evenement("invoice.payment_failed", {"subscription": "sub_9"})
    assert grant == {"kind": "subscription_state", "user_id": UID, "subscription_id": "sub_9"}


def test_le_webhook_recopie_l_etat_reel_de_stripe(monkeypatch):
    """L'état écrit est celui que Stripe renvoie au moment du traitement, pas
    celui de l'événement : un événement « updated » arrivé après « deleted »
    ne doit pas ressusciter un abonnement résilié."""
    from fastapi.testclient import TestClient

    from app.db import get_db
    from app.main import app
    from app.modules.billing import router as billing_router

    ecrit = {}
    monkeypatch.setattr(billing_router.stripe_gateway, "parse_webhook",
                        lambda p, s: {"kind": "subscription_state", "user_id": UID,
                                      "subscription_id": "sub_1"})
    monkeypatch.setattr(billing_router.stripe_gateway, "fetch_subscription_state",
                        lambda sid: {"stripe_subscription_id": sid, "status": "canceled",
                                     "cancel_at_period_end": False})
    monkeypatch.setattr(billing_router.service, "upsert_subscription",
                        lambda db, uid, **f: ecrit.update(uid=uid, **f))
    app.dependency_overrides[get_db] = lambda: None
    try:
        r = TestClient(app).post("/billing/webhook", content=b"{}",
                                 headers={"stripe-signature": "sig"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert ecrit == {"uid": UID, "stripe_subscription_id": "sub_1", "status": "canceled",
                     "cancel_at_period_end": False}
