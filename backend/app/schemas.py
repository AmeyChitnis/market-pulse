"""
Pydantic schemas for API responses.
"""

from datetime import datetime

from pydantic import BaseModel


class ItemSummary(BaseModel):
    id: int
    name: str
    category: str
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
    league: str
    currency: str
    points: list[PricePoint]