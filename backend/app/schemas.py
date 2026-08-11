"""
Pydantic schemas for API responses.

Separate from the SQLAlchemy models in app/models/ on purpose: those
describe database tables, these describe what the API returns, and the
two do not always match 1:1.
"""

from datetime import datetime

from pydantic import BaseModel


class GameOption(BaseModel):
    """One entry in GET /games - what the frontend offers on first load."""

    game: str
    league: str
    label: str


class ItemSummary(BaseModel):
    """One row in GET /items."""

    id: int
    name: str
    category: str
    game: str
    source_league: str
    image_url: str | None = None
    latest_value_in_chaos: float | None = None
    latest_value_in_exalted: float | None = None
    latest_value_in_divine: float | None = None

    model_config = {"from_attributes": True}


class PricePoint(BaseModel):
    value: float
    collected_at: datetime

    model_config = {"from_attributes": True}


class ItemHistory(BaseModel):
    item_name: str
    game: str
    league: str
    currency: str
    points: list[PricePoint]