"""Watch service: CRUD, scheduling math, and the run loop used by the worker."""
from __future__ import annotations

import datetime as dt
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.modules.watches.models import RssFeed, Watch, WatchRun

logger = logging.getLogger("axial.watches")

_CADENCE_DELTA = {
    "daily": dt.timedelta(days=1),
    "weekly": dt.timedelta(weeks=1),
}


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _next_run(cadence: str, base: dt.datetime | None = None) -> dt.datetime | None:
    delta = _CADENCE_DELTA.get(cadence)
    if delta is None:  # manual → no automatic scheduling
        return None
    return (base or _now()) + delta


# --- CRUD ------------------------------------------------------------------

def create_watch(db: Session, user_id: str, *, name: str, query: str,
                 analysis_type: str, cadence: str, skill: str = "concurrentielle",
                 email_recipients: list[str] | None) -> Watch:
    watch = Watch(
        id=uuid.uuid4(), user_id=uuid.UUID(user_id), name=name, query=query,
        analysis_type=analysis_type, cadence=cadence, skill=skill,
        email_recipients=email_recipients, next_run_at=_next_run(cadence),
    )
    db.add(watch)
    db.commit()
    db.refresh(watch)
    return watch


def list_watches(db: Session, user_id: str) -> list[Watch]:
    stmt = select(Watch).where(Watch.user_id == uuid.UUID(user_id)).order_by(Watch.created_at.desc())
    return list(db.scalars(stmt))


def list_runs(db: Session, user_id: str, watch_id: str, limit: int = 20) -> list[WatchRun]:
    """Dated finding history for one watch (newest first). Authz via ownership."""
    _own_watch(db, user_id, watch_id)
    stmt = (select(WatchRun).where(WatchRun.watch_id == uuid.UUID(watch_id))
            .order_by(WatchRun.created_at.desc()).limit(limit))
    return list(db.scalars(stmt))


def list_activity(db: Session, user_id: str, limit: int = 30) -> list:
    """Global run history across ALL the user's agents (newest first), with the
    agent name and its skill — the 'which skills ran' log."""
    stmt = (select(WatchRun, Watch.name, Watch.skill)
            .join(Watch, Watch.id == WatchRun.watch_id)
            .where(Watch.user_id == uuid.UUID(user_id))
            .order_by(WatchRun.created_at.desc()).limit(limit))
    return list(db.execute(stmt).all())


def _feeds_for(db: Session, user_id: str, categories: list[str]) -> list[RssFeed]:
    stmt = select(RssFeed).where(RssFeed.user_id == uuid.UUID(user_id), RssFeed.active.is_(True))
    if categories:
        stmt = stmt.where(RssFeed.category.in_(categories))
    return list(db.scalars(stmt))


def _prior_seen_urls(db: Session, watch_id) -> set[str]:
    """Every RSS url this watch already consumed — so we never re-report an article."""
    seen: set[str] = set()
    for urls in db.scalars(select(WatchRun.new_article_urls).where(WatchRun.watch_id == watch_id)):
        if urls:
            seen.update(urls)
    return seen


def _own_watch(db: Session, user_id: str, watch_id: str) -> Watch:
    watch = db.get(Watch, uuid.UUID(watch_id))
    if not watch or str(watch.user_id) != user_id:
        raise AppError("Veille introuvable.", 404, code="not_found")
    return watch


def set_status(db: Session, user_id: str, watch_id: str, status: str) -> Watch:
    watch = _own_watch(db, user_id, watch_id)
    watch.status = status
    watch.next_run_at = _next_run(watch.cadence) if status == "active" else None
    db.commit()
    db.refresh(watch)
    return watch


def delete_watch(db: Session, user_id: str, watch_id: str) -> None:
    db.delete(_own_watch(db, user_id, watch_id))
    db.commit()


# --- Execution (called by the worker or a manual trigger) ------------------

def _email_body(name: str, veille: dict) -> str:
    delta = veille.get("delta") or "Aucune nouveauté significative depuis la dernière veille."
    full = veille.get("full_report") or ""
    return (f"# Veille : {name}\n\n"
            f"## 🆕 Nouveautés depuis la dernière veille\n\n{delta}\n\n"
            f"---\n\n## 📊 Point complet actualisé\n\n{full}")


def run_watch(db: Session, watch: Watch) -> bool:
    """Run one cumulative veille pass for a watch: gather RSS + web sources, apply
    the agent's rolling memory, produce delta + full report, archive as a WatchRun
    and email. Returns True on success. Never raises to the scheduler."""
    uid = str(watch.user_id)
    try:
        from app.modules.billing import service as billing
        from app.modules.memory import service as memory
        from app.modules.watches import engine, rss, skills
        from app.modules.watches.email import send_email
        from app.shared import search as web_search

        if not billing.check_credits(db, uid, "run_agent_veille")["affordable"]:
            logger.info("Watch %s skipped: insufficient credits", watch.id)
            _reschedule(db, watch, produced=False)
            return False

        skill = skills.get_skill(watch.skill)

        # 1. Sources: fresh RSS (new since last run) + web search on the skill's angle.
        feeds = _feeds_for(db, uid, skill.rss_categories)
        articles = rss.fetch_new_articles(
            feeds, since=watch.last_run_at, seen_urls=_prior_seen_urls(db, watch.id))
        try:
            query = skill.web_query_template.format(subject=watch.query)
            web_results = web_search.search(query, top_k=6)
        except Exception as e:  # noqa: BLE001 — web is optional, RSS may carry the run
            logger.warning("Watch %s web search failed: %s", watch.id, e)
            web_results = []

        # 2. Cumulative generation (rolling memory → delta + full + updated memory).
        company_context = memory.build_context(db, uid)
        veille = engine.generate_veille(
            skill=skill, subject=watch.query, rolling_state=watch.rolling_state,
            rss_articles=articles, web_results=web_results, company_context=company_context,
        )

        # 3. Archive the run + advance the rolling memory.
        db.add(WatchRun(
            id=uuid.uuid4(), watch_id=watch.id,
            delta_content=veille.get("delta") or "",
            full_content=veille.get("full_report") or "",
            rolling_state=veille.get("rolling_state"),
            sources=veille.get("sources"),
            new_article_urls=[a["url"] for a in articles],
            had_changes=bool(veille.get("had_changes", True)),
        ))
        if veille.get("rolling_state"):
            watch.rolling_state = veille["rolling_state"]

        # 4. Charge credits + email the digest.
        billing.consume_credits(db, uid, "run_agent_veille", is_admin=False)  # 5 crédits / run
        from app.modules.memory import service as memory_service

        wants_email = memory_service.get_notification_prefs(db, uid).get("findings", True)
        if watch.email_recipients and wants_email:
            send_email(watch.email_recipients, f"[Axial · Veille] {watch.name}",
                       _email_body(watch.name, veille))

        _reschedule(db, watch, produced=True)
        return True
    except Exception:
        logger.exception("Watch %s run failed", watch.id)
        _reschedule(db, watch, produced=False)
        return False


def _reschedule(db: Session, watch: Watch, *, produced: bool) -> None:
    now = _now()
    if produced:
        watch.last_run_at = now
    watch.next_run_at = _next_run(watch.cadence, base=now) if watch.status == "active" else None
    db.commit()


def run_due_watches(db: Session) -> int:
    """Run every active watch whose next_run_at is in the past. Worker entrypoint."""
    stmt = select(Watch).where(
        Watch.status == "active",
        Watch.next_run_at.is_not(None),
        Watch.next_run_at <= _now(),
    )
    due = list(db.scalars(stmt))
    for watch in due:
        run_watch(db, watch)
    return len(due)
