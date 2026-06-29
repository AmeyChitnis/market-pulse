"""
Collector: pulls current prices from poe.ninja and persists them.
"""

import logging

from sqlalchemy.orm import Session

from app.models.item import Item
from app.models.price_snapshot import PriceSnapshot
from app.services.poe_ninja_client import fetch_currency_overview, parse_currency_lines

logger = logging.getLogger(__name__)


def _get_or_create_item(
    db: Session, name: str, category: str, league: str, image_path: str | None
) -> Item:
    item = (
        db.query(Item)
        .filter(Item.name == name, Item.source_league == league)
        .one_or_none()
    )
    if item is not None:
        if image_path and item.image_path != image_path:
            item.image_path = image_path
        return item

    item = Item(name=name, category=category, source_league=league, image_path=image_path)
    db.add(item)
    db.flush()
    return item


def run_collection(db: Session, league: str) -> int:
    raw = fetch_currency_overview(league)
    parsed_lines = parse_currency_lines(raw)

    snapshot_count = 0
    for line in parsed_lines:
        item = _get_or_create_item(
            db,
            name=line["name"],
            category="Currency",
            league=league,
            image_path=line.get("image_path"),
        )
        snapshot = PriceSnapshot(
            item_id=item.id,
            value_in_chaos=line["value_in_chaos"],
            value_in_exalted=line["value_in_exalted"],
            value_in_divine=line["value_in_divine"],
            primary_value=line["primary_value"],
            primary_currency=line["primary_currency"],
            listing_count=line["listing_count"],
        )
        db.add(snapshot)
        snapshot_count += 1

    db.commit()
    logger.info("Collected %d price snapshots for league=%s", snapshot_count, league)
    return snapshot_count