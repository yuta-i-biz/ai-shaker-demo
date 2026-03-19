"""HR management plugin (skeleton)."""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.services.base_plugin import BasePlugin

logger = logging.getLogger("smartexec.plugin.hr")

HR_KEYWORDS = ["勤怠", "出勤", "退勤", "打刻", "有給", "休暇", "人事"]


class HRManagementPlugin(BasePlugin):
    """HR management plugin — currently skeleton only.

    TODO: Implement attendance tracking -> Google Sheets integration.
    """

    @property
    def menu_id(self) -> str:
        return "hr_management"

    def should_handle(self, user_message: str) -> bool:
        return any(kw in user_message for kw in HR_KEYWORDS)

    def handle(self, user_message: str, line_user_id: str, db: Session) -> Optional[str]:
        logger.info("HRManagement handling message from %s", line_user_id)
        return (
            "人事管理機能は現在準備中です。\n"
            "近日中に勤怠打刻や有給管理ができるようになります。\n"
            "もうしばらくお待ちください。"
        )
