"""Pydantic schemas for Ticket operations."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TicketAddRequest(BaseModel):
    tenant_id: str
    tickets: int
    description: str = "Admin refill"


class TicketBalanceResponse(BaseModel):
    tenant_id: str
    tenant_name: str
    current_balance: int
    logs: list[dict[str, Any]] = []


class TicketLogEntry(BaseModel):
    id: int
    tenant_id: str
    action: str
    tickets_consumed: int
    description: str
    created_at: datetime

    model_config = {"from_attributes": True}
