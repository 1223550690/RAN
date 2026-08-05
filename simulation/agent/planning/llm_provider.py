"""LLM 自动模式计划提供者。

- 全程由 LLM 指挥下一步行动:每次请求返回语义目标(目的地引用 + 意图类型 + 参数),
  坐标合法性由导航层兜底,LLM 不接触坐标。
- 零第三方依赖:优先使用注入的 llm_call 函数;缺省时用标准库 urllib 调用
  OpenAI 兼容的 /chat/completions 接口。
- 可复现:record_path 记录每次计划(含计划哈希);replay_path 存在时按记录重放,
  不调用 LLM。重放条目与预期不符时抛出错误,保证测量一致。
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

from ..contracts import AgentPlan


class LlmAgentPlanProvider:
    def __init__(
        self,
        *,
        llm_call=None,
        endpoint: str | None = None,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        system_prompt: str | None = None,
        record_path: str | Path | None = None,
        replay_path: str | Path | None = None,
        max_retries: int = 1,
    ) -> None:
        if llm_call is None and not endpoint:
            raise ValueError("LlmAgentPlanProvider requires llm_call or endpoint")
        self.llm_call = llm_call
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model
        self.system_prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
        self.max_retries = max_retries
        self._record_file = Path(record_path) if record_path else None
        self._replay_entries: list[dict] = []
        self._replay_index = 0
        if replay_path:
            replay_file = Path(replay_path)
            if not replay_file.exists():
                raise FileNotFoundError(f"replay file not found: {replay_path}")
            self._replay_entries = [
                json.loads(line)
                for line in replay_file.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

    # ------------------------------------------------------------------ 接口

    def request_plan(self, agent_id: str, context: dict) -> AgentPlan | None:
        if self._replay_entries:
            return self._replay_next(agent_id)
        for attempt in range(self.max_retries + 1):
            payload = self._build_payload(agent_id, context)
            raw = self._invoke(payload)
            if raw is None:
                continue
            plan = self._parse(raw, agent_id)
            if plan is not None:
                self._record(agent_id, payload, raw, plan)
                return plan
        return None

    # ------------------------------------------------------------------ 重放

    def _replay_next(self, agent_id: str) -> AgentPlan | None:
        if self._replay_index >= len(self._replay_entries):
            return None
        entry = self._replay_entries[self._replay_index]
        self._replay_index += 1
        if entry.get("agent_id") != agent_id:
            raise ValueError(
                f"replay order mismatch: expected agent {agent_id!r}, got {entry.get('agent_id')!r}"
            )
        plan = AgentPlan(
            agent_id=agent_id,
            destination_ref=entry["destination_ref"],
            intent_type=entry["intent_type"],
            intent_parameters=dict(entry.get("intent_parameters", {})),
        )
        expected_hash = entry.get("plan_hash")
        if expected_hash and _plan_hash(plan) != expected_hash:
            raise ValueError(f"replay plan hash mismatch for agent {agent_id!r}: {entry}")
        return plan

    # ------------------------------------------------------------------ LLM 调用

    def _build_payload(self, agent_id: str, context: dict) -> dict:
        catalog = context.get("destination_catalog", [])
        catalog_text = "\n".join(f"- {item}" for item in catalog[:200])
        history = context.get("completed_intents", [])
        history_text = "\n".join(f"- {item}" for item in history[-20:]) or "(none)"
        user_message = (
            f"Agent: {agent_id}\n"
            f"Role: {context.get('role', 'unknown')}\n"
            f"Current tick: {context.get('tick', 0)}\n"
            f"Current location: {context.get('current_location', 'unknown')}\n"
            f"Available destinations:\n{catalog_text}\n"
            f"Completed intents:\n{history_text}\n"
            "Respond with JSON only."
        )
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.7,
            "response_format": {"type": "json_object"},
        }

    def _invoke(self, payload: dict) -> str | None:
        if self.llm_call is not None:
            return self.llm_call(payload)
        return self._http_invoke(payload)

    def _http_invoke(self, payload: dict) -> str | None:
        url = self.endpoint.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = json.loads(response.read().decode("utf-8"))
        except Exception:
            return None
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return None

    def _parse(self, raw: str, agent_id: str) -> AgentPlan | None:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        destination_ref = str(data.get("destination_ref") or "").strip()
        intent_type = str(data.get("intent_type") or "").strip()
        if not destination_ref or not intent_type:
            return None
        return AgentPlan(
            agent_id=agent_id,
            destination_ref=destination_ref,
            intent_type=intent_type,
            intent_parameters=dict(data.get("intent_parameters", {}) or {}),
        )

    # ------------------------------------------------------------------ 记录

    def _record(self, agent_id: str, payload: dict, raw: str, plan: AgentPlan) -> None:
        if self._record_file is None:
            return
        self._record_file.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "agent_id": agent_id,
            "tick": payload["messages"][1]["content"].split("Current tick: ")[1].split("\n")[0]
            if "Current tick: " in payload["messages"][1]["content"]
            else 0,
            "destination_ref": plan.destination_ref,
            "intent_type": plan.intent_type,
            "intent_parameters": plan.intent_parameters,
            "plan_hash": _plan_hash(plan),
            "raw_response": raw,
        }
        with self._record_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


_DEFAULT_SYSTEM_PROMPT = (
    "You are the planning brain of a human behavior simulation. "
    "Decide the next destination and network intent for an agent. "
    "The destination_ref MUST be one of the names listed under 'Available destinations', "
    "copied exactly as written — never invent, abbreviate, translate, or rephrase it. "
    "Prefer destinations inside the current building when listed, "
    "and do NOT pick the destination you are currently in — choose a different area. "
    "Reply with JSON only: "
    '{"destination_ref": "<exact destination name from the catalog>", '
    '"intent_type": "video_call|video_upload|file_transfer|message", '
    '"intent_parameters": {}} '
    "For video_upload/file_transfer set size_profile to small|medium|large. "
    "For video_call set duration_seconds and bitrate_kbps. "
    "Never invent coordinates."
)


def _plan_hash(plan: AgentPlan) -> str:
    canonical = json.dumps(
        [plan.agent_id, plan.destination_ref, plan.intent_type, plan.intent_parameters],
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
