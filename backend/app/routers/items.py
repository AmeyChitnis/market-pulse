"""
Read-side API: lets a frontend (or anyone) pull tracked items and their
price history back out.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.item import Item
from app.models.price_snapshot import PriceSnapshot
from app.schemas import ItemHistory, ItemSummary, PricePoint

router = APIRouter(prefix="/items", tags=["items"])

POE_CDN_BASE_URL = "https://web.poecdn.com"


def _build_image_url(image_path: str | None) -> str | None:
    if not image_path:
        return None
    return f"{POE_CDN_BASE_URL}{image_path}"


CURRENCY_COLUMNS = {
    "chaos": PriceSnapshot.value_in_chaos,
    "exalted": PriceSnapshot.value_in_exalted,
    "divine": PriceSnapshot.value_in_divine,
}


@router.get("", response_model=list[ItemSummary])
def list_items(db: Session = Depends(get_db)):
    latest_per_item = (
        db.query(
            PriceSnapshot.item_id,
            func.max(PriceSnapshot.collected_at).label("latest_collected_at"),
        )
        .group_by(PriceSnapshot.item_id)
        .subquery()
    )

    rows = (
        db.query(Item, PriceSnapshot)
        .join(latest_per_item, Item.id == latest_per_item.c.item_id)
        .join(
            PriceSnapshot,
            (PriceSnapshot.item_id == latest_per_item.c.item_id)
            & (PriceSnapshot.collected_at == latest_per_item.c.latest_collected_at),
        )
        .order_by(Item.name)
        .all()
    )

    return [
        ItemSummary(
            id=item.id,
            name=item.name,
            category=item.category,
            source_league=item.source_league,
            image_url=_build_image_url(item.image_path),
            latest_value_in_chaos=snapshot.value_in_chaos,
            latest_value_in_exalted=snapshot.value_in_exalted,
            latest_value_in_divine=snapshot.value_in_divine,
        )
        for item, snapshot in rows
    ]


@router.get("/{item_name}/history", response_model=ItemHistory)
def get_item_history(
    item_name: str,
    currency: str = Query(default="exalted"),
    hours: float | None = Query(default=24),
    db: Session = Depends(get_db),
):
    if currency not in CURRENCY_COLUMNS:
        raise HTTPException(
            status_code=400,
            detail=f"currency must be one of {list(CURRENCY_COLUMNS)}, got {currency!r}",
        )
    value_column = CURRENCY_COLUMNS[currency]

    item = db.query(Item).filter(Item.name == item_name).first()
    if item is None:
        raise HTTPException(
            status_code=404, detail=f"No tracked item named {item_name!r}"
        )

    query = db.query(PriceSnapshot).filter(PriceSnapshot.item_id == item.id)

    if hours is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        query = query.filter(PriceSnapshot.collected_at >= cutoff)

    snapshots = query.order_by(PriceSnapshot.collected_at.asc()).all()

    points = [
        PricePoint(value=getattr(s, value_column.key), collected_at=s.collected_at)
        for s in snapshots
        if getattr(s, value_column.key) is not None
    ]

    return ItemHistory(
        item_name=item.name,
        league=item.source_league,
        currency=currency,
        points=points,
    )