"""
Manual trigger for running a poe.ninja collection on demand.

Useful for testing the collector without waiting for the scheduler, and
as a manual "refresh now" control later if needed. Not meant to be
hit at high frequency — poe.ninja itself is the rate-limited resource
here, not this endpoint.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services.collector import run_collection

router = APIRouter(prefix="/collect", tags=["collection"])

@router.get("/status")
def scheduler_status():
    """Diagnostic: shows what the scheduler actually thinks is going on."""
    from app.services.scheduler import scheduler

    jobs = scheduler.get_jobs()
    return {
        "scheduler_running": scheduler.running,
        "jobs": [
            {
                "id": job.id,
                "next_run_time": str(job.next_run_time),
                "trigger": str(job.trigger),
            }
            for job in jobs
        ],
    }

@router.post("/run")
def trigger_collection(db: Session = Depends(get_db)):
    try:
        count = run_collection(db, league=settings.poe_league)
    except Exception as exc:  # noqa: BLE001 — surface any failure as a 502
        raise HTTPException(
            status_code=502, detail=f"Collection failed: {exc}"
        ) from exc

    return {"league": settings.poe_league, "snapshots_written": count}