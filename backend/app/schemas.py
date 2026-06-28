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
    latest_primary_value: float | None = None
    primary_currency: str | None = None

    model_config = {"from_attributes": True}


class PricePoint(BaseModel):
    primary_value: float
    collected_at: datetime

    model_config = {"from_attributes": True}


class ItemHistory(BaseModel):
    item_name: str
    league: str
    primary_currency: str
    points: list[PricePoint]