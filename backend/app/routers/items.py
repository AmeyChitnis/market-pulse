"""
Read-side API: pull tracked items and their price history back out.
Counterpart to the collector - nothing here writes to the database.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import SUPPORTED_GAMES, settings
from app.database import get_db
from app.models.item import Item
from app.models.price_snapshot import PriceSnapshot
from app.schemas import GameOption, ItemHistory, ItemSummary, PricePoint

router = APIRouter(tags=["items"])

# poe.ninja serves item icons as relative paths; this CDN host was
# confirmed from live traffic, not documentation.
POE_CDN_BASE_URL = "https://web.poecdn.com"

GAME_LABELS = {"poe1": "Path of Exile", "poe2": "Path of Exile 2"}

# Which SQLAlchemy column holds values in each currency. The caller picks
# one and the whole chart stays in that unit, instead of being at the
# mercy of poe.ninja's per-item "most traded against" pick, which flips
# between runs for illiquid items.
CURRENCY_COLUMNS = {
    "chaos": PriceSnapshot.value_in_chaos,
    "exalted": PriceSnapshot.value_in_exalted,
    "divine": PriceSnapshot.value_in_divine,
}


def _build_image_url(image_path: str | None) -> str | None:
    return f"{POE_CDN_BASE_URL}{image_path}" if image_path else None


def _validate_game(game: str) -> None:
    if game not in SUPPORTED_GAMES:
        raise HTTPException(
            status_code=400,
            detail=f"game must be one of {list(SUPPORTED_GAMES)}, got {game!r}",
        )


@router.get("/games", response_model=list[GameOption])
def list_games():
    """Which games this instance is actually collecting.

    The frontend's game picker reads this rather than hardcoding a list,
    so adding a source in config.yaml is enough to surface it in the UI.
    """
    return [
        GameOption(
            game=s.game,
            league=s.league,
            label=GAME_LABELS.get(s.game, s.game),
        )
        for s in settings.sources
    ]


@router.get("/items", response_model=list[ItemSummary])
def list_items(
    game: str = Query(..., description="poe1 or poe2"),
    db: Session = Depends(get_db),
):
    """
    Every tracked item for one game, with its most recent price in all
    three currencies.

    PERFORMANCE: this finds the latest collected_at per item_id in a
    single grouped subquery and joins it back, rather than running one
    extra "latest snapshot" query per item (an N+1 that got slower as
    history grew).
    """
    _validate_game(game)

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
        .filter(Item.game == game)
        .order_by(Item.name)
        .all()
    )

    return [
        ItemSummary(
            id=item.id,
            name=item.name,
            category=item.category,
            game=item.game,
            source_league=item.source_league,
            image_url=_build_image_url(item.image_path),
            latest_value_in_chaos=snapshot.value_in_chaos,
            latest_value_in_exalted=snapshot.value_in_exalted,
            latest_value_in_divine=snapshot.value_in_divine,
        )
        for item, snapshot in rows
    ]


@router.get("/items/{item_name}/history", response_model=ItemHistory)
def get_item_history(
    item_name: str,
    game: str = Query(..., description="poe1 or poe2"),
    currency: str = Query("exalted", description="chaos, exalted or divine"),
    hours: float | None = Query(24, description="Only points from the last N hours"),
    db: Session = Depends(get_db),
):
    """
    Price history for one item, in a single caller-chosen currency.

    Points whose value is NULL for the requested currency are dropped.
    That is expected on PoE1, where poe.ninja quotes no exalted rate at
    all - the Exalted view is simply empty there rather than wrong.
    """
    _validate_game(game)
    if currency not in CURRENCY_COLUMNS:
        raise HTTPException(
            status_code=400,
            detail=f"currency must be one of {list(CURRENCY_COLUMNS)}, got {currency!r}",
        )
    value_column = CURRENCY_COLUMNS[currency]

    item = (
        db.query(Item)
        .filter(Item.name == item_name, Item.game == game)
        .first()
    )
    if item is None:
        raise HTTPException(
            status_code=404,
            detail=f"No tracked item named {item_name!r} for game {game!r}",
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
        game=item.game,
        league=item.source_league,
        currency=currency,
        points=points,
    )