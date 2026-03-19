"""LINE Webhook handler — receives messages, dispatches to plugins."""

import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.core import (
    ServiceMenu,
    Tenant,
    TenantMenu,
    TicketBalance,
)

logger = logging.getLogger("smartexec.line")

router = APIRouter()

# Default menus installed for new tenants
DEFAULT_MENUS = ["schedule_ai", "line_complete"]

# Plugin priority order (first match wins)
PLUGIN_PRIORITY = [
    "schedule_ai",
    "expense_auditor",
    "hr_management",
    "onboarding",
    "line_complete",  # catch-all, always last
]


def _get_line_config():
    """Get LINE SDK configuration."""
    channel_secret = os.getenv("LINE_CHANNEL_SECRET", "")
    channel_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    return channel_secret, channel_token


def _verify_signature(body: bytes, signature: str, channel_secret: str) -> bool:
    """Verify LINE webhook signature using HMAC-SHA256."""
    import hashlib
    import hmac
    import base64

    if not channel_secret or not signature:
        logger.warning("Missing channel_secret or signature for verification")
        return False

    hash_value = hmac.new(
        channel_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).digest()
    expected_signature = base64.b64encode(hash_value).decode("utf-8")

    return hmac.compare_digest(signature, expected_signature)


def _load_plugin(menu_id: str, tenant_id: str, tenant_config: dict):
    """Dynamically load a plugin instance by menu_id."""
    from app.services.plugins.line_complete import LineCompletePlugin
    from app.services.plugins.schedule_ai import ScheduleAIPlugin
    from app.services.plugins.expense_auditor import ExpenseAuditorPlugin
    from app.services.plugins.hr_management import HRManagementPlugin
    from app.services.plugins.onboarding_plugin import OnboardingPlugin

    plugin_map = {
        "line_complete": LineCompletePlugin,
        "schedule_ai": ScheduleAIPlugin,
        "expense_auditor": ExpenseAuditorPlugin,
        "hr_management": HRManagementPlugin,
        "onboarding": OnboardingPlugin,
    }

    plugin_class = plugin_map.get(menu_id)
    if not plugin_class:
        return None

    menu_config = tenant_config.get("menus", {}).get(menu_id, {})
    return plugin_class(tenant_id=tenant_id, config=menu_config)


def _get_or_create_tenant(line_user_id: str, db: Session) -> Tenant:
    """Find tenant by LINE user ID, or auto-create one."""
    tenant = db.query(Tenant).filter_by(line_user_id=line_user_id).first()
    if tenant:
        return tenant

    # Auto-create tenant
    tenant_id = str(uuid.uuid4())
    tenant = Tenant(
        id=tenant_id,
        name=f"Auto-{line_user_id[:8]}",
        line_user_id=line_user_id,
        config={"deployment_pattern": "D"},
    )
    db.add(tenant)

    # Add initial ticket balance
    db.add(TicketBalance(tenant_id=tenant_id, current_balance=10))

    # Install default menus
    for menu_id in DEFAULT_MENUS:
        menu = db.query(ServiceMenu).filter_by(id=menu_id, is_active=True).first()
        if menu:
            db.add(TenantMenu(tenant_id=tenant_id, menu_id=menu_id, status="enabled"))

    db.commit()
    logger.info("Auto-created tenant %s for LINE user %s", tenant_id, line_user_id)
    return tenant


def _reply_to_line(reply_token: str, text: str, channel_token: str):
    """Send a reply message via LINE Messaging API."""
    import httpx

    if not channel_token:
        logger.error("LINE_CHANNEL_ACCESS_TOKEN is not set — cannot reply")
        return

    # Truncate long messages (LINE limit is 5000 chars)
    if len(text) > 4900:
        text = text[:4900] + "\n\n...(メッセージが長すぎるため省略されました)"

    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {channel_token}",
    }
    payload = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text}],
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                logger.error(
                    "LINE reply failed: status=%d body=%s",
                    resp.status_code,
                    resp.text,
                )
            else:
                logger.info("LINE reply sent successfully")
    except Exception as e:
        logger.error("Failed to send LINE reply: %s", e, exc_info=True)


def _handle_text_message(
    line_user_id: str,
    reply_token: str,
    user_message: str,
    channel_token: str,
    db: Session,
):
    """Process a text message through the plugin pipeline."""
    # Get or create tenant
    tenant = _get_or_create_tenant(line_user_id, db)
    tenant_config = tenant.config or {}

    # Get enabled menus for this tenant
    enabled_menus = (
        db.query(TenantMenu)
        .filter_by(tenant_id=tenant.id, status="enabled")
        .all()
    )
    enabled_menu_ids = {tm.menu_id for tm in enabled_menus}

    # Try plugins in priority order
    for menu_id in PLUGIN_PRIORITY:
        if menu_id not in enabled_menu_ids:
            continue

        plugin = _load_plugin(menu_id, tenant.id, tenant_config)
        if plugin is None:
            continue

        if plugin.should_handle(user_message):
            logger.info(
                "Plugin '%s' handling message from tenant %s",
                menu_id,
                tenant.id,
            )
            try:
                reply = plugin.handle(user_message, line_user_id, db)
                if reply:
                    _reply_to_line(reply_token, reply, channel_token)
                    return
            except Exception as e:
                logger.error(
                    "Plugin '%s' error: %s",
                    menu_id,
                    e,
                    exc_info=True,
                )
                _reply_to_line(
                    reply_token,
                    "申し訳ございません。処理中にエラーが発生しました。\n"
                    "しばらくしてからもう一度お試しください。",
                    channel_token,
                )
                return

    # No plugin matched — fallback
    _reply_to_line(
        reply_token,
        "メッセージを受け取りました。\n"
        "現在ご利用いただけるメニューが見つかりませんでした。\n"
        "管理者にお問い合わせください。",
        channel_token,
    )


@router.post("/webhook/line")
async def line_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_line_signature: Optional[str] = Header(None),
):
    """LINE Webhook endpoint.

    Receives events from LINE, verifies signature, and dispatches to plugins.
    Always returns 200 OK to LINE (to avoid retries), even on errors.
    """
    channel_secret, channel_token = _get_line_config()

    # Read raw body for signature verification
    body = await request.body()

    # Verify signature
    if channel_secret and x_line_signature:
        if not _verify_signature(body, x_line_signature, channel_secret):
            logger.warning("LINE signature verification failed")
            # Return 200 anyway to prevent LINE from retrying
            return JSONResponse(
                status_code=200,
                content={"status": "signature_invalid"},
            )
    elif channel_secret and not x_line_signature:
        logger.warning("Missing X-Line-Signature header")
        return JSONResponse(
            status_code=200,
            content={"status": "missing_signature"},
        )

    # Parse events
    try:
        import json

        body_json = json.loads(body)
        events = body_json.get("events", [])
    except Exception as e:
        logger.error("Failed to parse LINE webhook body: %s", e)
        return {"status": "parse_error"}

    # Process each event
    for event in events:
        event_type = event.get("type")
        logger.info("LINE event: type=%s", event_type)

        if event_type == "message":
            message = event.get("message", {})
            msg_type = message.get("type")
            reply_token = event.get("replyToken", "")
            source = event.get("source", {})
            line_user_id = source.get("userId", "")

            if not line_user_id:
                logger.warning("No userId in event source")
                continue

            if msg_type == "text":
                user_text = message.get("text", "").strip()
                if user_text:
                    try:
                        _handle_text_message(
                            line_user_id,
                            reply_token,
                            user_text,
                            channel_token,
                            db,
                        )
                    except Exception as e:
                        logger.error(
                            "Error handling text message: %s",
                            e,
                            exc_info=True,
                        )
                        _reply_to_line(
                            reply_token,
                            "申し訳ございません。システムエラーが発生しました。\n"
                            "管理者に連絡してください。",
                            channel_token,
                        )
            else:
                # Non-text messages (image, video, etc.)
                _reply_to_line(
                    reply_token,
                    f"「{msg_type}」タイプのメッセージを受信しました。\n"
                    "現在、テキストメッセージのみ対応しています。",
                    channel_token,
                )

        elif event_type == "follow":
            # User added the bot as friend
            reply_token = event.get("replyToken", "")
            source = event.get("source", {})
            line_user_id = source.get("userId", "")
            if line_user_id:
                _get_or_create_tenant(line_user_id, db)
                _reply_to_line(
                    reply_token,
                    "AI Shakerへようこそ！\n\n"
                    "以下の機能がご利用いただけます：\n"
                    "・何でも質問 → AIが回答します\n"
                    "・「日程調整」→ スケジュール調整をサポート\n"
                    "・「経費」→ 経費精算（準備中）\n"
                    "・「勤怠」→ 勤怠管理（準備中）\n\n"
                    "まずは何か話しかけてみてください！",
                    channel_token,
                )

        elif event_type == "unfollow":
            logger.info("User unfollowed the bot")

        else:
            logger.info("Unhandled event type: %s", event_type)

    return {"status": "ok"}
