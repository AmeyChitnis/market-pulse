"""
Client for poe.ninja's currency exchange API, for BOTH PoE1 and PoE2.

Endpoint shape (confirmed against live network traffic, not documentation
- the community-written docs for this API have repeatedly been stale):

    https://poe.ninja/{game}/api/economy/exchange/current/overview
        ?league={league}&type={overview_type}

`game` is "poe1" or "poe2" and is the only difference in the URL.

WHY THE PARSER IS CURRENCY-AGNOSTIC
-----------------------------------
An earlier version of this file hardcoded PoE2's shape: it assumed
line.primaryValue was denominated in divine, and raised if core.rates was
missing an "exalted" or "chaos" key. That is false for PoE1. Confirmed
captures:

    PoE2: core.primary = "divine", core.rates = {exalted, chaos}
    PoE1: core.primary = "chaos",  core.rates = {divine}   <- no exalted

So the parser now derives everything from the response itself:

    core.primary            = the unit line.primaryValue is expressed in
    core.rates[X]           = how many X you get for 1 primary
    multipliers             = {primary: 1.0, **core.rates}
    value_in_X              = primaryValue * multipliers[X], or None if
                              this game/league doesn't quote X at all

A missing currency yields None rather than an error, because the
value_in_* columns are nullable and the read API already filters out
None points. On PoE1 that means value_in_exalted stays empty and the
frontend's Exalted view is simply empty for that league - degraded, but
honest, rather than a crash or a fabricated number.
"""

import httpx

CURRENCY_KEYS = ("chaos", "exalted", "divine")

_HEADERS_TEMPLATE = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def _base_url(game: str) -> str:
    return f"https://poe.ninja/{game}/api/economy/exchange/current"


def fetch_currency_overview(game: str, league: str, overview_type: str) -> dict:
    """
    Fetch the current currency exchange overview.

    `league` must be the league/mechanic name (e.g. "Runes of Aldur",
    "Mirage"), not the patch name. A wrong league name is the most common
    cause of a 404 here. Raises httpx.HTTPStatusError on any non-2xx.
    """
    url = f"{_base_url(game)}/overview"
    params = {"league": league, "type": overview_type}
    headers = {**_HEADERS_TEMPLATE, "Referer": f"https://poe.ninja/{game}/economy/"}

    response = httpx.get(url, params=params, headers=headers, timeout=10.0)
    response.raise_for_status()
    return response.json()


def parse_currency_lines(raw_response: dict) -> list[dict]:
    """
    Normalize the response into flat dicts, one per priced item:

        {
            "name", "image_path",
            "value_in_chaos" | None,
            "value_in_exalted" | None,
            "value_in_divine" | None,
            "primary_value", "primary_currency",   # legacy, see below
            "listing_count",
        }
    """
    core = raw_response.get("core", {})
    primary = core.get("primary")
    if not primary:
        raise ValueError(
            "Response is missing core.primary - poe.ninja's format may have "
            "changed; re-verify against live traffic before trusting output."
        )

    # 1 primary is worth 1 primary; everything else comes from core.rates.
    multipliers = {primary: 1.0, **(core.get("rates") or {})}

    items = raw_response.get("items", [])
    id_to_name = {i["id"]: i["name"] for i in items if "id" in i and "name" in i}
    id_to_image = {i["id"]: i.get("image") for i in items if "id" in i}

    parsed = []
    for line in raw_response.get("lines", []):
        item_id = line.get("id")
        primary_value = line.get("primaryValue")
        if item_id is None or primary_value is None:
            continue

        values = {
            f"value_in_{key}": (
                primary_value * multipliers[key] if key in multipliers else None
            )
            for key in CURRENCY_KEYS
        }

        # Legacy fields: poe.ninja's own "most traded against" pick for
        # this item. Unstable for illiquid items (it flips between runs),
        # which is exactly why the value_in_* columns exist - these are
        # kept only for backward compatibility with older rows.
        max_volume_currency = line.get("maxVolumeCurrency")
        max_volume_rate = line.get("maxVolumeRate")
        if max_volume_currency and max_volume_rate:
            legacy_value, legacy_currency = 1 / max_volume_rate, max_volume_currency
        else:
            legacy_value, legacy_currency = primary_value, primary

        parsed.append(
            {
                "name": id_to_name.get(item_id, item_id),
                "image_path": id_to_image.get(item_id),
                **values,
                "primary_value": legacy_value,
                "primary_currency": legacy_currency,
                "listing_count": line.get("volumePrimaryValue"),
            }
        )

    return parsed