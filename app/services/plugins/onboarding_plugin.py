"""Onboarding plugin (skeleton)."""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.services.base_plugin import BasePlugin

logger = logging.getLogger("smartexec.plugin.onboarding")

ONBOARDING_KEYWORDS = ["オンボーディング", "入社", "新人", "研修", "入社手続"]


class OnboardingPlugin(BasePlugin):
    """Employee onboarding automation — currently skeleton only.

    TODO: Implement onboarding workflow automation.
    """

    @property
    def menu_id(self) -> str:
        return "onboarding"

    def should_handle(self, user_message: str) -> bool:
        return any(kw in user_message for kw in ONBOARDING_KEYWORDS)

    def handle(self, user_message: str, line_user_id: str, db: Session) -> Optional[str]:
        logger.info("Onboarding handling message from %s", line_user_id)
        return (
            "オンボーディング機能は現在準備中です。\n"
            "近日中に新入社員の手続きを自動化できるようになります。\n"
            "もうしばらくお待ちください。"
        )
