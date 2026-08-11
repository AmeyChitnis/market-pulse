"""
Centralized application configuration.

Two layers, on purpose:

  config.yaml  — WHAT we track (which games/leagues, which categories,
                 interval). Committed; edited by hand when a league
                 rotates, a game is added, or a category is enabled.
  .env         — WHERE/HOW this instance runs (database_url, app_env).
                 Machine-specific, gitignored.

YAML values are passed as explicit kwargs to Settings(), so they take
precedence over environment variables. That is deliberate: editing one
file must be enough to change the data source, without wondering whether
a stale .env is silently overriding it.

Nothing else in the app should read os.environ or parse YAML - import
`settings` from here.

Note on `extra="ignore"`: it makes stale .env keys harmless, but it also
means a MISSPELLED key in config.yaml is silently dropped rather than
rejected. The explicit checks at the bottom of this file exist to claw
back some of that safety for the fields that actually matter.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.categories import Endpoint, validate_category

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"

SUPPORTED_GAMES = ("poe1", "poe2")


class CategoryConfig(BaseModel):
    """One poe.ninja category to collect for a source.

    `endpoint` matters because poe.ninja serves these from two places with
    different response shapes - see app/categories.py. `section` and `label`
    are display concerns only: they are served to the frontend from config
    rather than stored on Item, so renaming a section is a YAML edit and not
    a database UPDATE.
    """

    type: str
    endpoint: Endpoint = Endpoint.EXCHANGE
    section: str = "General"
    label: str | None = None

    @property
    def display_label(self) -> str:
        return self.label or self.type


class DataSource(BaseModel):
    """One (game, league) pair, and the categories to collect for it."""

    game: str
    league: str
    categories: list[CategoryConfig] = [CategoryConfig(type="Currency")]

    @field_validator("game")
    @classmethod
    def _known_game(cls, v: str) -> str:
        if v not in SUPPORTED_GAMES:
            raise ValueError(
                f"game must be one of {list(SUPPORTED_GAMES)}, got {v!r}"
            )
        return v

    def categories_for(self, endpoint: Endpoint) -> list[CategoryConfig]:
        return [c for c in self.categories if c.endpoint is endpoint]


def _load_yaml_config() -> dict:
    """Read config.yaml if present. A missing file is not fatal - the
    defaults below are a working single-source PoE2 configuration."""
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Runtime (from .env)
    database_url: str = "sqlite:///./market_pulse.db"
    app_env: str = "development"

    # Data sources (from config.yaml)
    sources: list[DataSource] = [DataSource(game="poe2", league="Runes of Aldur")]
    collector_interval_minutes: int = 10

    # Accept category `type` values not in the documented whitelist. Turn this
    # on when poe.ninja adds a category and you want to track it immediately
    # rather than waiting for app/categories.py to be updated.
    allow_unknown_types: bool = False

    def source_for_game(self, game: str) -> DataSource | None:
        return next((s for s in self.sources if s.game == game), None)


settings = Settings(**_load_yaml_config())

if not settings.sources:
    raise ValueError("config.yaml: `sources` is empty - nothing would be collected.")

_seen = [s.game for s in settings.sources]
if len(_seen) != len(set(_seen)):
    raise ValueError(
        f"config.yaml: duplicate game entries in `sources` ({_seen}). "
        "One league per game is supported."
    )

# Fail the boot on a bad category rather than 400ing inside a background job
# hours later. validate_category also detects the likeliest mistake - listing a
# category under the wrong endpoint - and says which one it belongs to.
for _source in settings.sources:
    if not _source.categories:
        raise ValueError(
            f"config.yaml: source {_source.game!r} lists no categories."
        )
    _types = [c.type for c in _source.categories]
    if len(_types) != len(set(_types)):
        raise ValueError(
            f"config.yaml: duplicate categories for {_source.game!r} ({_types})."
        )
    for _category in _source.categories:
        validate_category(
            _source.game,
            _category.endpoint,
            _category.type,
            allow_unknown=settings.allow_unknown_types,
        )
