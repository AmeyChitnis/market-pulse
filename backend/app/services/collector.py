"""
Collector: pulls current prices from poe.ninja and persists them.

The only place in the app that writes to `items` and `price_snapshots`.
Insert-only: existing snapshots are never updated or deleted.

Isolation is two levels deep now. A source (game+league) failing must not stop
other sources, and a single CATEGORY failing must not stop the other categories
for that same source - poe.ninja retiring one category should cost you that
category, not the whole run's Currency data.
"""

import logging

from sqlalchemy.orm import Session

from app.categories import Endpoint
from app.config import CategoryConfig, DataSource
from app.models.item import Item
from app.models.price_snapshot import PriceSnapshot
from app.services.poe_ninja_client import fetch_currency_overview, parse_currency_lines

logger = logging.getLogger(__name__)


def _get_or_create_item(
    db: Session,
    name: str,
    category: str,
    game: str,
    league: str,
    image_path: str | None,
) -> Item:
    item = (
        db.query(Item)
        .filter(
            Item.name == name,
            Item.game == game,
            Item.source_league == league,
        )
        .one_or_none()
    )
    if item is not None:
        if image_path and item.image_path != image_path:
            item.image_path = image_path
        # An item can move between categories upstream. Keep the row and update
        # the label rather than forking its price history into a second item.
        if item.category != category:
            logger.info(
                "Item %r moved category: %s -> %s", name, item.category, category
            )
            item.category = category
        return item

    item = Item(
        name=name,
        category=category,
        game=game,
        source_league=league,
        image_path=image_path,
    )
    db.add(item)
    db.flush()
    return item


def run_collection(db: Session, game: str, league: str, overview_type: str) -> int:
    """
    Fetch current prices for one (game, league, category) and store one
    PriceSnapshot per priced item. Returns the number written. Raises on
    network/parse failure - the caller decides how to log and handle it.

    Exchange endpoint only. Stash-item categories need a different parser
    (app/services/stash_client.py) because the response shape differs.
    """
    raw = fetch_currency_overview(game, league, overview_type)
    parsed_lines = parse_currency_lines(raw)

    snapshot_count = 0
    for line in parsed_lines:
        item = _get_or_create_item(
            db,
            name=line["name"],
            category=overview_type,
            game=game,
            league=league,
            image_path=line.get("image_path"),
        )
        db.add(
            PriceSnapshot(
                item_id=item.id,
                value_in_chaos=line["value_in_chaos"],
                value_in_exalted=line["value_in_exalted"],
                value_in_divine=line["value_in_divine"],
                primary_value=line["primary_value"],
                primary_currency=line["primary_currency"],
                listing_count=line["listing_count"],
            )
        )
        snapshot_count += 1

    db.commit()
    logger.info(
        "Collected %d snapshots for game=%s league=%s category=%s",
        snapshot_count, game, league, overview_type,
    )
    return snapshot_count


def run_source(db: Session, source: DataSource) -> dict:
    """Collect every enabled category for one source."""
    total = 0
    ok: list[str] = []
    failed: dict[str, str] = {}

    for category in source.categories:
        if category.endpoint is not Endpoint.EXCHANGE:
            # Stash-item categories are declared in config.yaml but not yet
            # collectable. Skip quietly rather than logging a failure per tick.
            continue
        try:
            total += run_collection(
                db, game=source.game, league=source.league, overview_type=category.type
            )
            ok.append(category.type)
        except Exception as exc:  # noqa: BLE001 - report, never abort the loop
            db.rollback()
            logger.exception(
                "Collection failed for game=%s league=%s category=%s",
                source.game, source.league, category.type,
            )
            failed[category.type] = f"{type(exc).__name__}: {exc}"

    result = {
        "game": source.game,
        "league": source.league,
        "snapshots_written": total,
        "categories_ok": ok,
        "categories_failed": failed,
    }
    # Preserve the old contract: callers that looked for an "error" key on a
    # totally failed source still find one.
    if failed and not ok:
        result["error"] = f"all {len(failed)} categories failed"
    return result


def run_all_sources(db: Session) -> list[dict]:
    """
    Collect every configured source. Each source is isolated: a PoE1
    failure (wrong league name, poe.ninja hiccup) must not prevent PoE2
    from collecting on the same tick.

    Returns one result dict per source.
    """
    from app.config import settings

    results = []
    for source in settings.sources:
        try:
            results.append(run_source(db, source))
        except Exception as exc:  # noqa: BLE001 - a whole-source failure
            db.rollback()
            logger.exception(
                "Source failed entirely: game=%s league=%s", source.game, source.league
            )
            results.append(
                {
                    "game": source.game,
                    "league": source.league,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return results
