"""Billing service: balance lifecycle, atomic credit consumption, grants.

New users are lazily initialised with the Free Beta grant (120 credits / 14 days).
Consumption is atomic: the balance row is locked FOR UPDATE so concurrent
analyses can't double-spend. Order: trial (expiring) → free → purchased.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.modules.billing.catalog import cost_for
from app.modules.billing.models import CreditBalance

FREE_BETA_CREDITS = 120
FREE_BETA_DAYS = 14


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


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

    db.commit()
    db.refresh(balance)
    return {"charged": cost, "action": action, "remaining": available_credits(balance)}


def grant_purchased(db: Session, user_id: str, amount: int) -> CreditBalance:
    """Add purchased credits (e.g. from a Stripe webhook). Never expire."""
    balance = get_or_create_balance(db, user_id)
    balance.purchased_credits += amount
    db.commit()
    db.refresh(balance)
    return balance
