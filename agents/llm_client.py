from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class DeepSeekAPIError(RuntimeError):
    pass


@dataclass
class DeepSeekClient:
    api_key: str | None
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-flash"
    timeout_seconds: int = 30

    @classmethod
    def from_env(cls, *, model: str | None = None, timeout_seconds: int = 30) -> "DeepSeekClient":
        return cls(
            api_key=os.environ.get("DEEPSEEK_API_KEY"),
            base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            model=model or os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash"),
            timeout_seconds=timeout_seconds,
        )

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def chat_json(self, messages: list[dict[str, str]], *, max_tokens: int = 400) -> dict[str, Any]:
        if not self.api_key:
            raise DeepSeekAPIError("DEEPSEEK_API_KEY is not set")

        body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "thinking": {"type": "disabled"},
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(
            url=f"{self.base_url.rstrip('/')}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise DeepSeekAPIError(f"DeepSeek HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise DeepSeekAPIError(f"DeepSeek request failed: {exc.reason}") from exc

        try:
            choice = payload["choices"][0]
            message = choice["message"]
            content = message.get("content")
        except (KeyError, IndexError, TypeError) as exc:
            raise DeepSeekAPIError(f"Unexpected DeepSeek response: {payload}") from exc

        if not content:
            finish_reason = choice.get("finish_reason")
            reasoning = compact(message.get("reasoning_content"))
            tool_calls = message.get("tool_calls")
            raise DeepSeekAPIError(
                "DeepSeek returned empty content "
                f"(model={self.model}, finish_reason={finish_reason}, "
                f"reasoning_content={reasoning}, tool_calls={tool_calls})"
            )

        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise DeepSeekAPIError(f"DeepSeek returned non-JSON content: {content}") from exc


def compact(value: Any, *, limit: int = 180) -> str | None:
    if value is None:
        return None
    text = str(value).replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "..."
