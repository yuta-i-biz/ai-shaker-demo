"""Pydantic schemas for Tenant operations."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class TenantCreate(BaseModel):
    name: str
    industry: str = ""
    line_user_id: Optional[str] = None
    config: dict[str, Any] = {}


class TenantResponse(BaseModel):
    id: str
    name: str
    industry: str
    config: dict[str, Any]
    line_user_id: Optional[str]
    created_at: datetime
    ticket_balance: int = 0
    menus: list[dict[str, Any]] = []

    model_config = {"from_attributes": True}


class TenantConfigUpdate(BaseModel):
    config: dict[str, Any]
