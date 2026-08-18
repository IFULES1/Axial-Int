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
        # Subscriptions: credits arrive via invoice.paid — here we only capture
        # the Stripe ids so the app can mirror the subscription state.
        if obj.get("mode") == "subscription":
            meta = obj.get("metadata") or {}
            if not meta.get("user_id"):
                return None
            return {"kind": "subscription_started", "user_id": meta["user_id"],
                    "customer_id": obj.get("customer"),
                    "subscription_id": obj.get("subscription")}
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
                "kind": "subscription", "subscription_id": sub_id,
                "customer_id": obj.get("customer")}

    return None


# --- État d'abonnement, factures, portail ------------------------------------

def _period_end_dt(sub) -> "object":
    import datetime as dt

    # L'API Stripe récente porte current_period_end sur les ITEMS de
    # l'abonnement (plus sur l'abonnement lui-même) ; en essai, trial_end
    # est la date du premier prélèvement.
    ts = sub.get("current_period_end") or sub.get("trial_end")
    if not ts:
        items = ((sub.get("items") or {}).get("data") or [])
        if items:
            ts = items[0].get("current_period_end")
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc) if ts else None


def fetch_subscription_state(subscription_id: str) -> dict | None:
    """Live Stripe state for one subscription → app-side mirror fields."""
    stripe = _stripe()
    try:
        sub = stripe.Subscription.retrieve(subscription_id)
    except Exception:
        logger.warning("Subscription %s introuvable", subscription_id, exc_info=True)
        return None
    meta = sub.get("metadata") or {}
    return {
        "stripe_subscription_id": sub["id"],
        "stripe_customer_id": sub.get("customer"),
        "plan_key": meta.get("plan"),
        "status": sub.get("status") or "none",
        "cancel_at_period_end": bool(sub.get("cancel_at_period_end")),
        "current_period_end": _period_end_dt(sub),
    }


def find_subscription_for_user(user_id: str) -> dict | None:
    """Backfill: locate a user's subscription by metadata (accounts created
    before the app started mirroring subscriptions)."""
    stripe = _stripe()
    try:
        res = stripe.Subscription.search(
            query=f"metadata['user_id']:'{user_id}'", limit=5
        )
        subs = list(res.get("data") or [])
    except Exception:
        logger.warning("Subscription search indisponible", exc_info=True)
        return None
    if not subs:
        return None
    # Privilégier un abonnement vivant ; sinon le plus récent.
    alive = [s for s in subs if s.get("status") in ("trialing", "active", "past_due")]
    chosen = (alive or sorted(subs, key=lambda s: s.get("created", 0), reverse=True))[0]
    return fetch_subscription_state(chosen["id"])


def list_invoices(customer_id: str, limit: int = 12) -> list[dict]:
    """Factures Stripe du client — liens de téléchargement directs."""
    import datetime as dt
    stripe = _stripe()
    try:
        res = stripe.Invoice.list(customer=customer_id, limit=limit)
    except Exception:
        logger.warning("Liste factures indisponible", exc_info=True)
        return []
    out = []
    for inv in res.get("data") or []:
        out.append({
            "id": inv["id"],
            "number": inv.get("number"),
            "date": dt.datetime.fromtimestamp(inv["created"], dt.timezone.utc).isoformat(),
            "amount_eur": (inv.get("amount_paid") or inv.get("amount_due") or 0) / 100,
            "status": inv.get("status"),
            "url": inv.get("hosted_invoice_url"),
            "pdf": inv.get("invoice_pdf"),
        })
    return out


def create_portal_session(customer_id: str, return_url: str) -> str:
    """Portail client Stripe : gérer carte, annuler, télécharger les factures."""
    stripe = _stripe()
    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id, return_url=return_url
        )
        return session.url
    except Exception as e:
        raise AppError("Portail de facturation indisponible — active le Customer "
                       "Portal dans le dashboard Stripe (Settings → Billing).",
                       503, code="portal_unavailable") from e
