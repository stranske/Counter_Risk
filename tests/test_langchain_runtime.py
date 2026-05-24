"""Tests for runtime-safe LangChain provider helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, cast

import pytest

from counter_risk.chat.providers import langchain_runtime as runtime


def test_build_chat_client_ignores_invalid_env_provider_and_uses_slot_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "token")
    monkeypatch.setenv(runtime.ENV_PROVIDER, "invalid-provider")
    monkeypatch.setattr(
        runtime,
        "_resolve_slots",
        lambda: [
            runtime.SlotDefinition(name="slot1", provider=runtime.PROVIDER_OPENAI, model="gpt-5.2")
        ],
    )

    calls: list[tuple[str, str]] = []

    def _fake_build_client_for_provider(
        *,
        provider: str,
        model: str,
        **_kwargs: object,
    ) -> runtime.ClientInfo:
        calls.append((provider, model))
        return runtime.ClientInfo(client=object(), provider=provider, model=model)

    monkeypatch.setattr(runtime, "_build_client_for_provider", _fake_build_client_for_provider)

    client = runtime.build_chat_client()

    assert client is not None
    assert client.provider == runtime.PROVIDER_OPENAI
    assert calls == [(runtime.PROVIDER_OPENAI, "gpt-5.2")]


def test_load_slot_config_falls_back_when_payload_is_not_object(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slot_path = tmp_path / "slots.json"
    slot_path.write_text('["not-a-dict"]', encoding="utf-8")
    monkeypatch.setenv(runtime.ENV_SLOT_CONFIG, str(slot_path))

    slots = runtime._load_slot_config()

    assert slots == runtime._default_slots()


def test_build_langsmith_metadata_sets_tracing_env_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(runtime.ENV_LANGSMITH_KEY, "test-key")
    monkeypatch.delenv(runtime.ENV_LANGCHAIN_TRACING_V2, raising=False)
    monkeypatch.delenv(runtime.ENV_LANGCHAIN_API_KEY, raising=False)
    monkeypatch.delenv(runtime.ENV_LANGCHAIN_PROJECT, raising=False)
    monkeypatch.delenv(runtime.ENV_LANGSMITH_PROJECT, raising=False)

    payload = runtime.build_langsmith_metadata(operation="counter-risk-chat")
    metadata = cast(dict[str, Any], payload["metadata"])

    assert metadata["langsmith_project"] == "counter-risk"
    assert metadata["operation"] == "counter-risk-chat"
    assert os.environ[runtime.ENV_LANGCHAIN_TRACING_V2] == "true"
    assert os.environ[runtime.ENV_LANGCHAIN_API_KEY] == "test-key"
    assert os.environ[runtime.ENV_LANGCHAIN_PROJECT] == runtime.DEFAULT_LANGCHAIN_PROJECT
    assert os.environ[runtime.ENV_LANGSMITH_PROJECT] == runtime.DEFAULT_LANGCHAIN_PROJECT
