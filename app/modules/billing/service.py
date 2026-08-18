"""Billing service: balance lifecycle, atomic credit consumption, grants.

New users are lazily initialised with the Free Beta grant (20 credits / 14 days).
Consumption is atomic: the balance row is locked FOR UPDATE so concurrent
analyses can't double-spend. Order: trial (expiring) → free (monthly plan) →
purchased (PAYG, never expire).

Credit buckets:
  * trial_credits     — Free Beta welcome grant, expires after FREE_BETA_DAYS.
  * free_credits      — monthly subscription allowance; RESET (not added) on each
                        Stripe invoice so plan credits renew monthly and don't stack.
  * purchased_credits — pay-as-you-go packs; never expire, accumulate.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.modules.billing.catalog import cost_for
from app.modules.billing.models import CreditBalance, CreditEvent, UserSubscription

FREE_BETA_CREDITS = 20
FREE_BETA_DAYS = 14


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _log_event(db: Session, user_id: str, delta: int, action: str) -> None:
    """Append a ledger row (committed with the caller's transaction)."""
    db.add(CreditEvent(user_id=uuid.UUID(user_id), delta=delta, action=action))


def _as_aware(value: dt.datetime | None) -> dt.datetime | None:
    """Normalize to tz-aware UTC. Backends without tz (SQLite) return naive."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value


def _trial_active(balance: CreditBalance) -> bool:
    expires = _as_aware(balance.trial_expires_at)
    return bool(balance.trial_credits > 0 and expires and expires > _now())


def available_credits(balance: CreditBalance) -> int:
    trial = balance.trial_credits if _trial_active(balance) else 0
    return trial + balance.free_credits + balance.purchased_credits


def get_or_create_balance(db: Session, user_id: str) -> CreditBalance:
    uid = uuid.UUID(user_id)
    balance = db.get(CreditBalance, uid)
    if balance is None:
        balance = CreditBalance(
            user_id=uid,
            trial_credits=FREE_BETA_CREDITS,
            trial_expires_at=_now() + dt.timedelta(days=FREE_BETA_DAYS),
        )
        db.add(balance)
        _log_event(db, user_id, FREE_BETA_CREDITS, "essai_bienvenue")
        db.commit()
        db.refresh(balance)
    return balance


def check_credits(db: Session, user_id: str, action: str) -> dict:
    balance = get_or_create_balance(db, user_id)
    cost = cost_for(action)
    avail = available_credits(balance)
    return {
        "action": action,
        "cost": cost,
        "available": avail,
        "affordable": avail >= cost,
        "trial_active": _trial_active(balance),
    }


def consume_credits(db: Session, user_id: str, action: str,
                    *, is_admin: bool = False) -> dict:
    """Atomically debit the cost of `action`. Admins bypass consumption."""
    cost = cost_for(action)
    if is_admin:
        return {"charged": 0, "action": action, "bypass": True}

    uid = uuid.UUID(user_id)
    get_or_create_balance(db, user_id)  # ensure row exists

    # Lock the row for the duration of the debit.
    balance = db.execute(
        select(CreditBalance).where(CreditBalance.user_id == uid).with_for_update()
    ).scalar_one()

    if available_credits(balance) < cost:
        db.rollback()
        raise AppError("Crédits insuffisants.", 402, code="insufficient_credits")

    remaining = cost
    if _trial_active(balance):
        take = min(balance.trial_credits, remaining)
        balance.trial_credits -= take
        remaining -= take
    if remaining and balance.free_credits:
        take = min(balance.free_credits, remaining)
        balance.free_credits -= take
        remaining -= take
    if remaining and balance.purchased_credits:
        take = min(balance.purchased_credits, remaining)
        balance.purchased_credits -= take
        remaining -= take

    _log_event(db, user_id, -cost, action)
    db.commit()
    db.refresh(balance)
    return {"charged": cost, "action": action, "remaining": available_credits(balance)}


def grant_purchased(db: Session, user_id: str, amount: int) -> CreditBalance:
    """Add PAYG pack credits (from a Stripe checkout). Never expire, accumulate."""
    balance = get_or_create_balance(db, user_id)
    balance.purchased_credits += amount
    _log_event(db, user_id, amount, "pack_credits")
    db.commit()
    db.refresh(balance)
    return balance


def grant_subscription(db: Session, user_id: str, monthly_credits: int) -> CreditBalance:
    """Set the monthly plan allowance (from a Stripe invoice.paid).

    SETS free_credits to the plan amount rather than adding, so subscription
    credits renew each month and don't stack — matching the product promise
    ("les crédits inclus se renouvellent chaque mois et ne s'accumulent pas").
    PAYG (purchased) credits are untouched.
    """
    balance = get_or_create_balance(db, user_id)
    balance.free_credits = monthly_credits
    _log_event(db, user_id, monthly_credits, "abonnement_mensuel")
    db.commit()
    db.refresh(balance)
    return balance


# --- Abonnement (miroir applicatif de Stripe) --------------------------------

def upsert_subscription(db: Session, user_id: str, **fields) -> UserSubscription:
    uid = uuid.UUID(user_id)
    sub = db.get(UserSubscription, uid)
    if sub is None:
        sub = UserSubscription(user_id=uid)
        db.add(sub)
    for k, v in fields.items():
        if v is not None:
            setattr(sub, k, v)
    db.commit()
    db.refresh(sub)
    return sub


def get_subscription(db: Session, user_id: str) -> UserSubscription | None:
    return db.get(UserSubscription, uuid.UUID(user_id))


def list_events(db: Session, user_id: str, limit: int = 50) -> list[CreditEvent]:
    stmt = (select(CreditEvent)
            .where(CreditEvent.user_id == uuid.UUID(user_id))
            .order_by(CreditEvent.created_at.desc())
            .limit(limit))
    return list(db.scalars(stmt))
