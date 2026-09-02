"""Tests for runtime-safe LangChain provider helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from counter_risk.chat.providers import langchain_runtime as runtime


@pytest.fixture(autouse=True)
def _isolate_runtime_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep provider credentials and routing overrides isolated from every test."""

    names = {
        runtime.ENV_PROVIDER,
        runtime.ENV_MODEL,
        runtime.ENV_TIMEOUT,
        runtime.ENV_MAX_RETRIES,
        runtime.ENV_SLOT_CONFIG,
        runtime.ENV_ANTHROPIC_KEY,
        runtime.ENV_LANGSMITH_KEY,
        runtime.ENV_LANGCHAIN_TRACING_V2,
        runtime.ENV_LANGCHAIN_API_KEY,
        runtime.ENV_LANGCHAIN_PROJECT,
        runtime.ENV_LANGSMITH_PROJECT,
        "COUNTER_RISK_LANGSMITH_PROJECT",
        "GITHUB_REPOSITORY",
        "GITHUB_RUN_ID",
        "GITHUB_TOKEN",
        "ISSUE_NUMBER",
        "OPENAI_API_KEY",
        "PR_NUMBER",
        "RUN_ID",
    }
    for index in range(1, 4):
        names.add(f"{runtime.ENV_SLOT_PREFIX}{index}_PROVIDER")
        names.add(f"{runtime.ENV_SLOT_PREFIX}{index}_MODEL")
    for name in names:
        monkeypatch.delenv(name, raising=False)
    # These values are read before pytest fixtures run, so deleting their
    # source variables cannot by itself neutralize a developer's shell.
    monkeypatch.setattr(runtime, "DEFAULT_TIMEOUT", 60)
    monkeypatch.setattr(runtime, "DEFAULT_MAX_RETRIES", 2)


@pytest.mark.parametrize(
    ("provider", "available_modules", "expected"),
    [
        (runtime.PROVIDER_OPENAI, frozenset(), (runtime.LANGCHAIN_OPENAI_DIST,)),
        (runtime.PROVIDER_GITHUB, frozenset(), (runtime.LANGCHAIN_OPENAI_DIST,)),
        (runtime.PROVIDER_ANTHROPIC, frozenset(), (runtime.LANGCHAIN_ANTHROPIC_DIST,)),
        (runtime.PROVIDER_OPENAI, frozenset({"langchain_openai"}), ()),
        ("unknown", frozenset(), ()),
    ],
)
def test_missing_provider_dependencies_reports_exact_distributions(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    available_modules: frozenset[str],
    expected: tuple[str, ...],
) -> None:
    """Readiness diagnostics must name only the selected provider's missing package."""

    monkeypatch.setattr(
        runtime,
        "_module_available",
        lambda module_name: module_name in available_modules,
    )

    assert runtime.missing_provider_dependencies(provider) == expected


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


def test_load_slot_config_falls_back_when_slots_is_not_a_list(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A malformed slot container must not make the whole chat package unimportable."""

    slot_path = tmp_path / "slots.json"
    slot_path.write_text(json.dumps({"slots": None}), encoding="utf-8")
    monkeypatch.setenv(runtime.ENV_SLOT_CONFIG, str(slot_path))

    assert runtime._load_slot_config() == runtime._default_slots()


def test_load_slot_config_keeps_only_complete_supported_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed entries cannot displace a valid aliased provider/model definition."""

    slot_path = tmp_path / "slots.json"
    slot_path.write_text(
        json.dumps(
            {
                "slots": [
                    None,
                    {"name": "  ", "provider": "claude", "model": " claude-custom "},
                    {"provider": "unsupported", "model": "wrong"},
                    {"provider": "openai", "model": "  "},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(runtime.ENV_SLOT_CONFIG, str(slot_path))

    assert runtime._load_slot_config() == [
        runtime.SlotDefinition(
            name="slot2",
            provider=runtime.PROVIDER_ANTHROPIC,
            model="claude-custom",
        )
    ]


def test_slot_overrides_ignore_blank_models_and_normalize_real_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Blank env values cannot erase a valid model and disable its credentialed slot."""

    slots = [
        runtime.SlotDefinition("slot1", runtime.PROVIDER_OPENAI, "gpt-configured"),
        runtime.SlotDefinition("slot2", runtime.PROVIDER_ANTHROPIC, "claude-configured"),
    ]
    monkeypatch.setenv(f"{runtime.ENV_SLOT_PREFIX}1_MODEL", "  \t")
    monkeypatch.setenv(runtime.ENV_MODEL, "   ")
    monkeypatch.setenv(f"{runtime.ENV_SLOT_PREFIX}2_PROVIDER", "github_models")
    monkeypatch.setenv(f"{runtime.ENV_SLOT_PREFIX}2_MODEL", "  codex-mini-latest  ")

    assert runtime._apply_slot_env_overrides(slots) == [
        runtime.SlotDefinition("slot1", runtime.PROVIDER_OPENAI, "gpt-configured"),
        runtime.SlotDefinition("slot2", runtime.PROVIDER_GITHUB, "codex-mini-latest"),
    ]


@pytest.mark.parametrize(
    ("env_model", "expected_model"),
    [("   ", "gpt-configured"), ("  gpt-override  ", "gpt-override")],
)
def test_build_chat_client_normalizes_env_model_before_slot_selection(
    monkeypatch: pytest.MonkeyPatch,
    env_model: str,
    expected_model: str,
) -> None:
    """Blank model env must preserve slot config; real overrides must be normalized and honored."""

    monkeypatch.setenv("OPENAI_API_KEY", "openai-token")
    monkeypatch.setenv(runtime.ENV_MODEL, env_model)
    monkeypatch.setattr(
        runtime,
        "_resolve_slots",
        lambda: [runtime.SlotDefinition("slot1", runtime.PROVIDER_OPENAI, "gpt-configured")],
    )
    selected_models: list[str] = []

    def fake_build_client_for_provider(**kwargs: object) -> runtime.ClientInfo:
        selected_model = cast(str, kwargs["model"])
        selected_models.append(selected_model)
        return runtime.ClientInfo(
            client=object(),
            provider=runtime.PROVIDER_OPENAI,
            model=selected_model,
        )

    monkeypatch.setattr(runtime, "_build_client_for_provider", fake_build_client_for_provider)

    client = runtime.build_chat_client()

    assert client is not None
    assert client.model == expected_model
    assert selected_models == [expected_model]


def test_env_int_uses_valid_values_and_falls_back_for_malformed_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A malformed runtime limit must not crash module configuration parsing."""

    monkeypatch.setenv("COUNTER_RISK_TEST_INTEGER", "not-an-integer")
    assert runtime._env_int("COUNTER_RISK_TEST_INTEGER", 7) == 7

    monkeypatch.setenv("COUNTER_RISK_TEST_INTEGER", "12")
    assert runtime._env_int("COUNTER_RISK_TEST_INTEGER", 7) == 12


def test_openai_client_preserves_endpoint_credentials_and_reasoning_model_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GitHub endpoints and reasoning models need exact, non-crossed client kwargs."""

    calls: list[dict[str, object]] = []

    def fake_chat_openai(**kwargs: object) -> object:
        calls.append(kwargs)
        return SimpleNamespace(kwargs=kwargs)

    monkeypatch.setattr(
        runtime.importlib,
        "import_module",
        lambda name: SimpleNamespace(ChatOpenAI=fake_chat_openai),
    )

    regular = runtime._build_openai_client(
        model="gpt-5.4",
        token="github-token",
        timeout=17,
        max_retries=3,
        base_url=runtime.GITHUB_MODELS_BASE_URL,
    )
    reasoning = runtime._build_openai_client(
        model="o3-mini",
        token="openai-token",
        timeout=23,
        max_retries=4,
    )

    assert regular is not None
    assert reasoning is not None
    assert calls == [
        {
            "model": "gpt-5.4",
            "api_key": "github-token",
            "timeout": 17,
            "max_retries": 3,
            "base_url": runtime.GITHUB_MODELS_BASE_URL,
            "temperature": 0.1,
        },
        {
            "model": "o3-mini",
            "api_key": "openai-token",
            "timeout": 23,
            "max_retries": 4,
        },
    ]


@pytest.mark.parametrize("failure_mode", ["import", "missing-class", "constructor"])
def test_openai_client_failures_return_none_for_provider_fallback(
    monkeypatch: pytest.MonkeyPatch,
    failure_mode: str,
) -> None:
    """An unavailable optional client must yield control to the configured fallback slot."""

    if failure_mode == "import":

        def import_module(_: str) -> object:
            raise ImportError("dependency missing")

        monkeypatch.setattr(runtime.importlib, "import_module", import_module)
    elif failure_mode == "missing-class":
        monkeypatch.setattr(runtime.importlib, "import_module", lambda _: SimpleNamespace())
    else:

        def fail_constructor(**_: object) -> object:
            raise RuntimeError("client rejected configuration")

        monkeypatch.setattr(
            runtime.importlib,
            "import_module",
            lambda _: SimpleNamespace(ChatOpenAI=fail_constructor),
        )

    assert (
        runtime._build_openai_client(
            model="gpt-5.4",
            token="token",
            timeout=10,
            max_retries=1,
        )
        is None
    )


def test_anthropic_client_uses_its_credential_field_and_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anthropic credentials must stay in the Anthropic field and permit fallback on failure."""

    calls: list[dict[str, object]] = []

    def fake_chat_anthropic(**kwargs: object) -> object:
        calls.append(kwargs)
        return object()

    module = SimpleNamespace(ChatAnthropic=fake_chat_anthropic)
    monkeypatch.setattr(runtime.importlib, "import_module", lambda _: module)

    client = runtime._build_anthropic_client(
        model="claude-sonnet",
        token="anthropic-token",
        timeout=31,
        max_retries=2,
    )

    assert client is not None
    assert calls == [
        {
            "model": "claude-sonnet",
            "anthropic_api_key": "anthropic-token",
            "temperature": 0.1,
            "timeout": 31,
            "max_retries": 2,
        }
    ]

    def fail_constructor(**_: object) -> object:
        raise RuntimeError("client rejected configuration")

    module.ChatAnthropic = fail_constructor
    assert (
        runtime._build_anthropic_client(
            model="claude-sonnet",
            token="anthropic-token",
            timeout=31,
            max_retries=2,
        )
        is None
    )


@pytest.mark.parametrize(
    ("provider", "github_token", "expected_call"),
    [
        (
            runtime.PROVIDER_GITHUB,
            "github-token",
            ("openai", "github-token", runtime.GITHUB_MODELS_BASE_URL),
        ),
        (runtime.PROVIDER_OPENAI, "github-token", ("openai", "openai-token", None)),
        (runtime.PROVIDER_ANTHROPIC, "github-token", ("anthropic", "anthropic-token", None)),
        (runtime.PROVIDER_GITHUB, None, None),
    ],
)
def test_provider_router_never_crosses_credential_scopes(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    github_token: str | None,
    expected_call: tuple[str, str, str | None] | None,
) -> None:
    """A provider may consume only its own token, even when every other token exists."""

    calls: list[tuple[str, str, str | None]] = []

    def fake_openai(*, token: str, base_url: str | None = None, **_: object) -> object:
        calls.append(("openai", token, base_url))
        return object()

    def fake_anthropic(*, token: str, **_: object) -> object:
        calls.append(("anthropic", token, None))
        return object()

    monkeypatch.setattr(runtime, "_build_openai_client", fake_openai)
    monkeypatch.setattr(runtime, "_build_anthropic_client", fake_anthropic)

    client_info = runtime._build_client_for_provider(
        provider=provider,
        model="selected-model",
        timeout=60,
        max_retries=2,
        github_token=github_token,
        openai_token="openai-token",
        anthropic_token="anthropic-token",
    )

    assert calls == ([] if expected_call is None else [expected_call])
    if expected_call is None:
        assert client_info is None
    else:
        assert client_info is not None
        assert client_info.provider == provider
        assert client_info.model == "selected-model"


def test_build_chat_client_without_credentials_does_not_resolve_slots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Credential absence must stop before provider discovery or optional imports."""

    monkeypatch.setattr(
        runtime,
        "_resolve_slots",
        lambda: pytest.fail("slots must not resolve without credentials"),
    )

    assert runtime.build_chat_client() is None


def test_build_chat_client_rejects_unknown_explicit_provider_without_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit provider typo must not silently send a request to another provider."""

    monkeypatch.setenv("OPENAI_API_KEY", "openai-token")
    monkeypatch.setattr(
        runtime,
        "_build_client_for_provider",
        lambda **_: pytest.fail("unknown explicit provider must not build a client"),
    )

    assert runtime.build_chat_client(provider="not-a-provider") is None


def test_force_openai_passes_only_explicit_runtime_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Forced OpenAI routing must preserve the selected model, timeout, and retry policy."""

    monkeypatch.setenv("OPENAI_API_KEY", "openai-token")
    captured: dict[str, object] = {}

    def fake_build_client_for_provider(**kwargs: object) -> runtime.ClientInfo:
        captured.update(kwargs)
        return runtime.ClientInfo(client=object(), provider=runtime.PROVIDER_OPENAI, model="model")

    monkeypatch.setattr(runtime, "_build_client_for_provider", fake_build_client_for_provider)

    result = runtime.build_chat_client(
        model="gpt-explicit",
        force_openai=True,
        timeout=19,
        max_retries=5,
    )

    assert result is not None
    assert captured == {
        "provider": runtime.PROVIDER_OPENAI,
        "model": "gpt-explicit",
        "timeout": 19,
        "max_retries": 5,
        "github_token": None,
        "openai_token": "openai-token",
        "anthropic_token": None,
    }


def test_build_chat_client_uses_repo_defaults_when_runtime_limits_are_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Omitted limits must use stable repo defaults, independent of the test runner's shell."""

    monkeypatch.setenv("OPENAI_API_KEY", "openai-token")
    captured: dict[str, object] = {}

    def fake_build_client_for_provider(**kwargs: object) -> runtime.ClientInfo:
        captured.update(kwargs)
        return runtime.ClientInfo(client=object(), provider=runtime.PROVIDER_OPENAI, model="model")

    monkeypatch.setattr(runtime, "_build_client_for_provider", fake_build_client_for_provider)

    result = runtime.build_chat_client(model="gpt-defaults", force_openai=True)

    assert result is not None
    assert captured["timeout"] == 60
    assert captured["max_retries"] == 2


@pytest.mark.parametrize(
    ("issue_or_pr_number", "pr_number", "issue_number", "expected_number"),
    [
        (None, 42, 41, "42"),
        (None, None, 41, "41"),
        ("manual", 42, None, "manual"),
    ],
)
def test_langsmith_metadata_uses_unambiguous_issue_pr_attribution(
    issue_or_pr_number: str | None,
    pr_number: int | None,
    issue_number: int | None,
    expected_number: str,
) -> None:
    """Trace metadata must attribute a run to the explicit PR/issue with stable precedence."""

    payload = runtime.build_langsmith_metadata(
        operation="counter-risk-chat",
        issue_or_pr_number=issue_or_pr_number,
        pr_number=pr_number,
        issue_number=issue_number,
    )
    metadata = cast(dict[str, Any], payload["metadata"])
    tags = cast(list[str], payload["tags"])

    assert metadata["issue_or_pr_number"] == expected_number
    assert f"issue_or_pr:{expected_number}" in tags
    assert "langsmith_project" not in metadata


def test_langsmith_tracing_preserves_caller_owned_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Enabling tracing must not overwrite an operator's project, mode, or API-key aliases."""

    monkeypatch.setenv(runtime.ENV_LANGSMITH_KEY, "langsmith-key")
    monkeypatch.setenv(runtime.ENV_LANGCHAIN_TRACING_V2, "false")
    monkeypatch.setenv(runtime.ENV_LANGCHAIN_PROJECT, "operator-langchain-project")
    monkeypatch.setenv(runtime.ENV_LANGSMITH_PROJECT, "operator-langsmith-project")
    monkeypatch.setenv(runtime.ENV_LANGCHAIN_API_KEY, "operator-api-key")

    assert runtime._ensure_langsmith_tracing_env() is True
    assert os.environ[runtime.ENV_LANGCHAIN_TRACING_V2] == "false"
    assert os.environ[runtime.ENV_LANGCHAIN_PROJECT] == "operator-langchain-project"
    assert os.environ[runtime.ENV_LANGSMITH_PROJECT] == "operator-langsmith-project"
    assert os.environ[runtime.ENV_LANGCHAIN_API_KEY] == "operator-api-key"


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


def test_build_langsmith_metadata_uses_repo_project_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(runtime.ENV_LANGSMITH_KEY, "test-key")
    monkeypatch.setenv("COUNTER_RISK_LANGSMITH_PROJECT", "counter-risk-prod")
    monkeypatch.delenv(runtime.ENV_LANGCHAIN_PROJECT, raising=False)
    monkeypatch.delenv(runtime.ENV_LANGSMITH_PROJECT, raising=False)

    payload = runtime.build_langsmith_metadata(operation="counter-risk-chat")
    metadata = cast(dict[str, Any], payload["metadata"])

    assert metadata["langsmith_project"] == "counter-risk-prod"
    assert os.environ[runtime.ENV_LANGCHAIN_PROJECT] == "counter-risk-prod"
    assert os.environ[runtime.ENV_LANGSMITH_PROJECT] == "counter-risk-prod"
