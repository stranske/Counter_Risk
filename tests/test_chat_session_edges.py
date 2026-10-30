"""Deterministic provider selection and empty-result chat formatting."""

import logging

import pytest

from counter_risk.chat import session


def test_default_provider_skips_unavailable_models_and_checks_other_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        session,
        "_visible_provider_models",
        lambda: {
            "openai": {"unavailable"},
            "experimental": {"ready"},
        },
    )
    monkeypatch.setattr(session, "provider_env_available", lambda provider: True)
    monkeypatch.setattr(
        session, "_model_credentials_available", lambda provider, model: model == "ready"
    )
    assert session._default_provider_key() == "experimental"
    assert session._default_model_key() == "ready"


@pytest.mark.parametrize(
    ("models", "expected"),
    [({"openai": {"z-model", "a-model"}}, "a-model"), ({}, "chat-model-placeholder")],
)
def test_default_model_fallback_is_deterministic_when_none_are_available(
    monkeypatch: pytest.MonkeyPatch, models, expected
) -> None:
    monkeypatch.setattr(session, "_visible_provider_models", lambda: models)
    monkeypatch.setattr(session, "provider_env_available", lambda provider: False)
    monkeypatch.setattr(session, "_model_credentials_available", lambda provider, model: False)
    assert session._default_provider_key() == "openai"
    assert session._default_model_key() == expected


def test_local_model_support_requires_offline_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COUNTER_RISK_CHAT_OFFLINE_MODE", "0")
    assert not session.is_provider_model_supported("local", "chat-model-placeholder")


def test_empty_untrusted_text_produces_no_ratio_warnings(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)
    session._warn_on_heavy_encoding_or_escaping("")
    session._warn_on_high_non_alphanumeric_ratio("   ")
    assert caplog.records == []


def test_equal_exposure_rows_keep_source_order() -> None:
    first = {"variant": "all", "name": "CIBC", "value": 2.0, "marker": "first"}
    second = {**first, "marker": "second"}
    assert session._sort_top_exposure_rows([first, second]) == [first, second]


@pytest.mark.parametrize("top_n", [0, -1])
def test_nonpositive_top_count_returns_no_rows(top_n: int) -> None:
    assert (
        session._limit_top_exposure_rows(
            [{"variant": "all", "name": "CIBC", "value": 2.0}], top_n=top_n
        )
        == []
    )
