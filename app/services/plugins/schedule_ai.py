"""Schedule coordination plugin using AI natural language processing."""

import logging
import re
from typing import Optional

from sqlalchemy.orm import Session

from app.models.core import ConversationHistory
from app.services.ai_client import chat_with_ai
from app.services.base_plugin import BasePlugin

logger = logging.getLogger("smartexec.plugin.schedule_ai")

SCHEDULE_KEYWORDS = [
    "日程", "スケジュール", "予定", "空き", "調整",
    "ミーティング", "会議", "打ち合わせ", "アポ",
    "いつ", "何時", "カレンダー",
]

SYSTEM_PROMPT = """\
あなたは「AI Shaker」の日程調整AIアシスタントです。
ユーザーの日程調整リクエストを理解し、適切な候補日時を提案してください。

あなたの役割:
1. ユーザーが希望する日程の条件を把握する
2. 候補日時を3〜5つ提案する
3. 参加者の都合を考慮して最適な日程を選ぶ

注意事項:
- 現在はカレンダーAPIと未連携のため、一般的なビジネス時間帯で候補を提案してください
- 平日9:00〜18:00の範囲で提案してください
- 日本語で丁寧に回答してください
- 具体的な日付を提案する場合は「○月○日（○曜日）○時〜」の形式で
- ユーザーが確定を希望したら「承知しました。○月○日○時で確定しました」と返答してください

将来的にGoogle Calendar APIと連携する予定です。
現時点では候補日の提案のみ行います。
"""


class ScheduleAIPlugin(BasePlugin):
    """AI-powered schedule coordination plugin."""

    @property
    def menu_id(self) -> str:
        return "schedule_ai"

    def should_handle(self, user_message: str) -> bool:
        msg_lower = user_message.lower()
        return any(kw in msg_lower for kw in SCHEDULE_KEYWORDS)

    def handle(self, user_message: str, line_user_id: str, db: Session) -> Optional[str]:
        logger.info("ScheduleAI handling message from %s", line_user_id)

        # Load conversation history for this plugin
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

        from app.models.core import Tenant

        tenant = db.query(Tenant).filter_by(id=self.tenant_id).first()
        tenant_config = tenant.config if tenant else {}

        reply = chat_with_ai(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            conversation_history=conversation_history,
            tenant_config=tenant_config,
        )

        # Save conversation
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
