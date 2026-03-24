
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from ..config import settings
class Base(DeclarativeBase):
    pass
class SessionModel(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    jwt_jti: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
class TableModel(Base):
    __tablename__ = "tables"

    table_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    rules_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(32), default="open")  # open, active, abandoned, closed

    hands: Mapped[list["HandModel"]] = relationship("HandModel", back_populates="table")
class HandModel(Base):
    __tablename__ = "hands"

    hand_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    table_id: Mapped[str] = mapped_column(String(64), ForeignKey("tables.table_id"), nullable=False)
    hand_number: Mapped[int] = mapped_column(Integer, nullable=False)
    rules_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    table: Mapped["TableModel"] = relationship("TableModel", back_populates="hands")
    actions: Mapped[list["ActionModel"]] = relationship("ActionModel", back_populates="hand")
    results: Mapped[list["HandResultModel"]] = relationship("HandResultModel", back_populates="hand")
class ActionModel(Base):
    __tablename__ = "actions"

    action_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    hand_id: Mapped[str] = mapped_column(String(64), ForeignKey("hands.hand_id"), nullable=False)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    street: Mapped[str] = mapped_column(String(32), nullable=False)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, default=0)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    hand: Mapped["HandModel"] = relationship("HandModel", back_populates="actions")
class HandResultModel(Base):
    __tablename__ = "hand_results"

    # Composite primary key: hand_id + session_id
    hand_id: Mapped[str] = mapped_column(String(64), ForeignKey("hands.hand_id"), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    hole_cards_json: Mapped[str] = mapped_column(Text, nullable=False)
    best_hand: Mapped[str] = mapped_column(String(64), nullable=False)
    board: Mapped[str] = mapped_column(Text, nullable=False)
    amount_won: Mapped[int] = mapped_column(Integer, default=0)

    hand: Mapped["HandModel"] = relationship("HandModel", back_populates="results")
# ---------------------------------------------------------------------------
# Async engine and session factory
# ---------------------------------------------------------------------------

engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
async def init_db() -> None:
    """Create all tables (for development; use Alembic for production migrations)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
