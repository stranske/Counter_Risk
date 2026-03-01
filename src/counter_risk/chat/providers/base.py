"""Provider client abstraction for chat generation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final, Protocol, cast

from counter_risk.chat.providers.langchain_runtime import (
    PROVIDER_ANTHROPIC,
    PROVIDER_GITHUB,
    PROVIDER_OPENAI,
    build_chat_client,
    build_langsmith_metadata,
    get_provider_model_catalog,
    missing_provider_dependencies,
)

_GITHUB_ENV_KEYS: Final[tuple[str, ...]] = ("GITHUB_TOKEN",)
_OPENAI_API_ENV_KEYS: Final[tuple[str, ...]] = ("OPENAI_API_KEY",)
_OPENAI_ENV_KEYS: Final[tuple[str, ...]] = _GITHUB_ENV_KEYS + _OPENAI_API_ENV_KEYS
_ANTHROPIC_ENV_KEYS: Final[tuple[str, ...]] = ("CLAUDE_API_STRANSKE",)


class ProviderClient(Protocol):
    """Interface for pluggable chat providers."""

    def generate(self, messages: list[dict[str, str]], model: str, **kwargs: object) -> str:
        """Return provider text for a prepared messages list and selected model."""


class _LangChainInvokeClient(Protocol):
    def invoke(self, messages: list[dict[str, str]], config: object | None = None) -> object: ...


@dataclass(frozen=True)
class ProviderModelRegistry:
    """Available model ids keyed by chat provider."""

    provider_models: dict[str, set[str]]
    provider_model_required_env_keys: dict[str, dict[str, tuple[str, ...]]]


def build_provider_model_registry(
    *, local_model: str, include_local: bool = True
) -> ProviderModelRegistry:
    """Build provider model allowlists from shared slot configuration."""

    slot_catalog = get_provider_model_catalog()
    github_models = set(slot_catalog.get(PROVIDER_GITHUB, set()))
    openai_api_models = set(slot_catalog.get(PROVIDER_OPENAI, set()))
    openai_models = set(github_models).union(openai_api_models)
    anthropic_models = set(slot_catalog.get(PROVIDER_ANTHROPIC, set()))

    if not openai_models:
        openai_models.add("gpt-5.2")
    if not anthropic_models:
        anthropic_models.add("claude-sonnet-4-5-20250929")

    openai_model_requirements: dict[str, tuple[str, ...]] = {}
    for model in sorted(github_models):
        openai_model_requirements[model] = _GITHUB_ENV_KEYS
    for model in sorted(openai_api_models):
        if model in openai_model_requirements:
            openai_model_requirements[model] = _OPENAI_ENV_KEYS
        else:
            openai_model_requirements[model] = _OPENAI_API_ENV_KEYS
    for model in sorted(openai_models):
        openai_model_requirements.setdefault(model, _OPENAI_ENV_KEYS)

    anthropic_model_requirements = dict.fromkeys(sorted(anthropic_models), _ANTHROPIC_ENV_KEYS)

    provider_models: dict[str, set[str]] = {
        "openai": openai_models,
        "anthropic": anthropic_models,
    }
    provider_model_required_env_keys: dict[str, dict[str, tuple[str, ...]]] = {
        "openai": openai_model_requirements,
        "anthropic": anthropic_model_requirements,
    }
    if include_local:
        provider_models["local"] = {local_model}
        provider_model_required_env_keys["local"] = {local_model: ()}

    return ProviderModelRegistry(
        provider_models=provider_models,
        provider_model_required_env_keys=provider_model_required_env_keys,
    )


class LangChainProviderClient:
    """LangChain-backed provider client with ordered provider fallbacks."""

    def __init__(
        self, *, provider_chain: tuple[str, ...], required_env_keys: tuple[str, ...]
    ) -> None:
        self._provider_chain = provider_chain
        self._required_env_keys = required_env_keys

    def generate(self, messages: list[dict[str, str]], model: str, **kwargs: object) -> str:
        last_error: Exception | None = None
        metadata = build_langsmith_metadata(operation="counter-risk-chat")
        response_metadata = kwargs.get("response_metadata")
        metadata_sink = response_metadata if isinstance(response_metadata, dict) else None
        slot_catalog = get_provider_model_catalog()
        missing_dependency_names: set[str] = set()
        runtime_ready_provider_seen = False

        for provider_name in self._provider_chain:
            provider_models = slot_catalog.get(provider_name, set())
            if provider_models and model not in provider_models:
                continue
            client_info = build_chat_client(provider=provider_name, model=model)
            if client_info is None:
                missing_dependencies = missing_provider_dependencies(provider_name)
                if missing_dependencies:
                    missing_dependency_names.update(missing_dependencies)
                else:
                    runtime_ready_provider_seen = True
                continue
            runtime_ready_provider_seen = True
            try:
                client = cast(_LangChainInvokeClient, client_info.client)
                response = client.invoke(messages, config=metadata)
            except Exception as exc:
                last_error = exc
                continue
            response_text = _coerce_response_text(response)
            if response_text:
                if metadata_sink is not None:
                    metadata_sink["provider"] = client_info.provider
                    metadata_sink["model"] = client_info.model
                    trace_id, trace_url = _extract_trace_metadata(response)
                    if trace_id:
                        metadata_sink["trace_id"] = trace_id
                    if trace_url:
                        metadata_sink["trace_url"] = trace_url
                return response_text
            last_error = RuntimeError(
                f"Provider {provider_name!r} returned an empty response for model {model!r}."
            )

        if last_error is not None:
            raise RuntimeError(f"Provider request failed: {last_error}") from last_error

        if self._required_env_keys and not any(
            os.environ.get(key) for key in self._required_env_keys
        ):
            missing_env = ", ".join(self._required_env_keys)
            raise RuntimeError(
                "No provider credentials/configured clients available. "
                f"Set one of: {missing_env}."
            )

        if not runtime_ready_provider_seen and missing_dependency_names:
            missing_rendered = ", ".join(sorted(missing_dependency_names))
            raise RuntimeError(
                "LangChain provider dependencies are missing for the selected provider/model. "
                f"Install required packages: {missing_rendered}."
            )

        chain = ", ".join(self._provider_chain)
        raise RuntimeError(f"No configured clients available for provider chain: {chain}.")


def build_provider_clients() -> dict[str, ProviderClient]:
    """Construct provider clients used by chat sessions."""

    return {
        "openai": LangChainProviderClient(
            provider_chain=(PROVIDER_GITHUB, PROVIDER_OPENAI),
            required_env_keys=_OPENAI_ENV_KEYS,
        ),
        "anthropic": LangChainProviderClient(
            provider_chain=(PROVIDER_ANTHROPIC,),
            required_env_keys=_ANTHROPIC_ENV_KEYS,
        ),
    }


def provider_env_available(provider: str) -> bool:
    """Return whether any known credentials are available for *provider*."""

    provider_key = provider.strip().lower()
    if provider_key == "openai":
        return any(os.environ.get(key) for key in _OPENAI_ENV_KEYS)
    if provider_key == "anthropic":
        return any(os.environ.get(key) for key in _ANTHROPIC_ENV_KEYS)
    return True


def provider_dependency_error(provider: str) -> str | None:
    """Return install guidance when LangChain provider dependencies are unavailable."""

    provider_key = provider.strip().lower()
    missing = missing_provider_dependencies(provider_key)
    if not missing:
        return None
    rendered = ", ".join(missing)
    return (
        f"Provider '{provider_key}' requires missing dependencies ({rendered}). "
        f"Install packages: {rendered}."
    )


def _coerce_response_text(response: object) -> str:
    if isinstance(response, str):
        return response.strip()
    content = getattr(response, "content", None)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, str):
                chunks.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    chunks.append(text)
        return "".join(chunks).strip()
    return str(response).strip()


def _extract_trace_metadata(response: object) -> tuple[str | None, str | None]:
    trace_id: str | None = None
    trace_url: str | None = None

    for mapping in (
        getattr(response, "response_metadata", None),
        getattr(response, "additional_kwargs", None),
    ):
        if not isinstance(mapping, dict):
            continue
        trace_id = trace_id or _coerce_metadata_value(mapping, ("trace_id", "run_id", "id"))
        trace_url = trace_url or _coerce_metadata_value(mapping, ("trace_url", "run_url"))

    response_id = getattr(response, "id", None)
    if trace_id is None and isinstance(response_id, str):
        normalized_response_id = response_id.strip()
        if normalized_response_id:
            trace_id = normalized_response_id

    return trace_id, trace_url


def _coerce_metadata_value(
    payload: dict[object, object], candidate_keys: tuple[str, ...]
) -> str | None:
    for key in candidate_keys:
        value = payload.get(key)
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
    return None
