"""
Read-side API: lets a frontend (or anyone) pull tracked items and their
price history back out.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.item import Item
from app.models.price_snapshot import PriceSnapshot
from app.schemas import ItemHistory, ItemSummary, PricePoint

router = APIRouter(prefix="/items", tags=["items"])


@router.get("", response_model=list[ItemSummary])
def list_items(db: Session = Depends(get_db)):
    items = db.query(Item).order_by(Item.name).all()

    results = []
    for item in items:
        latest_snapshot = (
            db.query(PriceSnapshot)
            .filter(PriceSnapshot.item_id == item.id)
            .order_by(PriceSnapshot.collected_at.desc())
            .first()
        )
        results.append(
            ItemSummary(
                id=item.id,
                name=item.name,
                category=item.category,
                source_league=item.source_league,
                latest_primary_value=(
                    latest_snapshot.primary_value if latest_snapshot else None
                ),
                primary_currency=(
                    latest_snapshot.primary_currency if latest_snapshot else None
                ),
            )
        )

    return results


@router.get("/{item_name}/history", response_model=ItemHistory)
def get_item_history(item_name: str, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.name == item_name).first()
    if item is None:
        raise HTTPException(
            status_code=404, detail=f"No tracked item named {item_name!r}"
        )

    snapshots = (
        db.query(PriceSnapshot)
        .filter(PriceSnapshot.item_id == item.id)
        .order_by(PriceSnapshot.collected_at.asc())
        .all()
    )

    primary_currency = snapshots[-1].primary_currency if snapshots else "unknown"

    return ItemHistory(
        item_name=item.name,
        league=item.source_league,
        primary_currency=primary_currency,
        points=[
            PricePoint(primary_value=s.primary_value, collected_at=s.collected_at)
            for s in snapshots
        ],
    )