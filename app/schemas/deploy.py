"""Pydantic schemas for Limb deployment."""

from pydantic import BaseModel


class DeployLimbRequest(BaseModel):
    pattern: str = "D"  # A, B, C, D
    menus: list[str] = []
