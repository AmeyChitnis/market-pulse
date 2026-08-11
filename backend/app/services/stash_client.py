"""
Parser for poe.ninja's stash item overview endpoint.

Separate from the exchange parser because the response genuinely differs:

  exchange    lines[].primaryValue + core.rates  ->  multiply to get each currency
  stash_item  lines[].chaosValue / divineValue / exaltedValue (PoE 1)  ->  read directly
              lines[].primaryValue (PoE 2)  ->  needs rates from an exchange call

THE IDENTITY PROBLEM
--------------------
Exchange items are uniquely identified by name. Stash items are not. poe.ninja
prices the same `name` several times with different discriminators:

    Unique maps      -> `variant` (different roll ranges of the same unique)
    Maps             -> `mapTier`
    Anything corrupt -> `corrupted`

So a plain (game, league, name) key would collapse several distinct price
series into one row whose history flips between them — the same class of bug as
the old maxVolumeCurrency problem, and just as invisible on a chart.

`variant_key` below builds a deterministic discriminator string from whichever
fields are present. Add it to Item and make the constraint
UNIQUE(game, source_league, name, variant_key).

IMPORTANT: variant_key must be NOT NULL with a '' default. In SQLite and
Postgres, NULL != NULL, so a unique constraint containing a nullable column
silently stops deduplicating — you'd insert a fresh item row on every single
collection run and only notice when the table got enormous.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Fields that discriminate one priced variant of an item from another.
# Order is fixed so the generated key is stable across runs.
VARIANT_FIELDS = ("variant", "mapTier", "links", "gemLevel", "gemQuality", "corrupted")


def build_variant_key(line: dict) -> str:
    """Deterministic discriminator for a priced item line.

    Returns '' for items with no variants, which is the common case for beasts,
    vials, invitations and temples — those behave exactly like exchange items.
    """
    parts = []
    for field in VARIANT_FIELDS:
        value = line.get(field)
        if value in (None, "", False):
            continue
        parts.append(f"{field}={value}")
    return "|".join(parts)


def parse_stash_item_lines(raw_response: dict, game: str) -> list[dict]:
    """Flatten a stash item overview into one dict per priced item.

    PoE 1 only for now. PoE 2 stash lines carry `primaryValue` with no rates
    block on this endpoint, so pricing them means fetching the Currency
    exchange overview first and passing its rates in — deliberately not done
    here, because it makes collection order-dependent and that deserves its own
    design pass rather than being smuggled into a parser.
    """
    if game != "poe1":
        raise NotImplementedError(
            "Stash item parsing is implemented for poe1 only. PoE 2 stash lines "
            "need exchange rates to convert primaryValue; see the module docstring."
        )

    parsed: list[dict] = []
    skipped = 0

    for line in raw_response.get("lines", []):
        name = line.get("name")
        chaos_value = line.get("chaosValue")

        if not name or chaos_value is None:
            skipped += 1
            continue

        parsed.append(
            {
                "name": name,
                "variant_key": build_variant_key(line),
                "base_type": line.get("baseType"),
                "details_id": line.get("detailsId"),
                "image_path": line.get("icon"),
                "values": {
                    "chaos": chaos_value,
                    "divine": line.get("divineValue"),
                    # Documented as omitted when zero, so absence means 0, not unknown.
                    "exalted": line.get("exaltedValue", 0.0),
                },
                # Real listing count here, unlike the exchange endpoint where the
                # nearest equivalent is volumePrimaryValue (traded volume, a
                # different quantity that the current collector mislabels).
                "listing_count": line.get("listingCount"),
                "observation_count": line.get("count"),
            }
        )

    if skipped:
        logger.info("Skipped %d stash lines with no name or no chaos value", skipped)

    return parsed
