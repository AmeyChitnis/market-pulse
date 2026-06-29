"""
PriceSnapshot model: a single price observation for an item at a point in
time. This table is the time series - every collector run inserts new
rows here rather than updating existing ones, so history accumulates
naturally and nothing is ever overwritten.

PRICING - multiple currencies stored per row:
    Earlier versions stored a single `primary_value` priced in whatever
    currency poe.ninja's `maxVolumeCurrency` said was most popular for
    that item at that moment. This turned out to be unstable for
    low-liquidity items: poe.ninja's "most popular pairing" can flip
    between collection runs (e.g. divine one run, exalted the next) even
    though the item's REAL price barely moved - this showed up as a
    fake-looking spike on price charts, since the same real value was
    being expressed in two very differently-scaled units back to back.

    Fix: store the price in all three currencies poe.ninja tracks rates
    for (chaos, exalted, divine) on every row, computed from poe.ninja's
    own core.rates at collection time. A chart can now stay in ONE
    currency for an item's entire history, regardless of which currency
    poe.ninja happened to consider "most popular" at any given moment.
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

    # Legacy fields - poe.ninja's own "most popular currency" pick at
    # collection time. Kept for backward compatibility.
    primary_value: Mapped[float] = mapped_column(Float)
    primary_currency: Mapped[str] = mapped_column(String(50), default="chaos")

    # Explicit, stable-per-currency values.
    value_in_chaos: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_in_exalted: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_in_divine: Mapped[float | None] = mapped_column(Float, nullable=True)

    listing_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    item: Mapped["Item"] = relationship(back_populates="snapshots")

    def __repr__(self) -> str:
        return (
            f"<PriceSnapshot item_id={self.item_id} "
            f"chaos={self.value_in_chaos} exalted={self.value_in_exalted} "
            f"divine={self.value_in_divine} collected_at={self.collected_at}>"
        )