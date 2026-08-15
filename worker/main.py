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


def main() -> None:
    logger.info("Axial worker starting (tick=%ss)", TICK_SECONDS)
    scheduler = BlockingScheduler(timezone="UTC")
    # Fire the first tick immediately, then every TICK_SECONDS. Passing
    # next_run_time=None would ADD the job PAUSED (it never runs) — the bug we hit.
    scheduler.add_job(tick, "interval", seconds=TICK_SECONDS,
                      next_run_time=dt.datetime.now(dt.timezone.utc))
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Axial worker stopping")


if __name__ == "__main__":
    main()
