"""Pattern D: General-purpose AI assistant plugin."""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.core import ConversationHistory
from app.services.ai_client import chat_with_ai
from app.services.base_plugin import BasePlugin

logger = logging.getLogger("smartexec.plugin.line_complete")

SYSTEM_PROMPT = """\
あなたは「AI Shaker」のAIアシスタントです。
企業の業務をサポートするために、ユーザーの質問に丁寧かつ的確に回答してください。

ガイドライン:
- 日本語で回答してください
- 簡潔でわかりやすい回答を心がけてください
- ビジネスシーンにふさわしい丁寧な口調で回答してください
- わからないことは正直に「わかりません」と答えてください
- 機密情報や個人情報の取り扱いには注意してください
"""


class LineCompletePlugin(BasePlugin):
    """Catch-all AI assistant — handles any message not caught by other plugins."""

    @property
    def menu_id(self) -> str:
        return "line_complete"

    def should_handle(self, user_message: str) -> bool:
        # Catch-all: always handles if no other plugin matched
        return True

    def handle(self, user_message: str, line_user_id: str, db: Session) -> Optional[str]:
        logger.info("LineComplete handling message from %s", line_user_id)

        # Load conversation history
        history_rows = (
            db.query(ConversationHistory)
            .filter_by(line_user_id=line_user_id, plugin_id=self.menu_id)
            .order_by(ConversationHistory.created_at.desc())
            .limit(10)
            .all()
        )
        history_rows.reverse()
        conversation_history = [
            {"role": row.role, "content": row.content} for row in history_rows
        ]

        # Get tenant config for BYOK
        from app.models.core import Tenant

        tenant = db.query(Tenant).filter_by(id=self.tenant_id).first()
        tenant_config = tenant.config if tenant else {}

        # Call AI
        reply = chat_with_ai(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            conversation_history=conversation_history,
            tenant_config=tenant_config,
        )

        # Save conversation history
        db.add(ConversationHistory(
            tenant_id=self.tenant_id,
            line_user_id=line_user_id,
            role="user",
            content=user_message,
            plugin_id=self.menu_id,
        ))
        db.add(ConversationHistory(
            tenant_id=self.tenant_id,
            line_user_id=line_user_id,
            role="assistant",
            content=reply,
            plugin_id=self.menu_id,
        ))
        db.commit()

        return reply
