"""Input guardrails for lightweight safety and hygiene checks."""

from __future__ import annotations

import re

from app.core.exceptions import BizError
from agent.input.preprocessor import UnifiedMessage

_EMAIL_RE = re.compile(r"([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
_PHONE_RE = re.compile(r"\b1[3-9]\d{9}\b")


class Guardrails:
    """Small, synchronous validation rules for incoming requests."""

    def validate(self, message: UnifiedMessage) -> UnifiedMessage:
        if not message.content and not message.attachments:
            raise BizError(message="消息内容不能为空")

        if len(message.content) > 4000:
            raise BizError(message="输入内容过长，请精简后重试")

        message.metadata["pii_detected"] = self.contains_pii(message.content)
        return message

    def contains_pii(self, text: str) -> bool:
        return bool(_EMAIL_RE.search(text) or _PHONE_RE.search(text))

    def redact(self, text: str) -> str:
        redacted = _EMAIL_RE.sub("[email-redacted]", text)
        redacted = _PHONE_RE.sub("[phone-redacted]", redacted)
        return redacted

