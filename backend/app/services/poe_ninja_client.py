"""
Client for poe.ninja's live currency exchange API - PoE2 edition.

PRICING MODEL - multi-currency, not a single "most popular" pick:
    An earlier version priced each item in whichever currency
    poe.ninja's maxVolumeCurrency said was most popular at that moment.
    This was unstable for low-liquidity items - the "most popular
    pairing" can flip between collection runs even when the real price
    barely moved, causing fake-looking spikes on charts.

    Fix: every item's price is reported in ALL THREE currencies
    (chaos, exalted, divine), computed from poe.ninja's core.rates:
        value_in_exalted = primaryValue * core.rates["exalted"]
        value_in_chaos   = primaryValue * core.rates["chaos"]
        value_in_divine  = primaryValue
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
    url = f"{POE_NINJA_BASE_URL}/overview"
    params = {"league": league, "type": currency_type}

    response = httpx.get(url, params=params, headers=_HEADERS, timeout=10.0)
    response.raise_for_status()
    return response.json()


def parse_currency_lines(raw_response: dict) -> list[dict]:
    core = raw_response.get("core", {})
    rates = core.get("rates", {})
    primary_currency_name = core.get("primary")

    rate_to_exalted = rates.get("exalted")
    rate_to_chaos = rates.get("chaos")

    if rate_to_exalted is None or rate_to_chaos is None:
        raise ValueError(
            "core.rates is missing 'exalted' or 'chaos' - poe.ninja's "
            "response format may have changed; re-verify against live traffic."
        )

    id_to_name = {
        item["id"]: item["name"]
        for item in raw_response.get("items", [])
        if "id" in item and "name" in item
    }

    parsed = []
    for line in raw_response.get("lines", []):
        item_id = line.get("id")
        value_in_divine = line.get("primaryValue")

        if item_id is None or value_in_divine is None:
            continue

        name = id_to_name.get(item_id, item_id)

        max_volume_currency = line.get("maxVolumeCurrency")
        max_volume_rate = line.get("maxVolumeRate")
        if max_volume_currency and max_volume_rate:
            legacy_primary_value = 1 / max_volume_rate
            legacy_primary_currency = max_volume_currency
        else:
            legacy_primary_value = value_in_divine
            legacy_primary_currency = primary_currency_name

        parsed.append(
            {
                "name": name,
                "value_in_chaos": value_in_divine * rate_to_chaos,
                "value_in_exalted": value_in_divine * rate_to_exalted,
                "value_in_divine": value_in_divine,
                "primary_value": legacy_primary_value,
                "primary_currency": legacy_primary_currency,
                "listing_count": line.get("volumePrimaryValue"),
            }
        )

    return parsed