from sqlalchemy import String, Float, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from db import Base
from sqlalchemy import DateTime, func

class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    theme: Mapped[str] = mapped_column(String, nullable=False)
    rarity: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    date: Mapped[str] = mapped_column(String, nullable=False)  # keep as string for MVP
    summary: Mapped[str] = mapped_column(String, nullable=False)
    briefing_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    key_points_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    entities_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    source: Mapped[str] = mapped_column(String, nullable=False)
    freshness_status: Mapped[str] = mapped_column(String, nullable=False, default="fresh")
    freshness_age_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    url: Mapped[str] = mapped_column(String, nullable=False, default="")




class SavedSignal(Base):
    __tablename__ = "saved_signals"

    # No login yet -> treat this as a single demo user's vault
    signal_id: Mapped[str] = mapped_column(String, primary_key=True)
    saved_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
