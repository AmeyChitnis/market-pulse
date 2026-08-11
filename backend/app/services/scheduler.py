"""
Background scheduler: runs the collector on a fixed interval so price
history accumulates while the app is running.

APScheduler's BackgroundScheduler runs jobs on a separate thread inside
the same process as FastAPI. Consequences worth remembering:
  - It only runs while uvicorn runs. Closing the terminal stops
    collection; there is no separate daemon.
  - `--reload` restarts and machine sleep both reset the interval timer.
  - Each job run needs its own DB session (sessions are not safe to share
    across threads), so we build one here rather than reusing get_db().
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.database import SessionLocal
from app.services.collector import run_all_sources

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _scheduled_collection_job():
    """Collect every configured source, with its own session.

    run_all_sources already isolates per-source failures, but this outer
    try/except is still needed: a failure to even open a session must not
    kill the scheduler and stop all future runs.
    """
    db = SessionLocal()
    try:
        for result in run_all_sources(db):
            if "error" in result:
                logger.warning(
                    "Scheduled collection FAILED game=%s league=%s: %s",
                    result["game"],
                    result["league"],
                    result["error"],
                )
            else:
                logger.info(
                    "Scheduled collection ok game=%s league=%s: %d snapshots",
                    result["game"],
                    result["league"],
                    result["snapshots_written"],
                )
    except Exception:
        logger.exception("Scheduled collection run failed before reaching sources")
    finally:
        db.close()


def start_scheduler():
    """Call once, at app startup."""
    scheduler.add_job(
        _scheduled_collection_job,
        trigger="interval",
        minutes=settings.collector_interval_minutes,
        id="poe_ninja_collection",
    )
    scheduler.start()
    logger.info(
        "Scheduler started: collecting every %d minutes from %d source(s): %s",
        settings.collector_interval_minutes,
        len(settings.sources),
        ", ".join(f"{s.game}/{s.league}" for s in settings.sources),
    )


def shutdown_scheduler():
    """Call at app shutdown so the background thread exits cleanly."""
    if scheduler.running:
        scheduler.shutdown(wait=False)