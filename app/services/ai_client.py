"""Unified AI client — supports Gemini (default) and Claude (BYOK)."""

import logging
import os
from typing import Optional

logger = logging.getLogger("smartexec.ai")

# Gemini setup
_gemini_model = None


def _get_gemini_model():
    global _gemini_model
    if _gemini_model is None:
        import google.generativeai as genai

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set")
        genai.configure(api_key=api_key)
        _gemini_model = genai.GenerativeModel("gemini-2.0-flash")
    return _gemini_model


def chat_with_ai(
    system_prompt: str,
    user_message: str,
    conversation_history: Optional[list[dict[str, str]]] = None,
    tenant_config: Optional[dict] = None,
) -> str:
    """Send a message to an AI model and get a response.

    Uses Claude if tenant has BYOK config, otherwise Gemini.
    """
    # Check BYOK (Bring Your Own Key) — tenant can provide their Anthropic key
    if tenant_config and tenant_config.get("byok", {}).get("anthropic_key"):
        return _chat_claude(
            system_prompt,
            user_message,
            conversation_history,
            tenant_config["byok"],
        )

    return _chat_gemini(system_prompt, user_message, conversation_history)


def _chat_gemini(
    system_prompt: str,
    user_message: str,
    conversation_history: Optional[list[dict[str, str]]] = None,
) -> str:
    """Call Google Gemini API."""
    try:
        model = _get_gemini_model()

        # Build prompt with history
        parts = [system_prompt, ""]
        if conversation_history:
            for entry in conversation_history[-10:]:  # last 10 messages
                role_label = "User" if entry["role"] == "user" else "Assistant"
                parts.append(f"{role_label}: {entry['content']}")
            parts.append("")
        parts.append(f"User: {user_message}")

        full_prompt = "\n".join(parts)
        response = model.generate_content(full_prompt)
        return response.text.strip()

    except Exception as e:
        logger.error("Gemini API error: %s", e, exc_info=True)
        return f"AI\u51e6\u7406\u4e2d\u306b\u30a8\u30e9\u30fc\u304c\u767a\u751f\u3057\u307e\u3057\u305f\u3002\u3057\u3070\u3089\u304f\u3057\u3066\u304b\u3089\u3082\u3046\u4e00\u5ea6\u304a\u8a66\u3057\u304f\u3060\u3055\u3044\u3002"


def _chat_claude(
    system_prompt: str,
    user_message: str,
    conversation_history: Optional[list[dict[str, str]]] = None,
    byok_config: Optional[dict] = None,
) -> str:
    """Call Anthropic Claude API with tenant's own key."""
    try:
        from anthropic import Anthropic

        api_key = byok_config.get("anthropic_key") if byok_config else None
        if not api_key:
            api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return _chat_gemini(system_prompt, user_message, conversation_history)

        client = Anthropic(api_key=api_key)
        model = byok_config.get("model", "claude-sonnet-4-5") if byok_config else "claude-sonnet-4-5"

        messages = []
        if conversation_history:
            for entry in conversation_history[-10:]:
                messages.append({"role": entry["role"], "content": entry["content"]})
        messages.append({"role": "user", "content": user_message})

        response = client.messages.create(
            model=model,
            max_tokens=2048,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text.strip()

    except Exception as e:
        logger.error("Claude API error: %s — falling back to Gemini", e)
        return _chat_gemini(system_prompt, user_message, conversation_history)
