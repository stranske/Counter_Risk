"""Tests for LangChain-backed chat provider clients."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from counter_risk.chat.providers import base as provider_base


def test_build_provider_model_registry_uses_real_model_ids() -> None:
    registry = provider_base.build_provider_model_registry(local_model="chat-model-placeholder")

    assert "chat-model-placeholder" in registry.provider_models["local"]
    assert "chat-model-placeholder" not in registry.provider_models["openai"]
    assert "chat-model-placeholder" not in registry.provider_models["anthropic"]
    assert registry.provider_models["openai"]
    assert registry.provider_models["anthropic"]


def test_build_provider_model_registry_can_exclude_local_stub_model() -> None:
    registry = provider_base.build_provider_model_registry(
        local_model="chat-model-placeholder",
        include_local=False,
    )

    assert "local" not in registry.provider_models
    assert "local" not in registry.provider_model_required_env_keys


def test_build_provider_model_registry_tracks_credential_requirements_per_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        provider_base,
        "get_provider_model_catalog",
        lambda: {
            "github-models": {"github-only", "shared-model"},
            "openai": {"openai-only", "shared-model"},
            "anthropic": {"claude-model"},
        },
    )

    registry = provider_base.build_provider_model_registry(local_model="chat-model-placeholder")

    openai_requirements = registry.provider_model_required_env_keys["openai"]
    assert openai_requirements["github-only"] == ("GITHUB_TOKEN",)
    assert openai_requirements["openai-only"] == ("OPENAI_API_KEY",)
    assert openai_requirements["shared-model"] == ("GITHUB_TOKEN", "OPENAI_API_KEY")
    assert registry.provider_model_required_env_keys["anthropic"]["claude-model"] == (
        "CLAUDE_API_STRANSKE",
    )


def test_langchain_provider_client_uses_fallback_provider_when_first_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        provider_base,
        "get_provider_model_catalog",
        lambda: {
            "github-models": {"gpt-5.2"},
            "openai": {"gpt-5.2"},
            "anthropic": set(),
        },
    )
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-key")
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    monkeypatch.delenv("LANGCHAIN_PROJECT", raising=False)
    calls: list[tuple[str | None, str | None]] = []

    def _fake_build_chat_client(
        *, provider: str | None = None, model: str | None = None, **_: object
    ) -> SimpleNamespace | None:
        calls.append((provider, model))
        if provider == "github-models":
            return None

        class _Client:
            def invoke(self, messages: object, config: object | None = None) -> object:
                _ = (messages, config)
                return SimpleNamespace(content="provider-response")

        return SimpleNamespace(client=_Client(), provider=provider, model=model)

    monkeypatch.setattr(provider_base, "build_chat_client", _fake_build_chat_client)

    client = provider_base.LangChainProviderClient(
        provider_chain=("github-models", "openai"),
        required_env_keys=("GITHUB_TOKEN", "OPENAI_API_KEY"),
    )
    response_metadata: dict[str, object] = {}
    response = client.generate(
        messages=[{"role": "user", "content": "hello"}],
        model="gpt-5.2",
        response_metadata=response_metadata,
    )

    assert response == "provider-response"
    assert calls == [("github-models", "gpt-5.2"), ("openai", "gpt-5.2")]
    assert response_metadata["provider"] == "openai"
    assert response_metadata["model"] == "gpt-5.2"


def test_langchain_provider_client_populates_trace_metadata_from_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        provider_base,
        "get_provider_model_catalog",
        lambda: {
            "github-models": {"gpt-5.2"},
            "openai": {"gpt-5.2"},
            "anthropic": set(),
        },
    )

    def _fake_build_chat_client(
        *, provider: str | None = None, model: str | None = None, **_: object
    ) -> SimpleNamespace:
        class _Client:
            def invoke(self, messages: object, config: object | None = None) -> object:
                _ = (messages, config)
                return SimpleNamespace(
                    content="trace-response",
                    id="trace-123",
                    response_metadata={"trace_url": "https://smith.langchain.com/r/trace-123"},
                )

        return SimpleNamespace(client=_Client(), provider=provider, model=model)

    monkeypatch.setattr(provider_base, "build_chat_client", _fake_build_chat_client)

    client = provider_base.LangChainProviderClient(
        provider_chain=("openai",),
        required_env_keys=("OPENAI_API_KEY",),
    )
    response_metadata: dict[str, object] = {}
    response = client.generate(
        messages=[{"role": "user", "content": "hello"}],
        model="gpt-5.2",
        response_metadata=response_metadata,
    )

    assert response == "trace-response"
    assert response_metadata["provider"] == "openai"
    assert response_metadata["model"] == "gpt-5.2"
    assert response_metadata["trace_id"] == "trace-123"
    assert response_metadata["trace_url"] == "https://smith.langchain.com/r/trace-123"


def test_langchain_provider_client_retries_next_provider_after_invoke_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        provider_base,
        "get_provider_model_catalog",
        lambda: {
            "github-models": {"gpt-5.2"},
            "openai": {"gpt-5.2"},
            "anthropic": set(),
        },
    )

    def _fake_build_chat_client(
        *, provider: str | None = None, model: str | None = None, **_: object
    ) -> SimpleNamespace:
        class _FailingClient:
            def invoke(self, messages: object, config: object | None = None) -> object:
                _ = (messages, config)
                raise RuntimeError("first provider failure")

        class _WorkingClient:
            def invoke(self, messages: object, config: object | None = None) -> object:
                _ = (messages, config)
                return SimpleNamespace(content="fallback-success")

        if provider == "github-models":
            return SimpleNamespace(client=_FailingClient(), provider=provider, model=model)
        return SimpleNamespace(client=_WorkingClient(), provider=provider, model=model)

    monkeypatch.setattr(provider_base, "build_chat_client", _fake_build_chat_client)

    client = provider_base.LangChainProviderClient(
        provider_chain=("github-models", "openai"),
        required_env_keys=("GITHUB_TOKEN", "OPENAI_API_KEY"),
    )
    response = client.generate(messages=[{"role": "user", "content": "hello"}], model="gpt-5.2")

    assert response == "fallback-success"


def test_langchain_provider_client_reports_missing_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        provider_base,
        "get_provider_model_catalog",
        lambda: {
            "github-models": {"gpt-5.2"},
            "openai": {"gpt-5.2"},
            "anthropic": set(),
        },
    )
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(provider_base, "build_chat_client", lambda **_: None)

    client = provider_base.LangChainProviderClient(
        provider_chain=("github-models", "openai"),
        required_env_keys=("GITHUB_TOKEN", "OPENAI_API_KEY"),
    )

    with pytest.raises(RuntimeError, match="Set one of: GITHUB_TOKEN, OPENAI_API_KEY"):
        client.generate(messages=[{"role": "user", "content": "hello"}], model="gpt-5.2")


def test_langchain_provider_client_skips_incompatible_model_for_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        provider_base,
        "get_provider_model_catalog",
        lambda: {
            "github-models": {"github-only"},
            "openai": {"openai-only"},
            "anthropic": set(),
        },
    )
    calls: list[tuple[str | None, str | None]] = []

    def _fake_build_chat_client(
        *, provider: str | None = None, model: str | None = None, **_: object
    ) -> SimpleNamespace | None:
        calls.append((provider, model))
        return None

    monkeypatch.setattr(provider_base, "build_chat_client", _fake_build_chat_client)

    client = provider_base.LangChainProviderClient(
        provider_chain=("github-models", "openai"),
        required_env_keys=("GITHUB_TOKEN", "OPENAI_API_KEY"),
    )

    with pytest.raises(RuntimeError, match="Set one of: GITHUB_TOKEN, OPENAI_API_KEY"):
        client.generate(messages=[{"role": "user", "content": "hello"}], model="github-only")
    assert calls == [("github-models", "github-only")]


def test_langchain_provider_client_reports_missing_dependencies_for_provider_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        provider_base,
        "get_provider_model_catalog",
        lambda: {
            "github-models": {"gpt-5.2"},
            "openai": {"gpt-5.2"},
            "anthropic": set(),
        },
    )
    monkeypatch.setattr(
        provider_base,
        "missing_provider_dependencies",
        lambda provider: ("langchain-openai",) if provider in {"github-models", "openai"} else (),
    )
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setattr(provider_base, "build_chat_client", lambda **_: None)

    client = provider_base.LangChainProviderClient(
        provider_chain=("github-models", "openai"),
        required_env_keys=("GITHUB_TOKEN", "OPENAI_API_KEY"),
    )

    with pytest.raises(RuntimeError, match="Install required packages: langchain-openai"):
        client.generate(messages=[{"role": "user", "content": "hello"}], model="gpt-5.2")
