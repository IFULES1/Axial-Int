"""P6 tests: PII redaction/guard + watch scheduling + route wiring."""
import datetime as dt

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.modules.pii import client as pii
from app.modules.pii.redaction import redact, restore

client = TestClient(app)


def test_redact_and_restore_roundtrip():
    text = "Contacte jean@acme.com ou +33 6 12 34 56 78 pour l'IBAN FR76 3000 4000 0512 3456 7890 143."
    redacted, mapping = redact(text)
    assert "jean@acme.com" not in redacted
    assert "[EMAIL_1]" in redacted
    assert "[PHONE_FR_1]" in redacted
    assert "[IBAN_1]" in redacted
    assert restore(redacted, mapping) == text


def test_guard_off_is_passthrough(monkeypatch):
    monkeypatch.setenv("PII_GUARD_MODE", "off")
    get_settings.cache_clear()
    assert pii.guard_outbound("mail me at a@b.com") == "mail me at a@b.com"
    get_settings.cache_clear()


def test_guard_enforce_redacts(monkeypatch):
    monkeypatch.setenv("PII_GUARD_MODE", "enforce")
    get_settings.cache_clear()
    out = pii.guard_outbound("écris à a@b.com")
    assert "a@b.com" not in out
    assert "[EMAIL_1]" in out
    get_settings.cache_clear()


def test_guard_shadow_sends_original(monkeypatch):
    monkeypatch.setenv("PII_GUARD_MODE", "shadow")
    get_settings.cache_clear()
    assert pii.guard_outbound("a@b.com") == "a@b.com"
    get_settings.cache_clear()


def test_watch_scheduling_math():
    from app.modules.watches.service import _next_run

    base = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    assert _next_run("daily", base) == base + dt.timedelta(days=1)
    assert _next_run("weekly", base) == base + dt.timedelta(weeks=1)
    assert _next_run("manual", base) is None


def test_watches_routes_mounted():
    paths = client.get("/openapi.json").json()["paths"]
    for p in ["/watches", "/watches/{watch_id}/run", "/watches/{watch_id}/pause"]:
        assert p in paths
    assert client.get("/watches").status_code in (401, 403)
