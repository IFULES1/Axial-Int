"""Webhook Resend (`POST /track/resend`) : signature, clics, plaintes, rebonds.

Le webhook écrit en base sur la foi d'un appel entrant : la signature Svix
est la seule chose qui distingue Resend d'un inconnu. D'où des tests qui
couvrent d'abord les refus, puis les écritures.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.modules.emailing.models import EmailSend, EmailSuppression

SECRET = "whsec_" + base64.b64encode(b"secret-de-test-32-octets-exactement").decode()


def _signer(corps: bytes, msg_id="msg_1", horodatage=None, secret=SECRET) -> dict:
    horodatage = str(horodatage or int(time.time()))
    cle = base64.b64decode(secret.split("_", 1)[1])
    sig = base64.b64encode(hmac.new(
        cle, f"{msg_id}.{horodatage}.".encode() + corps, hashlib.sha256).digest()).decode()
    return {"svix-id": msg_id, "svix-timestamp": horodatage,
            "svix-signature": f"v1,{sig}", "content-type": "application/json"}


@pytest.fixture
def env(monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "resend_webhook_secret", SECRET)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    EmailSend.__table__.create(engine)
    EmailSuppression.__table__.create(engine)
    with Session(engine) as db:
        db.add(EmailSend(token="t1", email="a@exemple.fr", campaign="c", provider_id="re_1"))
        db.commit()

    def _db():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_db] = _db
    yield TestClient(app), engine
    app.dependency_overrides.clear()


def _poster(client, evt: dict, **kw):
    corps = json.dumps(evt).encode()
    return client.post("/track/resend", content=corps, headers=_signer(corps, **kw))


def test_signature_absente_ou_fausse_refusee(env):
    client, engine = env
    corps = json.dumps({"type": "email.clicked", "data": {"email_id": "re_1"}}).encode()
    assert client.post("/track/resend", content=corps).status_code == 401
    faux = _signer(corps, secret="whsec_" + base64.b64encode(b"autre-secret").decode())
    assert client.post("/track/resend", content=corps, headers=faux).status_code == 401
    with Session(engine) as db:
        assert db.get(EmailSend, db.query(EmailSend).one().id).click_count == 0


def test_evenement_trop_ancien_refuse(env):
    client, _ = env
    r = _poster(client, {"type": "email.clicked", "data": {"email_id": "re_1"}},
                horodatage=int(time.time()) - 600)
    assert r.status_code == 401


def test_clic_enregistre_et_compte(env):
    client, engine = env
    for _ in range(2):
        assert _poster(client, {"type": "email.clicked", "data": {"email_id": "re_1"}}).status_code == 200
    with Session(engine) as db:
        row = db.query(EmailSend).one()
        assert row.click_count == 2
        assert row.clicked_at is not None


def test_plainte_met_en_liste_de_suppression(env):
    client, engine = env
    assert _poster(client, {"type": "email.complained", "data": {"email_id": "re_1"}}).status_code == 200
    with Session(engine) as db:
        assert db.get(EmailSuppression, "a@exemple.fr").reason == "plainte pour spam"


def test_rebond_temporaire_ignore_rebond_definitif_supprime(env):
    client, engine = env
    _poster(client, {"type": "email.bounced",
                     "data": {"email_id": "re_1", "bounce": {"type": "Transient"}}})
    with Session(engine) as db:
        assert db.get(EmailSuppression, "a@exemple.fr") is None
    _poster(client, {"type": "email.bounced",
                     "data": {"email_id": "re_1", "bounce": {"type": "Permanent"}}})
    with Session(engine) as db:
        assert db.get(EmailSuppression, "a@exemple.fr").reason == "rebond définitif"


def test_evenement_inconnu_acquitte(env):
    client, _ = env
    r = _poster(client, {"type": "email.delivery_delayed", "data": {"email_id": "re_inconnu"}})
    assert r.status_code == 200
