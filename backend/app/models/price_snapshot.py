"""
PriceSnapshot model: a single price observation for an item at a point in
time. This table is the time series - every collector run inserts new
rows here rather than updating existing ones, so history accumulates
naturally and nothing is ever overwritten.

The price is stored as `primary_value`: the item's price denominated in
whatever poe.ninja's `core.primary` currency is for that game/league at
collection time. This is NOT always chaos - PoE1 leagues are typically
chaos-denominated, but PoE2 leagues have been observed using divine as
the primary unit instead. `primary_currency` records which currency
`primary_value` is actually expressed in, so this never has to be
guessed or assumed later.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("items.id", ondelete="CASCADE"), index=True
    )

    primary_value: Mapped[float] = mapped_column(Float)
    primary_currency: Mapped[str] = mapped_column(String(50), default="chaos")
    listing_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    item: Mapped["Item"] = relationship(back_populates="snapshots")

    def __repr__(self) -> str:
        return (
            f"<PriceSnapshot item_id={self.item_id} "
            f"primary_value={self.primary_value} {self.primary_currency} "
            f"collected_at={self.collected_at}>"
        )