"""Background worker — runs scheduled watches.

Same codebase as the API, launched as a separate process (`make worker`). Every
tick it runs any watch whose next_run_at is due. Kept intentionally simple: the
scheduling state lives in the DB (next_run_at), so the worker is stateless and
safe to restart.
"""
from __future__ import annotations

import datetime as dt
import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from app.config import get_settings
from app.db import SessionLocal
from app.modules.watches.service import run_due_watches

logging.basicConfig(level=get_settings().log_level)
logger = logging.getLogger("axial.worker")

TICK_SECONDS = 60


def tick() -> None:
    with SessionLocal() as db:
        count = run_due_watches(db)
        if count:
            logger.info("Worker tick: ran %d due watch(es)", count)


def weekly_recap() -> None:
    """Récap hebdo par email (lundi matin) — uniquement aux utilisateurs dont la
    préférence `weekly` est active ET qui ont eu de l'activité de veille."""
    from sqlalchemy import text

    from app.modules.watches.email import send_email

    with SessionLocal() as db:
        rows = db.execute(text("""
            SELECT u.id, u.email,
                   count(DISTINCT w.id)  AS watches,
                   count(r.id)           AS runs,
                   count(r.id) FILTER (WHERE r.had_changes) AS runs_new
            FROM auth.users u
            JOIN watches w ON w.user_id = u.id
            LEFT JOIN watch_runs r ON r.watch_id = w.id
                 AND r.created_at > now() - interval '7 days'
            LEFT JOIN notification_prefs np ON np.user_id = u.id
            WHERE COALESCE(np.weekly, true)
            GROUP BY u.id, u.email
        """)).all()
        for uid, email, watches, runs, runs_new in rows:
            if not runs:
                continue  # pas d'activité → pas d'email
            body = (
                f"# Votre semaine Axial\n\n"
                f"- **{watches}** agent(s) de veille actifs\n"
                f"- **{runs}** run(s) exécutés ces 7 derniers jours\n"
                f"- **{runs_new}** avec du nouveau\n\n"
                f"Retrouvez le détail dans l'onglet Agents : https://app.axial-ia.fr\n\n"
                f"---\n*Pour ne plus recevoir ce récap : Paramètres → Notifications.*"
            )
            try:
                send_email([email], "[Axial] Récap hebdomadaire de votre veille", body)
                logger.info("Récap hebdo envoyé à %s", email)
            except Exception:
                logger.warning("Récap hebdo : échec pour %s", email, exc_info=True)


def sequences_emails() -> None:
    """Séquences de cycle de vie — toutes les heures.

    Interrupteur `EMAIL_SEQUENCES_ACTIVES` : tant qu'il est à false, le passage
    se fait en simulation et n'envoie rien. Un moteur d'emails qui s'allume
    tout seul au premier déploiement écrirait à de vrais clients avant que
    quiconque ait relu les textes.
    """
    import os

    from app.modules.emailing.sequences import executer

    actives = os.getenv("EMAIL_SEQUENCES_ACTIVES", "false").lower() in ("1", "true", "yes")
    with SessionLocal() as db:
        journal = executer(db, simulation=not actives)
    envoyes = sum(1 for j in journal if j.get("envoye"))
    if envoyes:
        logger.info("Séquences email : %d envoi(s)", envoyes)
    elif journal and not actives:
        logger.info("Séquences email (simulation) : %d candidat(s)", len(journal))


def main() -> None:
    logger.info("Axial worker starting (tick=%ss)", TICK_SECONDS)
    scheduler = BlockingScheduler(timezone="UTC")
    # Fire the first tick immediately, then every TICK_SECONDS. Passing
    # next_run_time=None would ADD the job PAUSED (it never runs) — the bug we hit.
    scheduler.add_job(tick, "interval", seconds=TICK_SECONDS,
                      next_run_time=dt.datetime.now(dt.timezone.utc))
    # Lundi 08:00 Paris ≈ 06:00 UTC (été) — récap hebdo.
    scheduler.add_job(weekly_recap, "cron", day_of_week="mon", hour=6, minute=0)
    # Séquences de cycle de vie : toutes les heures à la minute 20, pour ne pas
    # tomber en même temps que le récap hebdo.
    scheduler.add_job(sequences_emails, "cron", minute=20)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Axial worker stopping")


if __name__ == "__main__":
    main()
