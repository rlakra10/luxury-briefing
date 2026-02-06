from sqlalchemy import String, Float, Date
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
    source: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False, default="")




class SavedSignal(Base):
    __tablename__ = "saved_signals"

    # No login yet -> treat this as a single demo user's vault
    signal_id: Mapped[str] = mapped_column(String, primary_key=True)
    saved_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
