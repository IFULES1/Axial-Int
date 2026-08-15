"""P7 tests: veille — skills, cumulative engine parsing, RSS dedup, email, PDF watermark.

Pure/logic tests only (no DB, no network): the engine's LLM call and Cohere rerank
are monkeypatched, and feedparser is stubbed, so these run fast and deterministically.
"""
import datetime as dt
import time

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# --- Skills catalogue --------------------------------------------------------

def test_skills_catalogue_and_fallback():
    from app.modules.watches import skills

    keys = {s.key for s in skills.list_skills()}
    assert keys == {"concurrentielle", "reglementaire", "financement", "produit_tech", "marche"}
    assert skills.get_skill("financement").key == "financement"
    # concurrentielle now reads broad categories (product/tech/funding feed into competitive intel)
    assert {"produit", "tech", "financement"} <= set(skills.get_skill("concurrentielle").rss_categories)
    assert skills.get_skill("inconnu").key == skills.DEFAULT_SKILL  # unknown → default


# --- Engine: delimiter parsing ----------------------------------------------

def test_engine_parse_full():
    from app.modules.watches.engine import _parse

    text = (
        "===HAD_CHANGES===\noui\n"
        "===DELTA===\n- Signal A [1]\n"
        "===FULL_REPORT===\n# Rapport\nDétail complet.\n"
        "===ROLLING_STATE===\nÉtat mémoire."
    )
    p = _parse(text)
    assert p["had_changes"] is True
    assert "Signal A" in p["delta"]
    assert "Rapport" in p["full_report"]
    assert p["rolling_state"] == "État mémoire."


def test_engine_parse_no_changes():
    from app.modules.watches.engine import _parse

    text = ("===HAD_CHANGES===\nnon\n===DELTA===\nRien de neuf.\n"
            "===FULL_REPORT===\nStable.\n===ROLLING_STATE===\nx")
    assert _parse(text)["had_changes"] is False


def test_engine_parse_fallback_plain_text():
    from app.modules.watches.engine import _parse

    p = _parse("Texte libre sans marqueurs.")
    assert p["full_report"] == "Texte libre sans marqueurs."
    assert p["delta"] == ""


def test_generate_veille_mirrors_empty_full(monkeypatch):
    from app.modules.watches import engine, skills

    class _Res:
        text = ("===HAD_CHANGES===\noui\n===DELTA===\nNouveau signal X\n"
                "===FULL_REPORT===\n\n===ROLLING_STATE===\nmémoire compacte")

    monkeypatch.setattr("app.shared.llm_client.generate", lambda **kw: _Res())
    out = engine.generate_veille(
        skill=skills.get_skill("concurrentielle"), subject="fintech",
        rolling_state=None, rss_articles=[], web_results=[], company_context="",
    )
    # full_report was empty → mirrored from delta; rolling_state carried through
    assert "Nouveau signal X" in out["full_report"]
    assert out["rolling_state"] == "mémoire compacte"


# --- RSS: freshness + dedup --------------------------------------------------

class _Entry:
    def __init__(self, link, title, ts):
        self.link, self.title, self.summary = link, title, "résumé"
        self.published_parsed = time.gmtime(ts)


class _Parsed:
    def __init__(self, entries):
        self.entries = entries
        self.feed = type("F", (), {"title": "Feed"})()


class _Feed:
    url = "http://feed.example/rss"
    title = "Feed"


def test_rss_filters_old_and_dedupes(monkeypatch):
    from app.modules.watches import rss

    now = time.time()
    entries = [_Entry("http://a", "A", now), _Entry("http://b", "B", now - 100_000)]
    monkeypatch.setattr("feedparser.parse", lambda url: _Parsed(entries))

    since = dt.datetime.fromtimestamp(now - 3600, tz=dt.timezone.utc)
    fresh = rss.fetch_new_articles([_Feed()], since=since, seen_urls=set())
    urls = {a["url"] for a in fresh}
    assert "http://a" in urls and "http://b" not in urls  # old entry filtered out

    deduped = rss.fetch_new_articles([_Feed()], since=None, seen_urls={"http://a"})
    assert "http://a" not in {a["url"] for a in deduped}   # already-seen excluded


def test_rss_broken_feed_is_soft(monkeypatch):
    from app.modules.watches import rss

    def _boom(url):
        raise RuntimeError("bad feed")

    monkeypatch.setattr("feedparser.parse", _boom)
    assert rss.fetch_new_articles([_Feed()], since=None, seen_urls=set()) == []


# --- Email rendering ---------------------------------------------------------

def test_md_to_html_renders_structure():
    from app.modules.watches.email import _md_to_html

    h = _md_to_html("# Titre\n## Section\n- **gras**\n- item\n\n---\n\nparagraphe")
    assert "<h1>Titre</h1>" in h and "<h2>Section</h2>" in h
    assert "<strong>gras</strong>" in h and "<ul>" in h and "<hr>" in h


def test_send_email_no_recipients_is_false():
    from app.modules.watches.email import send_email

    assert send_email([], "sujet", "corps") is False


# --- PDF watermark -----------------------------------------------------------

def test_pdf_valid_with_watermark_when_asset_present():
    from app.modules.reports import pdf

    reader = pdf._watermark_reader()          # None if the brand asset is absent
    out = pdf.render_pdf("Veille", "# Titre\n\n## Section\n- point")
    assert out[:5] == b"%PDF-"
    assert len(out) > 800
    if reader is not None:                     # asset present → image embedded, PDF is heavier
        assert len(out) > 50_000


# --- Route wiring ------------------------------------------------------------

def test_veille_routes_mounted():
    paths = client.get("/openapi.json").json()["paths"]
    for p in ("/watches/skills", "/watches/feeds", "/watches/{watch_id}/runs"):
        assert p in paths
    assert client.get("/watches/skills").status_code == 200          # public
    assert client.get("/watches/feeds").status_code in (401, 403)    # auth required
