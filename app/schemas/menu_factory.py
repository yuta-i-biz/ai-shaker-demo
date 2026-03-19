"""Pydantic schemas for Menu Factory operations."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class SessionCreate(BaseModel):
    menu_name: str


class SessionResponse(BaseModel):
    id: str
    menu_name: str
    status: str
    gemini_analysis: Optional[dict[str, Any]] = None
    qa_history: list[dict[str, Any]] = []
    spec_markdown: Optional[str] = None
    generated_code: Optional[str] = None
    tenant_config_items: Optional[list[dict[str, Any]]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AnswerRequest(BaseModel):
    answers: list[dict[str, str]]


class MenuInstallRequest(BaseModel):
    menu_id: str
    action: str = "install"  # "install" | "enable" | "disable"
