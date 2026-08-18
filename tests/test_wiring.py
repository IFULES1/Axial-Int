"""Tests for the billing/reports/analytics wiring into the analysis flow.

Uses an in-memory SQLite session so the credit + report tables are real, but no
external providers are called (web-search forced unavailable → degraded path).
"""
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.modules.analysis import service as analysis
from app.modules.analysis.service import AnalysisResult
from app.modules.billing import service as billing


@pytest.fixture
def db():
    # SQLite in-memory; JSONB columns degrade to JSON under SQLite fine for these.
    engine = create_engine("sqlite://", future=True)
    import app.modules.billing.models  # noqa: F401
    import app.modules.reports.models  # noqa: F401
    Base.metadata.create_all(engine, tables=[
        Base.metadata.tables["credit_balances"],
        Base.metadata.tables["reports"],
    ])
    with Session(engine) as s:
        yield s


def test_new_user_gets_free_beta(db):
    uid = str(uuid.uuid4())
    bal = billing.get_or_create_balance(db, uid)
    assert bal.trial_credits == billing.FREE_BETA_CREDITS
    assert billing.available_credits(bal) == billing.FREE_BETA_CREDITS


def test_finalize_charges_and_archives_on_success(db):
    uid = str(uuid.uuid4())
    billing.get_or_create_balance(db, uid)
    # The Free Beta grant (20) doesn't cover an etude_marche (40) — top up first.
    billing.grant_purchased(db, uid, 50)
    result = AnalysisResult(analysis_type="etude_marche", title="T", content="Corps",
                            degraded=False)
    info = analysis.finalize(db, uid, "etude_marche", result, is_admin=False)
    assert info["charged"] == 40                      # etude_marche cost
    assert info["report_id"] is not None
    bal = billing.get_or_create_balance(db, uid)
    assert billing.available_credits(bal) == billing.FREE_BETA_CREDITS + 50 - 40


def test_degraded_is_free_and_not_archived(db):
    uid = str(uuid.uuid4())
    billing.get_or_create_balance(db, uid)
    result = AnalysisResult(analysis_type="etude_marche", title="T",
                            content="⚠️ indispo", degraded=True)
    info = analysis.finalize(db, uid, "etude_marche", result, is_admin=False)
    assert info["charged"] == 0
    assert info["report_id"] is None
    bal = billing.get_or_create_balance(db, uid)
    assert billing.available_credits(bal) == billing.FREE_BETA_CREDITS  # untouched


def test_admin_bypasses_charge(db):
    uid = str(uuid.uuid4())
    billing.get_or_create_balance(db, uid)
    result = AnalysisResult(analysis_type="etude_marche", title="T", content="Corps",
                            degraded=False)
    info = analysis.finalize(db, uid, "etude_marche", result, is_admin=True)
    assert info["charged"] == 0
    bal = billing.get_or_create_balance(db, uid)
    assert billing.available_credits(bal) == billing.FREE_BETA_CREDITS
