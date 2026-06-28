"""
Client for poe.ninja's live currency exchange API - PoE2 edition.

VERIFIED against real network traffic in June 2026. See prior commit
history for this file (and its PoE1 equivalent) for examples of how
poe.ninja's actual API has repeatedly differed from third-party
documentation - always re-verify against live traffic rather than trust
a write-up, including this docstring once enough time has passed.

Confirmed live endpoint and params:
    https://poe.ninja/poe2/api/economy/exchange/current/overview
        ?league=<league name>&type=Currency

IMPORTANT - league name vs patch name: the league query param wants the
actual league/mechanic name (e.g. "Runes of Aldur"), NOT the patch/season
name reported in news articles (e.g. "Return of the Ancients" = patch
0.5.0's name). Confirm the current value directly from network traffic
on https://poe.ninja/poe2/economy/... rather than from a news search.

PRICING MODEL - "most popular pairing" instead of a fixed base unit:
    poe.ninja's `primaryValue` is denominated in whatever `core.primary`
    is for the league (observed as "divine" for PoE2, "chaos" for PoE1).
    However, many low-value items are rarely actually traded for the
    primary currency in bulk - in practice traders exchange them for
    whatever poe.ninja calls `maxVolumeCurrency`, the currency this item
    trades against with the highest observed volume.

    This client reports each item's price in ITS OWN most-popular
    pairing currency, not the league's fixed primary currency. This
    means different rows in price_snapshots can be denominated in
    different currencies - by design. `primary_currency` records which
    currency a given row is actually expressed in, so this is always
    explicit, never assumed.

    The conversion uses a field poe.ninja already computes for us,
    `maxVolumeRate`, confirmed (by checking real data, not docs) to mean:
        maxVolumeRate = how many units of THIS item you get for 1 unit
                        of maxVolumeCurrency
    e.g. bauble: maxVolumeCurrency="exalted", maxVolumeRate=0.7106 means
    1 Exalted Orb buys ~0.71 Glassblower's Baubles (confirmed by manual
    calculation: exalted.primaryValue / bauble.primaryValue == 0.7106).

    Since we want "price of 1 unit of this item, in its popular
    currency" (not "how many of this item per 1 of that currency"), we
    invert it: price_in_popular_currency = 1 / maxVolumeRate.
"""

import httpx

POE_NINJA_BASE_URL = "https://poe.ninja/poe2/api/economy/exchange/current"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://poe.ninja/poe2/economy/",
}

DEFAULT_TYPE = "Currency"


def fetch_currency_overview(league: str, currency_type: str = DEFAULT_TYPE) -> dict:
    """
    Fetch the current currency exchange overview for a PoE2 league.

    `league` must be the actual league/mechanic name (e.g. "Runes of
    Aldur"), not the patch name. Raises httpx.HTTPStatusError on a
    non-2xx response.
    """
    url = f"{POE_NINJA_BASE_URL}/overview"
    params = {"league": league, "type": currency_type}

    response = httpx.get(url, params=params, headers=_HEADERS, timeout=10.0)
    response.raise_for_status()
    return response.json()


def parse_currency_lines(raw_response: dict) -> list[dict]:
    """
    Normalize poe.ninja's response into a flat list of simple dicts,
    re-priced into each item's own most-popular trading currency.

    Returns a list of:
        {
            "name": str,
            "primary_value": float,   # price in THIS item's popular currency
            "primary_currency": str,  # which currency that is (varies per item)
            "listing_count": float | None,
        }

    Items missing maxVolumeCurrency/maxVolumeRate, or with a zero rate
    (which would make inversion undefined), are skipped rather than
    guessed at - better to have fewer, trustworthy rows than a fabricated
    price.
    """
    id_to_name = {
        item["id"]: item["name"]
        for item in raw_response.get("items", [])
        if "id" in item and "name" in item
    }

    parsed = []
    for line in raw_response.get("lines", []):
        item_id = line.get("id")
        max_volume_currency = line.get("maxVolumeCurrency")
        max_volume_rate = line.get("maxVolumeRate")

        if item_id is None or max_volume_currency is None or not max_volume_rate:
            continue

        name = id_to_name.get(item_id, item_id)
        price_in_popular_currency = 1 / max_volume_rate

        parsed.append(
            {
                "name": name,
                "primary_value": price_in_popular_currency,
                "primary_currency": max_volume_currency,
                "listing_count": line.get("volumePrimaryValue"),
            }
        )

    return parsed