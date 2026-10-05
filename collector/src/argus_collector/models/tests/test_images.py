"""A user message with a screenshot goes as OpenAI-style parts (vision model)."""

from __future__ import annotations

from argus_collector.models import service


def test_images_become_data_url_parts() -> None:
    config = service.ModelConfig("http://127.0.0.1:1/v1", "qwen2.5-vl:7b")
    body = service.request_body(config, "sys", "look", True, images=(b"\x89PNGxx", b"\xff\xd8y"))
    parts = body["messages"][1]["content"]
    assert parts[0] == {"type": "text", "text": "look"}
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert parts[2]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    plain = service.request_body(config, "sys", "look", True)
    assert plain["messages"][1]["content"] == "look"
