"""
PriceSnapshot model: a single price observation for an item at a point in
time. This table is the time series — every collector run inserts new
rows here rather than updating existing ones, so history accumulates
naturally and nothing is ever overwritten.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("items.id", ondelete="CASCADE"), index=True
    )

    chaos_value: Mapped[float] = mapped_column(Float)
    divine_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    listing_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    item: Mapped["Item"] = relationship(back_populates="snapshots")

    def __repr__(self) -> str:
        return (
            f"<PriceSnapshot item_id={self.item_id} chaos_value={self.chaos_value} "
            f"collected_at={self.collected_at}>"
        )
