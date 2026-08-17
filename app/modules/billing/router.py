"""Billing endpoints — plans, balance, credit check, checkout, webhook."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
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


class CheckoutIn(BaseModel):
    pack: str
    success_url: str
    cancel_url: str


class SubscribeIn(BaseModel):
    plan: str
    success_url: str
    cancel_url: str


@router.get("/plans")
def plans() -> dict:
    return {"plans": PLANS, "packs": stripe_gateway.CREDIT_PACKS}


@router.get("/balance", response_model=BalanceOut)
def balance(user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)) -> BalanceOut:
    b = service.get_or_create_balance(db, user.id)
    return BalanceOut(
        available=service.available_credits(b), trial_credits=b.trial_credits,
        free_credits=b.free_credits, purchased_credits=b.purchased_credits,
        trial_active=service._trial_active(b),
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
        user.id, payload.plan, payload.success_url, payload.cancel_url
    )
    return {"checkout_url": url}


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    grant = stripe_gateway.parse_webhook(payload, signature)
    if grant:
        if grant.get("kind") == "subscription":
            # Monthly allowance: reset (renew), don't accumulate.
            service.grant_subscription(db, grant["user_id"], grant["credits"])
        else:
            # PAYG pack: accumulate, never expire.
            service.grant_purchased(db, grant["user_id"], grant["credits"])
        return {"granted": grant["credits"], "user_id": grant["user_id"],
                "kind": grant.get("kind", "pack")}
    return {"ignored": True}
