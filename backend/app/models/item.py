"""
Item model: a tradeable asset being tracked.

Kept deliberately generic - `game`, `category` and `source_league` say
where a row came from, but nothing here is named after a specific game,
so a collector for a different market could populate the same table.

WHY THE UNIQUE CONSTRAINT INCLUDES `game`:
Both PoE1 and PoE2 have leagues literally named "Standard" and
"Hardcore", and both games have a "Chaos Orb". Without `game` in the
constraint, ('Chaos Orb', 'Standard') collides across games and the
collector's get-or-create would silently reuse the wrong row - writing
one game's prices onto the other game's history.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        UniqueConstraint(
            "game", "name", "source_league", name="uq_item_game_name_league"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    category: Mapped[str] = mapped_column(String(100), index=True)
    game: Mapped[str] = mapped_column(String(10), index=True)
    source_league: Mapped[str] = mapped_column(String(100), index=True)
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    snapshots: Mapped[list["PriceSnapshot"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Item id={self.id} game={self.game!r} name={self.name!r} "
            f"league={self.source_league!r}>"
        )