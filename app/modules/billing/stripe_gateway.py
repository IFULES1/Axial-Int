"""Stripe integration — checkout for credit packs + webhook verification.

Degrades cleanly: with no STRIPE_SECRET_KEY, checkout returns a clear 503 and
the webhook rejects unverified calls. Credit grants happen only on a verified
`checkout.session.completed` event.
"""
from __future__ import annotations

import logging

from app.config import get_settings
from app.errors import AppError

logger = logging.getLogger("axial.billing.stripe")

# One-time credit packs (credits, price in cents).
CREDIT_PACKS: dict[str, dict] = {
    "starter": {"credits": 50, "amount_cents": 2000, "label": "Starter — 50 crédits"},
    "boost": {"credits": 100, "amount_cents": 4000, "label": "Boost — 100 crédits"},
    "scale": {"credits": 200, "amount_cents": 8000, "label": "Scale — 200 crédits"},
}


def _stripe():
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise AppError("Paiement indisponible (Stripe non configuré).", 503,
                       code="stripe_unconfigured")
    import stripe

    stripe.api_key = settings.stripe_secret_key
    return stripe


def create_checkout_session(user_id: str, pack: str, success_url: str,
                            cancel_url: str) -> str:
    if pack not in CREDIT_PACKS:
        raise AppError("Pack inconnu.", 400, code="unknown_pack")
    stripe = _stripe()
    p = CREDIT_PACKS[pack]
    session = stripe.checkout.Session.create(
        mode="payment",
        success_url=success_url,
        cancel_url=cancel_url,
        line_items=[{
            "quantity": 1,
            "price_data": {
                "currency": "eur",
                "unit_amount": p["amount_cents"],
                "product_data": {"name": p["label"]},
            },
        }],
        metadata={"user_id": user_id, "pack": pack, "credits": str(p["credits"])},
    )
    return session.url


def create_subscription_session(user_id: str, plan_key: str, success_url: str,
                                cancel_url: str, trial_days: int = 0) -> str:
    """Recurring monthly subscription checkout via inline recurring price_data —
    no Stripe Product/Price needs to be created by hand.

    With trial_days > 0 (onboarding step 4): the card is collected now, 0€ is
    charged, and the first debit happens automatically at trial end. Stripe
    sends the legally required pre-debit reminder email.
    """
    from app.modules.billing.catalog import PLANS

    plan = next((p for p in PLANS if p["key"] == plan_key), None)
    if not plan or not plan.get("price_eur"):
        raise AppError("Plan inconnu ou non facturable.", 400, code="unknown_plan")
    stripe = _stripe()
    subscription_data: dict = {
        # Metadata on the SUBSCRIPTION too, so invoice.paid (renewals) can read it.
        "metadata": {"user_id": user_id, "plan": plan_key,
                     "credits": str(plan["monthly_credits"] or 0)},
    }
    if trial_days > 0:
        subscription_data["trial_period_days"] = trial_days
    session = stripe.checkout.Session.create(
        mode="subscription",
        success_url=success_url,
        cancel_url=cancel_url,
        line_items=[{
            "quantity": 1,
            "price_data": {
                "currency": "eur",
                "unit_amount": plan["price_eur"] * 100,
                "recurring": {"interval": "month"},
                "product_data": {"name": f"Axial {plan['name']}"},
            },
        }],
        subscription_data=subscription_data,
        metadata={"user_id": user_id, "plan": plan_key,
                  "credits": str(plan["monthly_credits"] or 0)},
    )
    return session.url


def parse_webhook(payload: bytes, signature: str) -> dict | None:
    """Verify the signature and return a grant instruction, or None to ignore."""
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise AppError("Webhook Stripe non configuré.", 503, code="stripe_unconfigured")
    import stripe

    if settings.stripe_secret_key:
        stripe.api_key = settings.stripe_secret_key
    try:
        event = stripe.Webhook.construct_event(
            payload, signature, settings.stripe_webhook_secret
        )
    except Exception as e:
        raise AppError("Signature webhook invalide.", 400, code="bad_signature") from e

    etype = event["type"]
    obj = event["data"]["object"]

    # One-time PAYG packs → grant on checkout completion (accumulate).
    if etype == "checkout.session.completed":
        # Subscriptions are credited via invoice.paid (fires for the 1st payment AND
        # every renewal), so skip subscription-mode checkouts to avoid double-granting.
        if obj.get("mode") == "subscription":
            return None
        meta = obj.get("metadata") or {}
        if not meta.get("user_id"):
            return None
        return {"user_id": meta["user_id"], "credits": int(meta.get("credits", 0)),
                "kind": "pack"}

    # Subscriptions (first payment + monthly renewals) → reset the plan allowance.
    if etype == "invoice.paid":
        # A trial start issues a 0€ invoice: no money moved, no credits granted.
        # Plan credits arrive with the first REAL debit at trial end.
        if not obj.get("amount_paid"):
            return None
        sub_id = obj.get("subscription")
        if not sub_id:
            return None
        try:
            meta = (stripe.Subscription.retrieve(sub_id).get("metadata") or {})
        except Exception:
            logger.warning("invoice.paid: subscription %s introuvable", sub_id, exc_info=True)
            return None
        if not meta.get("user_id"):
            return None
        return {"user_id": meta["user_id"], "credits": int(meta.get("credits", 0)),
                "kind": "subscription"}

    return None
