"""SQLAlchemy engine and small persistence boundary."""
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .models import Base, PortfolioSnapshotRecord
from .settings import settings


def _engine_url() -> str:
    url = settings.database_url
    if url.startswith("sqlite:///"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    return url


DATABASE_URL = _engine_url()
engine_kwargs: dict[str, object] = {"future": True, "pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def ping_db() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def save_paper_snapshot(*, equity: float, daily_pnl: float, drawdown_percent: float, open_positions: int) -> None:
    with SessionLocal() as session:
        session.add(
            PortfolioSnapshotRecord(
                equity=equity,
                daily_pnl=daily_pnl,
                open_positions=open_positions,
                drawdown_percent=drawdown_percent,
                mode="paper",
                captured_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
