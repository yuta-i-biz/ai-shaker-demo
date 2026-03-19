"""SQLAlchemy models for SmartExec."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text

from app.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    industry = Column(String, default="")
    config = Column(JSON, default=dict)
    line_user_id = Column(String, unique=True, index=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ServiceMenu(Base):
    __tablename__ = "service_menus"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, default="")
    base_ticket_cost = Column(Integer, default=2)
    is_active = Column(Boolean, default=True)


class TenantMenu(Base):
    __tablename__ = "tenant_menus"

    tenant_id = Column(String, ForeignKey("tenants.id"), primary_key=True)
    menu_id = Column(String, ForeignKey("service_menus.id"), primary_key=True)
    status = Column(String, default="enabled")  # "enabled" | "disabled"
    installed_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class TicketBalance(Base):
    __tablename__ = "ticket_balances"

    tenant_id = Column(String, ForeignKey("tenants.id"), primary_key=True)
    current_balance = Column(Integer, default=10)


class TicketLog(Base):
    __tablename__ = "ticket_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, ForeignKey("tenants.id"))
    action = Column(String)  # "install_menu" | "admin_add" etc.
    tickets_consumed = Column(Integer)  # negative for refills
    description = Column(String, default="")
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class MenuDevSession(Base):
    __tablename__ = "menu_dev_sessions"

    id = Column(String, primary_key=True)
    menu_name = Column(String, default="")
    status = Column(String, default="created")
    # status: created -> uploaded -> analyzed -> questioning -> finalized -> generated
    gemini_analysis = Column(JSON, default=dict)
    qa_history = Column(JSON, default=list)
    spec_markdown = Column(Text, default="")
    generated_code = Column(Text, default="")
    tenant_config_items = Column(JSON, default=list)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ConversationHistory(Base):
    """Stores per-user conversation history for multi-turn AI interactions."""

    __tablename__ = "conversation_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    line_user_id = Column(String, index=True)
    role = Column(String)  # "user" | "assistant"
    content = Column(Text)
    plugin_id = Column(String, default="line_complete")
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
