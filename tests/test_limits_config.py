"""Unit tests for limits configuration parsing and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from counter_risk.limits_config import LimitsConfig, load_limits_config


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
                "  - entity_type: custom_group",
                "    entity_name: Trend Energy",
                "    limit_value: 0.2",
                "    limit_kind: percent_of_total",
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
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Limits config validation failed"):
        load_limits_config(config_path)
