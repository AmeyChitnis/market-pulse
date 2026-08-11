"""
Manual collection triggers and scheduler diagnostics.

Useful for testing without waiting for the next tick, and as a "refresh
now" control. Not meant for high-frequency use - poe.ninja is the
rate-limited resource here, not this endpoint.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services.collector import run_all_sources, run_collection

router = APIRouter(prefix="/collect", tags=["collection"])


@router.get("/status")
def scheduler_status():
    """Diagnostic: what the scheduler actually thinks is going on."""
    from app.services.scheduler import scheduler

    return {
        "scheduler_running": scheduler.running,
        "interval_minutes": settings.collector_interval_minutes,
        "sources": [
            {"game": s.game, "league": s.league} for s in settings.sources
        ],
        "jobs": [
            {
                "id": job.id,
                "next_run_time": str(job.next_run_time),
                "trigger": str(job.trigger),
            }
            for job in scheduler.get_jobs()
        ],
    }


@router.post("/run")
def trigger_collection(db: Session = Depends(get_db)):
    """Collect every configured source once, right now.

    Returns 200 with per-source results even when some sources failed -
    a partial success is real information, and failing the whole call
    because PoE1's league name went stale would hide that PoE2 worked.
    """
    return {"results": run_all_sources(db)}


@router.post("/run/{game}")
def trigger_collection_for_game(game: str, db: Session = Depends(get_db)):
    """Collect a single configured game, for targeted testing."""
    source = settings.source_for_game(game)
    if source is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No source configured for game {game!r}. "
                f"Configured: {[s.game for s in settings.sources]}"
            ),
        )
    try:
        count = run_collection(
            db,
            game=source.game,
            league=source.league,
            overview_type=settings.overview_type,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Collection failed: {exc}") from exc

    return {
        "game": source.game,
        "league": source.league,
        "snapshots_written": count,
    }