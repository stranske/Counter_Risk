"""Unit tests for limits configuration parsing and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from counter_risk.limits_config import LimitEntry, LimitsConfig, load_limits_config


@pytest.mark.parametrize("limit_kind", ["absolute_notional", "percent_of_total"])
@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_limit_entry_rejects_non_finite_values(
    limit_kind: str, enabled: bool, value: float
) -> None:
    with pytest.raises(ValueError, match=r"limit_value\s+Input should be a finite number"):
        LimitEntry.model_validate(
            {
                "entity_type": "counterparty",
                "entity_name": "Alpha",
                "limit_value": value,
                "limit_kind": limit_kind,
                "enabled": enabled,
            }
        )


@pytest.mark.parametrize("limit_kind", ["absolute_notional", "percent_of_total"])
@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.parametrize("value", [".inf", "-.inf", ".nan"])
def test_load_limits_config_rejects_non_finite_yaml(
    tmp_path: Path, limit_kind: str, enabled: bool, value: str
) -> None:
    config_path = tmp_path / "limits.yml"
    config_path.write_text(
        "schema_version: 1\nlimits:\n"
        "  - entity_type: counterparty\n    entity_name: Alpha\n"
        f"    limit_value: {value}\n    limit_kind: {limit_kind}\n"
        f"    enabled: {str(enabled).lower()}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"limit_value.*finite number"):
        load_limits_config(config_path)


def test_load_limits_config_default_file() -> None:
    config = load_limits_config()

    assert isinstance(config, LimitsConfig)
    assert config.schema_version == 1
    assert config.strict_missing_entities is False
    assert len(config.limits) >= 2


def test_load_limits_config_supports_optional_notes(tmp_path: Path) -> None:
    config_path = tmp_path / "limits.yml"
    config_path.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "limits:",
                "  - entity_type: fcm",
                "    entity_name: CME FCM",
                "    limit_value: 50000000",
                "    limit_kind: absolute_notional",
                "    severity: fail",
                "  - entity_type: custom_group",
                "    entity_name: Trend Energy",
                "    limit_value: 0.2",
                "    limit_kind: percent_of_total",
                "    enabled: false",
                "    notes: '   Max concentration for trend energy sleeve.   '",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    config = load_limits_config(config_path)

    assert config.limits[0].notes is None
    assert config.limits[1].notes == "Max concentration for trend energy sleeve."
    assert config.limits[0].entity_name == "cme_fcm"
    assert config.limits[1].entity_name == "trend_energy"
    assert config.limits[0].severity == "fail"
    assert config.limits[1].enabled is False


def test_load_limits_config_rejects_missing_required_fields(tmp_path: Path) -> None:
    config_path = tmp_path / "limits.yml"
    config_path.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "limits:",
                "  - entity_type: counterparty",
                "    entity_name: citibank",
                "    limit_kind: absolute_notional",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Limits config validation failed"):
        load_limits_config(config_path)


def test_load_limits_config_rejects_invalid_types_and_values(tmp_path: Path) -> None:
    config_path = tmp_path / "limits.yml"
    config_path.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "strict_missing_entities: not-a-bool",
                "limits:",
                "  - entity_type: counterparty",
                "    entity_name: citibank",
                "    limit_value: -10",
                "    limit_kind: unknown_kind",
                "    severity: urgent",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Limits config validation failed"):
        load_limits_config(config_path)


def test_load_limits_config_rejects_duplicate_limit_keys(tmp_path: Path) -> None:
    config_path = tmp_path / "limits.yml"
    config_path.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "limits:",
                "  - entity_type: counterparty",
                "    entity_name: Citibank",
                "    limit_value: 100",
                "    limit_kind: absolute_notional",
                "  - entity_type: counterparty",
                "    entity_name: citibank",
                "    limit_value: 200",
                "    limit_kind: absolute_notional",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate limit keys"):
        load_limits_config(config_path)


def test_load_limits_config_rejects_duplicate_yaml_keys(tmp_path: Path) -> None:
    config_path = tmp_path / "limits.yml"
    config_path.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "limits:",
                "  - entity_type: counterparty",
                "    entity_name: Citibank",
                "    limit_value: 100",
                "    limit_kind: absolute_notional",
                "    severity: warning",
                "    severity: fail",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid YAML"):
        load_limits_config(config_path)
