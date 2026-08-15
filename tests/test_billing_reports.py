"""P5 tests: credit costs/aliases, PDF generation, route wiring (no DB/Stripe)."""
from fastapi.testclient import TestClient

from app.main import app
from app.modules.billing.catalog import PLANS, cost_for
from app.modules.reports.pdf import render_pdf

client = TestClient(app)


def test_cost_canonical_and_aliases():
    assert cost_for("etude_marche") == 40
    assert cost_for("market_study") == 40          # alias
    assert cost_for("analyse_concurrentielle") == 25
    assert cost_for("competition") == 25           # alias
    assert cost_for("agent_message") == 2
    assert cost_for("unknown_thing") == 25         # default


def test_plans_present():
    keys = {p["key"] for p in PLANS}
    assert keys == {"free_beta", "solo_founder", "startup_pro", "enterprise"}
    assert cost_for("run_agent_veille") == 5


def test_pdf_is_generated():
    pdf = render_pdf("Étude de marché — Fintech", "# Titre\n\n## Section\n- point 1\n- **gras**\n\nParagraphe.")
    assert pdf[:5] == b"%PDF-"      # valid PDF magic number
    assert len(pdf) > 800


def test_billing_reports_routes_mounted():
    paths = client.get("/openapi.json").json()["paths"]
    for p in ["/billing/plans", "/billing/balance", "/billing/checkout",
              "/billing/webhook", "/reports", "/reports/{report_id}",
              "/reports/{report_id}/pdf"]:
        assert p in paths, p
    assert client.get("/billing/plans").status_code == 200          # public
    assert client.get("/billing/balance").status_code in (401, 403)  # protected
    assert client.get("/reports").status_code in (401, 403)          # protected
