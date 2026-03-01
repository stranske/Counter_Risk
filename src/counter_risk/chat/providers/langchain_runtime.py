"""Runtime-safe LangChain helpers for chat providers.

This module lives under ``src`` so packaged/runtime execution does not depend on
the repository-root ``tools`` package being importable.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from counter_risk.runtime_paths import resolve_runtime_path

ENV_PROVIDER = "LANGCHAIN_PROVIDER"
ENV_MODEL = "LANGCHAIN_MODEL"
ENV_TIMEOUT = "LANGCHAIN_TIMEOUT"
ENV_MAX_RETRIES = "LANGCHAIN_MAX_RETRIES"
ENV_SLOT_CONFIG = "LANGCHAIN_SLOT_CONFIG"
ENV_SLOT_PREFIX = "LANGCHAIN_SLOT"
ENV_ANTHROPIC_KEY = "CLAUDE_API_STRANSKE"

PROVIDER_OPENAI = "openai"
PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_GITHUB = "github-models"

GITHUB_MODELS_BASE_URL = "https://models.inference.ai.azure.com"
DEFAULT_MODEL = "codex-mini-latest"

DEFAULT_SLOT_CONFIG_PATH = "config/llm_slots.json"

LANGCHAIN_OPENAI_DIST = "langchain-openai"
LANGCHAIN_ANTHROPIC_DIST = "langchain-anthropic"


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def missing_provider_dependencies(provider: str) -> tuple[str, ...]:
    """Return missing package distributions required by *provider*."""

    normalized = (provider or "").strip().lower()
    missing: list[str] = []
    if normalized in {PROVIDER_OPENAI, PROVIDER_GITHUB} and not _module_available(
        "langchain_openai"
    ):
        missing.append(LANGCHAIN_OPENAI_DIST)
    if normalized == PROVIDER_ANTHROPIC and not _module_available("langchain_anthropic"):
        missing.append(LANGCHAIN_ANTHROPIC_DIST)
    return tuple(missing)


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


DEFAULT_TIMEOUT = _env_int(ENV_TIMEOUT, 60)
DEFAULT_MAX_RETRIES = _env_int(ENV_MAX_RETRIES, 2)


@dataclass(frozen=True)
class ClientInfo:
    client: object
    provider: str
    model: str


@dataclass(frozen=True)
class SlotDefinition:
    name: str
    provider: str
    model: str


def _normalize_provider(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    if normalized in {"github", "github_models", "github-models"}:
        return PROVIDER_GITHUB
    if normalized in {"anthropic", "claude"}:
        return PROVIDER_ANTHROPIC
    if normalized in {"openai"}:
        return PROVIDER_OPENAI
    return None


def _resolve_provider(provider: str | None, *, force_openai: bool) -> tuple[str | None, bool]:
    if force_openai:
        return PROVIDER_OPENAI, True
    if provider is not None:
        return _normalize_provider(provider), True
    env_provider = os.environ.get(ENV_PROVIDER)
    return _normalize_provider(env_provider), bool(env_provider)


def _default_slots() -> list[SlotDefinition]:
    return [
        SlotDefinition(name="slot1", provider=PROVIDER_OPENAI, model="gpt-5.2"),
        SlotDefinition(
            name="slot2", provider=PROVIDER_ANTHROPIC, model="claude-sonnet-4-5-20250929"
        ),
        SlotDefinition(name="slot3", provider=PROVIDER_GITHUB, model=DEFAULT_MODEL),
    ]


def _load_slot_config() -> list[SlotDefinition]:
    config_path = os.environ.get(ENV_SLOT_CONFIG)
    path = Path(config_path) if config_path else resolve_runtime_path(DEFAULT_SLOT_CONFIG_PATH)
    if not path.is_file():
        return _default_slots()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_slots()

    slots: list[SlotDefinition] = []
    for idx, entry in enumerate(payload.get("slots", []), start=1):
        if not isinstance(entry, dict):
            continue
        provider = _normalize_provider(str(entry.get("provider", "")))
        model = str(entry.get("model", "")).strip()
        if not provider or not model:
            continue
        name = str(entry.get("name") or f"slot{idx}").strip() or f"slot{idx}"
        slots.append(SlotDefinition(name=name, provider=provider, model=model))
    return slots or _default_slots()


def _apply_slot_env_overrides(slots: list[SlotDefinition]) -> list[SlotDefinition]:
    updated: list[SlotDefinition] = []
    for idx, slot in enumerate(slots, start=1):
        provider_key = f"{ENV_SLOT_PREFIX}{idx}_PROVIDER"
        model_key = f"{ENV_SLOT_PREFIX}{idx}_MODEL"
        provider_override = _normalize_provider(os.environ.get(provider_key))
        model_override = os.environ.get(model_key)
        if idx == 1:
            model_override = model_override or os.environ.get(ENV_MODEL)
        updated.append(
            SlotDefinition(
                name=slot.name,
                provider=provider_override or slot.provider,
                model=(model_override or slot.model).strip(),
            )
        )
    return updated


def _resolve_slots() -> list[SlotDefinition]:
    return _apply_slot_env_overrides(_load_slot_config())


def get_provider_model_catalog() -> dict[str, set[str]]:
    """Return provider->model mappings from configured slots."""

    catalog: dict[str, set[str]] = {
        PROVIDER_OPENAI: set(),
        PROVIDER_ANTHROPIC: set(),
        PROVIDER_GITHUB: set(),
    }
    for slot in _resolve_slots():
        catalog.setdefault(slot.provider, set()).add(slot.model)
    if not any(catalog.values()):
        for slot in _default_slots():
            catalog.setdefault(slot.provider, set()).add(slot.model)
    return catalog


_REASONING_MODEL_PATTERN: Final[re.Pattern[str]] = re.compile(r"o[0-9]+(?:-[a-z0-9]+)*")


def _is_reasoning_model(model: str) -> bool:
    return bool(_REASONING_MODEL_PATTERN.fullmatch(model.lower().strip()))


def _build_openai_client(
    *,
    model: str,
    token: str,
    timeout: int,
    max_retries: int,
    base_url: str | None = None,
) -> object | None:
    try:
        module = importlib.import_module("langchain_openai")
    except ImportError:
        return None
    chat_openai = getattr(module, "ChatOpenAI", None)
    if chat_openai is None:
        return None

    kwargs: dict[str, object] = {
        "model": model,
        "api_key": token,
        "timeout": timeout,
        "max_retries": max_retries,
    }
    if base_url is not None:
        kwargs["base_url"] = base_url
    if not _is_reasoning_model(model):
        kwargs["temperature"] = 0.1
    try:
        return cast(object, chat_openai(**kwargs))
    except Exception:
        return None


def _build_anthropic_client(
    *, model: str, token: str, timeout: int, max_retries: int
) -> object | None:
    try:
        module = importlib.import_module("langchain_anthropic")
    except ImportError:
        return None
    chat_anthropic = getattr(module, "ChatAnthropic", None)
    if chat_anthropic is None:
        return None
    try:
        return cast(
            object,
            chat_anthropic(
                model=model,
                anthropic_api_key=token,
                temperature=0.1,
                timeout=timeout,
                max_retries=max_retries,
            ),
        )
    except Exception:
        return None


def _build_client_for_provider(
    *,
    provider: str,
    model: str,
    timeout: int,
    max_retries: int,
    github_token: str | None,
    openai_token: str | None,
    anthropic_token: str | None,
) -> ClientInfo | None:
    if provider == PROVIDER_GITHUB and github_token:
        client = _build_openai_client(
            model=model,
            token=github_token,
            timeout=timeout,
            max_retries=max_retries,
            base_url=GITHUB_MODELS_BASE_URL,
        )
        if client is not None:
            return ClientInfo(client=client, provider=PROVIDER_GITHUB, model=model)

    if provider == PROVIDER_OPENAI and openai_token:
        client = _build_openai_client(
            model=model,
            token=openai_token,
            timeout=timeout,
            max_retries=max_retries,
        )
        if client is not None:
            return ClientInfo(client=client, provider=PROVIDER_OPENAI, model=model)

    if provider == PROVIDER_ANTHROPIC and anthropic_token:
        client = _build_anthropic_client(
            model=model,
            token=anthropic_token,
            timeout=timeout,
            max_retries=max_retries,
        )
        if client is not None:
            return ClientInfo(client=client, provider=PROVIDER_ANTHROPIC, model=model)

    return None


def build_chat_client(
    *,
    model: str | None = None,
    provider: str | None = None,
    force_openai: bool = False,
    timeout: int | None = None,
    max_retries: int | None = None,
) -> ClientInfo | None:
    github_token = os.environ.get("GITHUB_TOKEN")
    openai_token = os.environ.get("OPENAI_API_KEY")
    anthropic_token = os.environ.get(ENV_ANTHROPIC_KEY)
    if not github_token and not openai_token and not anthropic_token:
        return None

    selected_model = model or os.environ.get(ENV_MODEL) or DEFAULT_MODEL
    selected_timeout = DEFAULT_TIMEOUT if timeout is None else timeout
    selected_retries = DEFAULT_MAX_RETRIES if max_retries is None else max_retries

    selected_provider, provider_explicit = _resolve_provider(provider, force_openai=force_openai)
    if provider_explicit:
        if selected_provider is None:
            return None
        return _build_client_for_provider(
            provider=selected_provider,
            model=selected_model,
            timeout=selected_timeout,
            max_retries=selected_retries,
            github_token=github_token,
            openai_token=openai_token,
            anthropic_token=anthropic_token,
        )

    model_override = model or os.environ.get(ENV_MODEL)
    used_override = False
    for slot in _resolve_slots():
        slot_model = model_override if model_override and not used_override else slot.model
        client = _build_client_for_provider(
            provider=slot.provider,
            model=slot_model,
            timeout=selected_timeout,
            max_retries=selected_retries,
            github_token=github_token,
            openai_token=openai_token,
            anthropic_token=anthropic_token,
        )
        if client is not None:
            used_override = True
            return client

    return None


def build_langsmith_metadata(
    *,
    operation: str,
    repo: str | None = None,
    run_id: str | None = None,
    issue_or_pr_number: str | None = None,
    pr_number: int | None = None,
    issue_number: int | None = None,
) -> dict[str, object]:
    """Build a LangChain-compatible metadata+tags payload for tracing."""

    repo_value = repo or os.environ.get("GITHUB_REPOSITORY", "unknown")
    run_id_value = (
        run_id or os.environ.get("GITHUB_RUN_ID") or os.environ.get("RUN_ID") or "unknown"
    )

    if issue_or_pr_number is None:
        if pr_number is not None:
            issue_or_pr_number = str(pr_number)
        elif issue_number is not None:
            issue_or_pr_number = str(issue_number)
        else:
            env_pr = os.environ.get("PR_NUMBER", "")
            env_issue = os.environ.get("ISSUE_NUMBER", "")
            issue_or_pr_number = (
                env_pr if env_pr.isdigit() else env_issue if env_issue.isdigit() else "unknown"
            )

    metadata: dict[str, object] = {
        "repo": repo_value,
        "run_id": run_id_value,
        "issue_or_pr_number": issue_or_pr_number,
        "operation": operation,
        "pr_number": str(pr_number) if pr_number is not None else None,
        "issue_number": str(issue_number) if issue_number is not None else None,
    }
    if os.environ.get("LANGSMITH_API_KEY"):
        metadata["langsmith_project"] = os.environ.get("LANGCHAIN_PROJECT", "workflows-agents")

    tags = [
        "workflows-agents",
        f"operation:{operation}",
        f"repo:{repo_value}",
        f"issue_or_pr:{issue_or_pr_number}",
        f"run_id:{run_id_value}",
    ]
    return {"metadata": metadata, "tags": tags}
