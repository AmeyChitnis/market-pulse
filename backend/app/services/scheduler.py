"""
Background scheduler: runs the poe.ninja collector on a fixed interval
so price history accumulates automatically while the app is running.

This uses APScheduler's BackgroundScheduler, which runs jobs in a
separate thread inside the same process as the FastAPI app. That means:
  - The scheduler only runs while `uvicorn` is running. Closing the
    terminal stops collection too — there's no separate daemon.
  - Each job run needs its own DB session (sessions aren't safely
    shared across threads), so we create one specifically for the job
    rather than reusing the request-scoped get_db() dependency.
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.database import SessionLocal
from app.services.collector import run_collection

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _scheduled_collection_job():
    """Wraps run_collection with its own DB session and error handling.

    A failed run (e.g. poe.ninja briefly unreachable) must not crash the
    scheduler or stop future runs — it should just log and try again
    next interval.
    """
    db = SessionLocal()
    try:
        count = run_collection(db, league=settings.poe_league)
        logger.info("Scheduled collection succeeded: %d snapshots", count)
    except Exception:
        logger.exception("Scheduled collection run failed")
    finally:
        db.close()


def start_scheduler():
    """Call once, at app startup. Safe to call only once per process."""
    scheduler.add_job(
        _scheduled_collection_job,
        trigger="interval",
        minutes=settings.collector_interval_minutes,
        id="poe_ninja_collection",
    )
    scheduler.start()
    logger.info(
        "Scheduler started: collecting every %d minutes",
        settings.collector_interval_minutes,
    )


def shutdown_scheduler():
    """Call at app shutdown so the background thread exits cleanly."""
    if scheduler.running:
        scheduler.shutdown(wait=False)