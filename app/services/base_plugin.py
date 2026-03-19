"""Base plugin class for SmartExec menu plugins."""

from abc import ABC, abstractmethod
from typing import Optional

from sqlalchemy.orm import Session


class BasePlugin(ABC):
    """Abstract base class for all SmartExec plugins.

    Each plugin handles a specific business function (menu).
    """

    def __init__(self, tenant_id: str, config: dict):
        self.tenant_id = tenant_id
        self.config = config  # tenant config["menus"][menu_id] or {}

    @property
    @abstractmethod
    def menu_id(self) -> str:
        """ServiceMenu ID (e.g. 'line_complete')."""

    @abstractmethod
    def should_handle(self, user_message: str) -> bool:
        """Return True if this plugin should handle the given message."""

    @abstractmethod
    def handle(self, user_message: str, line_user_id: str, db: Session) -> Optional[str]:
        """Process the message and return a reply string. None means no reply."""
