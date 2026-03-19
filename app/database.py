"""Database connection and session management."""

import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

def _default_db_url() -> str:
    """Return the default SQLite URL, using /data/app.db if the volume is mounted."""
    if os.path.isdir("/data"):
        return "sqlite:////data/app.db"
    return "sqlite:///./smart_exec.db"


DATABASE_URL = os.getenv("DATABASE_URL", _default_db_url())

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency that yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables and seed initial data."""
    from app.models.core import (  # noqa: F401
        MenuDevSession,
        ServiceMenu,
        Tenant,
        TenantMenu,
        TicketBalance,
        TicketLog,
    )

    Base.metadata.create_all(bind=engine)
    _seed_menus()


def _seed_menus():
    """Insert default ServiceMenu records if they don't exist."""
    from app.models.core import ServiceMenu

    default_menus = [
        {
            "id": "line_complete",
            "name": "AI\u30a2\u30b7\u30b9\u30bf\u30f3\u30c8",
            "description": "\u6c4e\u7528AI\u30c1\u30e3\u30c3\u30c8\u30dc\u30c3\u30c8\u3002\u8cea\u554f\u306b\u4f55\u3067\u3082\u7b54\u3048\u307e\u3059\u3002",
            "base_ticket_cost": 1,
        },
        {
            "id": "schedule_ai",
            "name": "\u65e5\u7a0b\u8abf\u6574AI",
            "description": "AI\u304c\u81ea\u7136\u8a00\u8a9e\u3067\u65e5\u7a0b\u8abf\u6574\u3092\u30b5\u30dd\u30fc\u30c8\u3057\u307e\u3059\u3002",
            "base_ticket_cost": 2,
        },
        {
            "id": "expense_auditor",
            "name": "\u7d4c\u8cbb\u7cbe\u7b97",
            "description": "\u30ec\u30b7\u30fc\u30c8\u753b\u50cf\u3092\u9001\u308b\u3060\u3051\u3067\u7d4c\u8cbb\u7cbe\u7b97\u3002",
            "base_ticket_cost": 3,
        },
        {
            "id": "hr_management",
            "name": "\u4eba\u4e8b\u7ba1\u7406",
            "description": "\u52e4\u6020\u6253\u523b\u30fb\u4eba\u4e8b\u60c5\u5831\u7ba1\u7406\u3002",
            "base_ticket_cost": 2,
        },
        {
            "id": "onboarding",
            "name": "\u30aa\u30f3\u30dc\u30fc\u30c7\u30a3\u30f3\u30b0",
            "description": "\u65b0\u5165\u793e\u54e1\u306e\u30aa\u30f3\u30dc\u30fc\u30c7\u30a3\u30f3\u30b0\u3092\u81ea\u52d5\u5316\u3002",
            "base_ticket_cost": 2,
        },
    ]

    db = SessionLocal()
    try:
        for menu_data in default_menus:
            existing = db.query(ServiceMenu).filter_by(id=menu_data["id"]).first()
            if not existing:
                db.add(ServiceMenu(**menu_data))
        db.commit()
    finally:
        db.close()
