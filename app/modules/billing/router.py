"""Billing endpoints — plans, balance, credit check, checkout, webhook."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.modules.auth.schemas import AuthUser
from app.modules.auth.security import get_current_user
from app.modules.billing import service, stripe_gateway
from app.modules.billing.catalog import PLANS

router = APIRouter(prefix="/billing", tags=["billing"])


class BalanceOut(BaseModel):
    available: int
    trial_credits: int
    free_credits: int
    purchased_credits: int
    trial_active: bool
    # `trial_active` exige des crédits restants : quelqu'un qui a tout dépensé
    # le jour 3 y serait « hors essai ». La PÉRIODE est une autre question, et
    # c'est elle qui décide si la carte peut encore être remise à plus tard.
    periode_essai_active: bool = False
    essai_expire_le: str | None = None


class CheckoutIn(BaseModel):
    pack: str
    success_url: str
    cancel_url: str


class SubscribeIn(BaseModel):
    plan: str
    success_url: str
    cancel_url: str
    # Onboarding step 4: card now, first debit after the trial (True → 14 days).
    trial: bool = False


@router.get("/plans")
def plans() -> dict:
    return {"plans": PLANS, "packs": stripe_gateway.CREDIT_PACKS}


@router.get("/balance", response_model=BalanceOut)
def balance(user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)) -> BalanceOut:
    b = service.get_or_create_balance(db, user.id)
    expire = service._as_aware(b.trial_expires_at)
    return BalanceOut(
        available=service.available_credits(b), trial_credits=b.trial_credits,
        free_credits=b.free_credits, purchased_credits=b.purchased_credits,
        trial_active=service._trial_active(b),
        periode_essai_active=bool(expire and expire > service._now()),
        essai_expire_le=expire.isoformat() if expire else None,
    )


@router.get("/check")
def check(action: str, user: AuthUser = Depends(get_current_user),
          db: Session = Depends(get_db)) -> dict:
    return service.check_credits(db, user.id, action)


@router.post("/checkout")
def checkout(payload: CheckoutIn, user: AuthUser = Depends(get_current_user)) -> dict:
    url = stripe_gateway.create_checkout_session(
        user.id, payload.pack, payload.success_url, payload.cancel_url
    )
    return {"checkout_url": url}


@router.post("/subscribe")
def subscribe(payload: SubscribeIn, user: AuthUser = Depends(get_current_user)) -> dict:
    url = stripe_gateway.create_subscription_session(
        user.id, payload.plan, payload.success_url, payload.cancel_url,
        trial_days=14 if payload.trial else 0,
    )
    return {"checkout_url": url}


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    grant = stripe_gateway.parse_webhook(payload, signature)
    if not grant:
        return {"ignored": True}

    kind = grant.get("kind", "pack")
    if kind == "subscription_started":
        # Carte posée (essai démarré) : on mémorise les ids + l'état Stripe.
        state = (stripe_gateway.fetch_subscription_state(grant["subscription_id"])
                 if grant.get("subscription_id") else None)
        service.upsert_subscription(
            db, grant["user_id"],
            **(state or {"stripe_customer_id": grant.get("customer_id"),
                         "stripe_subscription_id": grant.get("subscription_id"),
                         "status": "trialing"}),
        )
        return {"subscription": "started", "user_id": grant["user_id"]}

    if kind == "subscription":
        # Vrai débit mensuel : reset de l'enveloppe + rafraîchissement du miroir.
        service.grant_subscription(db, grant["user_id"], grant["credits"])
        state = (stripe_gateway.fetch_subscription_state(grant["subscription_id"])
                 if grant.get("subscription_id") else None)
        if state:
            service.upsert_subscription(db, grant["user_id"], **state)
    else:
        # PAYG pack: accumulate, never expire.
        service.grant_purchased(db, grant["user_id"], grant["credits"])
    return {"granted": grant["credits"], "user_id": grant["user_id"], "kind": kind}


def _sub_out(sub) -> dict:
    plan = next((p for p in PLANS if p["key"] == sub.plan_key), None) if sub.plan_key else None
    return {
        "active": sub.status in ("trialing", "active", "past_due"),
        "status": sub.status,
        "plan": sub.plan_key,
        "plan_name": plan["name"] if plan else None,
        "price_eur": plan["price_eur"] if plan else None,
        "monthly_credits": plan["monthly_credits"] if plan else None,
        "cancel_at_period_end": sub.cancel_at_period_end,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
    }


@router.get("/subscription")
def subscription(user: AuthUser = Depends(get_current_user),
                 db: Session = Depends(get_db)) -> dict:
    """Plan actuel + prochain prélèvement. Rafraîchit depuis Stripe ; backfille
    les comptes abonnés avant la mise en place du miroir."""
    sub = service.get_subscription(db, user.id)
    try:
        if sub and sub.stripe_subscription_id:
            state = stripe_gateway.fetch_subscription_state(sub.stripe_subscription_id)
            if state:
                sub = service.upsert_subscription(db, user.id, **state)
        elif sub is None:
            state = stripe_gateway.find_subscription_for_user(user.id)
            if state:
                sub = service.upsert_subscription(db, user.id, **state)
    except Exception:
        pass  # Stripe injoignable → on sert l'état stocké
    if sub is None:
        return {"active": False, "status": "none"}
    return _sub_out(sub)


@router.get("/history")
def history(user: AuthUser = Depends(get_current_user),
            db: Session = Depends(get_db)) -> list[dict]:
    """Historique de consommation/crédits (journal append-only)."""
    return [{"delta": e.delta, "action": e.action,
             "created_at": e.created_at.isoformat()}
            for e in service.list_events(db, user.id)]


@router.get("/invoices")
def invoices(user: AuthUser = Depends(get_current_user),
             db: Session = Depends(get_db)) -> list[dict]:
    """Factures Stripe (liens de téléchargement directs)."""
    sub = service.get_subscription(db, user.id)
    if not sub or not sub.stripe_customer_id:
        return []
    return stripe_gateway.list_invoices(sub.stripe_customer_id)


class PortalIn(BaseModel):
    return_url: str


@router.post("/portal")
def portal(payload: PortalIn, user: AuthUser = Depends(get_current_user),
           db: Session = Depends(get_db)) -> dict:
    """Portail client Stripe : gérer sa carte, annuler, factures."""
    sub = service.get_subscription(db, user.id)
    if not sub or not sub.stripe_customer_id:
        raise AppError("Aucun abonnement associé à ce compte.", 404, code="no_subscription")
    return {"portal_url": stripe_gateway.create_portal_session(
        sub.stripe_customer_id, payload.return_url)}
