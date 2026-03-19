"""Menu Factory service — Gemini analysis + AI Q&A + code generation."""

import json
import logging
import os
from typing import Any

logger = logging.getLogger("smartexec.menu_factory")


def _get_gemini_model():
    import google.generativeai as genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-2.0-flash")


def analyze_with_gemini(session) -> dict[str, Any]:
    """Analyze uploaded content with Gemini to extract business requirements."""
    model = _get_gemini_model()

    raw_input = ""
    if session.gemini_analysis and isinstance(session.gemini_analysis, dict):
        raw_input = session.gemini_analysis.get("raw_input", "")

    prompt = f"""\
以下の業務資料を分析し、LINEボットのプラグインとして自動化できる業務フローを抽出してください。

JSON形式で以下の構造で回答してください:
{{
  "business_flows": [
    {{
      "name": "フロー名",
      "description": "フローの説明",
      "trigger_keywords": ["トリガーキーワード1", "キーワード2"],
      "steps": ["ステップ1", "ステップ2"],
      "external_systems": ["連携先システム"],
      "implementation_pattern": "A/B/C/D"
    }}
  ],
  "required_config": [
    {{
      "key": "設定キー",
      "description": "設定の説明",
      "type": "string/number/boolean"
    }}
  ],
  "complexity": "low/medium/high",
  "estimated_ticket_cost": 2
}}

--- 業務資料 ---
{raw_input}
"""

    response = model.generate_content(prompt)
    text = response.text.strip()

    # Try to parse JSON from response
    try:
        # Remove markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "raw_analysis": text,
            "raw_input": raw_input,
            "business_flows": [],
            "complexity": "unknown",
        }


def generate_questions(session) -> list[dict[str, str]]:
    """Generate clarifying questions based on Gemini analysis."""
    model = _get_gemini_model()

    analysis = session.gemini_analysis or {}
    qa_history = session.qa_history or []

    prompt = f"""\
あなたはAIプラグイン開発のコンサルタントです。
以下の業務分析結果に基づいて、プラグイン開発に必要な追加情報を得るための質問を3〜5つ生成してください。

JSON配列形式で回答してください:
[
  {{"id": "q1", "question": "質問内容", "purpose": "この質問の目的"}},
  ...
]

--- 分析結果 ---
{json.dumps(analysis, ensure_ascii=False, indent=2)}

--- これまでのQ&A ---
{json.dumps(qa_history, ensure_ascii=False, indent=2)}
"""

    response = model.generate_content(prompt)
    text = response.text.strip()

    try:
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])
        return json.loads(text)
    except json.JSONDecodeError:
        return [{"id": "q1", "question": text, "purpose": "general"}]


def generate_spec(session) -> str:
    """Generate a specification document from analysis and Q&A."""
    model = _get_gemini_model()

    analysis = session.gemini_analysis or {}
    qa_history = session.qa_history or []

    prompt = f"""\
以下の業務分析結果とQ&A履歴に基づいて、LINEボットプラグインの仕様書をMarkdown形式で生成してください。

仕様書には以下を含めてください:
1. プラグイン概要
2. トリガー条件（キーワード）
3. 処理フロー
4. 外部システム連携
5. テナント設定項目
6. エラーハンドリング
7. 実装パターン（A/B/C/D）

--- 分析結果 ---
{json.dumps(analysis, ensure_ascii=False, indent=2)}

--- Q&A履歴 ---
{json.dumps(qa_history, ensure_ascii=False, indent=2)}

メニュー名: {session.menu_name}
"""

    response = model.generate_content(prompt)
    return response.text.strip()


def generate_plugin_code(session) -> str:
    """Generate Python plugin code from the spec."""
    model = _get_gemini_model()

    prompt = f"""\
以下の仕様書に基づいて、SmartExecプラグインのPythonコードを生成してください。

必ず以下のBasePluginを継承してください:

```python
from app.services.base_plugin import BasePlugin
from sqlalchemy.orm import Session
from typing import Optional

class BasePlugin(ABC):
    def __init__(self, tenant_id: str, config: dict):
        self.tenant_id = tenant_id
        self.config = config

    @property
    @abstractmethod
    def menu_id(self) -> str: ...

    @abstractmethod
    def should_handle(self, user_message: str) -> bool: ...

    @abstractmethod
    def handle(self, user_message: str, line_user_id: str, db: Session) -> Optional[str]: ...
```

AI呼び出しには以下を使ってください:
```python
from app.services.ai_client import chat_with_ai
reply = chat_with_ai(system_prompt="...", user_message=text, tenant_config=config)
```

--- 仕様書 ---
{session.spec_markdown}

メニューID: {session.menu_name}

コードのみ返してください（説明文は不要）。
"""

    response = model.generate_content(prompt)
    text = response.text.strip()

    # Remove markdown code fences
    if text.startswith("```python"):
        lines = text.split("\n")
        text = "\n".join(lines[1:])
    if text.endswith("```"):
        text = text[:-3].rstrip()

    return text
