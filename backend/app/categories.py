"""
Category registry: which poe.ninja categories exist, and which endpoint serves
each one.

This is the piece that lets config.yaml stay declarative. The YAML says
"Scarab, exchange"; this module knows whether that's a real combination and
fails the boot with a useful message if it isn't.

The whitelists below are transcribed from https://poe.ninja/docs/api. They will
go stale whenever poe.ninja adds a category — which is what
`allow_unknown_types: true` in config.yaml is for. Flip it and validation drops
to a warning, so you can track a new category the day it appears without
waiting on a code change.
"""

from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class Endpoint(str, Enum):
    """Which poe.ninja endpoint serves a category.

    The two shapes are genuinely different, not cosmetically different:

    EXCHANGE lines give `primaryValue` plus a `core.rates` map, so every
    currency column is derived by multiplication. On PoE 1 the primary is Chaos
    and rates carries only Divine, so value_in_exalted is unavailable there.

    STASH_ITEM lines on PoE 1 give `chaosValue`, `divineValue` and
    `exaltedValue` outright — no rates, no arithmetic, and Exalted IS available.
    That asymmetry is upstream, not a bug in the collector.
    """

    EXCHANGE = "exchange"
    STASH_ITEM = "stash_item"

    @property
    def path(self) -> str:
        return {
            Endpoint.EXCHANGE: "/exchange/current/overview",
            Endpoint.STASH_ITEM: "/stash/current/item/overview",
        }[self]


# Documented `type` values, keyed by (game, endpoint).
# Source: https://poe.ninja/docs/api, transcribed 2026-08-11.
KNOWN_TYPES: dict[tuple[str, Endpoint], set[str]] = {
    ("poe1", Endpoint.EXCHANGE): {
        "Currency", "Fragment", "Runegraft", "AllflameEmber", "Tattoo", "Omen",
        "DjinnCoin", "Ducat", "EnshroudingCrystal", "DivinationCard", "Artifact",
        "Oil", "DeliriumOrb", "Scarab", "Astrolabe", "Fossil", "Resonator",
        "Essence",
    },
    ("poe1", Endpoint.STASH_ITEM): {
        "Wombgift", "Incubator", "UniqueWeapon", "UniqueArmour", "UniqueAccessory",
        "UniqueFlask", "UniqueJewel", "ForbiddenJewel", "ShrineBelt",
        "UniqueTincture", "UniqueRelic", "SkillGem", "ImbuedGem", "ClusterJewel",
        "Map", "BlightedMap", "BlightRavagedMap", "UniqueMap", "ValdoMap",
        "Invitation", "Memory", "IncursionTemple", "BaseType", "Flask", "Beast",
        "Vial",
    },
    ("poe2", Endpoint.EXCHANGE): {
        "Currency", "Fragments", "Abyss", "UncutGems", "LineageSupportGems",
        "Essences", "SoulCores", "Idols", "Runes", "Ritual", "Expedition",
        "Delirium", "Breach", "Verisium",
    },
    ("poe2", Endpoint.STASH_ITEM): {
        "UniqueWeapons", "UniqueArmours", "UniqueAccessories", "UniqueFlasks",
        "UniqueCharms", "UniqueJewels", "UniqueSanctumRelics", "UniqueTablets",
        "PrecursorTablets",
    },
}


def validate_category(
    game: str, endpoint: Endpoint, category_type: str, *, allow_unknown: bool = False
) -> None:
    """Raise (or warn) if this category isn't served where the config claims."""
    known = KNOWN_TYPES.get((game, endpoint))

    if known is None:
        message = f"No known categories for game={game!r} endpoint={endpoint.value!r}"
        if allow_unknown:
            logger.warning("%s — allowing anyway.", message)
            return
        raise ValueError(message)

    if category_type in known:
        return

    # A category listed under the wrong endpoint is the most likely mistake, so
    # check for it and say so rather than just "unknown value".
    other = Endpoint.STASH_ITEM if endpoint is Endpoint.EXCHANGE else Endpoint.EXCHANGE
    if category_type in KNOWN_TYPES.get((game, other), set()):
        raise ValueError(
            f"{game}: {category_type!r} is served by the {other.value!r} endpoint, "
            f"not {endpoint.value!r}. Change `endpoint:` on that line in config.yaml."
        )

    message = (
        f"{game}/{endpoint.value}: {category_type!r} is not a documented category. "
        f"Known values: {', '.join(sorted(known))}"
    )
    if allow_unknown:
        logger.warning("%s — allowing because allow_unknown_types is set.", message)
        return
    raise ValueError(message)
