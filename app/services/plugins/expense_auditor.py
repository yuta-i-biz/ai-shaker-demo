"""Expense auditor plugin (skeleton)."""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.services.base_plugin import BasePlugin

logger = logging.getLogger("smartexec.plugin.expense")

EXPENSE_KEYWORDS = ["経費", "レシート", "領収書", "精算", "立替", "交通費"]


class ExpenseAuditorPlugin(BasePlugin):
    """Expense auditing plugin — currently skeleton only.

    TODO: Implement LINE image receipt -> Gemini OCR -> freee API journal entry.
    """

    @property
    def menu_id(self) -> str:
        return "expense_auditor"

    def should_handle(self, user_message: str) -> bool:
        return any(kw in user_message for kw in EXPENSE_KEYWORDS)

    def handle(self, user_message: str, line_user_id: str, db: Session) -> Optional[str]:
        logger.info("ExpenseAuditor handling message from %s", line_user_id)
        return (
            "経費精算機能は現在準備中です。\n"
            "近日中にレシート画像を送るだけで自動仕訳できるようになります。\n"
            "もうしばらくお待ちください。"
        )
