"""
Collector: pulls current prices from poe.ninja and persists them.

This is the only place that writes to `items` and `price_snapshots`.
Every call to `run_collection` does an insert-only operation on
PriceSnapshot - existing snapshots are never updated or deleted, since
they're the historical record this whole project is built around.
"""

import logging

from sqlalchemy.orm import Session

from app.models.item import Item
from app.models.price_snapshot import PriceSnapshot
from app.services.poe_ninja_client import fetch_currency_overview, parse_currency_lines

logger = logging.getLogger(__name__)


def _get_or_create_item(db: Session, name: str, category: str, league: str) -> Item:
    item = (
        db.query(Item)
        .filter(Item.name == name, Item.source_league == league)
        .one_or_none()
    )
    if item is not None:
        return item

    item = Item(name=name, category=category, source_league=league)
    db.add(item)
    db.flush()
    return item


def run_collection(db: Session, league: str) -> int:
    raw = fetch_currency_overview(league)
    parsed_lines = parse_currency_lines(raw)

    snapshot_count = 0
    for line in parsed_lines:
        item = _get_or_create_item(
            db, name=line["name"], category="Currency", league=league
        )
        snapshot = PriceSnapshot(
            item_id=item.id,
            primary_value=line["primary_value"],
            primary_currency=line["primary_currency"],
            listing_count=line["listing_count"],
        )
        db.add(snapshot)
        snapshot_count += 1

    db.commit()
    logger.info("Collected %d price snapshots for league=%s", snapshot_count, league)
    return snapshot_count