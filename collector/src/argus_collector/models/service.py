"""Pure parts of the model adapter: config, request bodies, reply parsing."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

DEFAULT_ENDPOINT = "http://127.0.0.1:11434/v1"
DEFAULT_MODEL = "qwen2.5:14b-instruct"
HEALTH_TIMEOUT_S = 2.0
DEFAULT_TIMEOUT_S = 180.0
DEFAULT_MAX_TOKENS = 1024
DEFAULT_TEMPERATURE = 0.0
FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


@dataclass(frozen=True)
class ModelConfig:
    endpoint: str = DEFAULT_ENDPOINT
    name: str = DEFAULT_MODEL
    timeout_s: float = DEFAULT_TIMEOUT_S
    max_tokens: int = DEFAULT_MAX_TOKENS
    temperature: float = DEFAULT_TEMPERATURE


@dataclass(frozen=True)
class ModelReply:
    content: str
    prompt_tokens: int
    completion_tokens: int
    elapsed_ms: int
    model: str = ""


@dataclass(frozen=True)
class Health:
    reachable: bool
    model_listed: bool
    detail: str


def _same_model(listed: str, name: str) -> bool:
    """`qwen2.5:14b-instruct` is also served as `qwen2.5:14b-instruct:latest`."""
    return listed == name or listed == name + ":latest" or name == listed + ":latest"


def health_from_models(listed: list[str], name: str) -> Health:
    if any(_same_model(item, name) for item in listed):
        return Health(reachable=True, model_listed=True, detail=f"model {name} listed")
    shown = ", ".join(listed[:5]) if listed else "none"
    return Health(reachable=True, model_listed=False, detail=f"model {name} not listed ({shown})")


def request_body(config: ModelConfig, system: str, user: str, json_mode: bool) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": config.name,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "stream": False,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    return body


def parse_models(data: object) -> list[str]:
    """`GET /models` document -> model ids (OpenAI shape; raises ValueError)."""
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise ValueError("models document has no 'data' list")
    return [str(item.get("id", "")) for item in data["data"] if isinstance(item, dict)]


def parse_reply(data: object, elapsed_ms: int) -> ModelReply:
    if not isinstance(data, dict):
        raise ValueError("completion is not a JSON object")
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError("completion has no choices")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise ValueError("completion has no message")
    usage: dict[str, Any] = data["usage"] if isinstance(data.get("usage"), dict) else {}
    return ModelReply(
        content=str(message.get("content") or ""),
        prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
        completion_tokens=int(usage.get("completion_tokens", 0) or 0),
        elapsed_ms=elapsed_ms,
        model=str(data.get("model") or ""),
    )


def parse_json_reply(content: str) -> dict[str, Any] | None:
    text = content.strip()
    fenced = FENCE_RE.search(text)
    if fenced:
        text = fenced.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None
