"""Unit tests for name registry parsing and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from counter_risk.name_registry import NameRegistryConfig, load_name_registry


def test_load_name_registry_default_config() -> None:
    registry = load_name_registry()

    assert isinstance(registry, NameRegistryConfig)
    assert registry.schema_version == 1
    assert registry.entries
    assert all(entry.canonical_key for entry in registry.entries)
    assert all(entry.display_name for entry in registry.entries)
    assert all(entry.aliases for entry in registry.entries)


def test_load_name_registry_includes_optional_series_flags() -> None:
    registry = load_name_registry(Path("config/name_registry.yml"))

    ice_euro = next(entry for entry in registry.entries if entry.canonical_key == "ice_euro")
    assert ice_euro.series_included is not None
    assert ice_euro.series_included.all_programs is True
    assert ice_euro.series_included.ex_trend is True
    assert ice_euro.series_included.trend is False

    bank_of_america = next(
        entry for entry in registry.entries if entry.canonical_key == "bank_of_america"
    )
    assert bank_of_america.series_included is None


def test_load_name_registry_rejects_invalid_canonical_key(tmp_path: Path) -> None:
    config_path = tmp_path / "name_registry.yml"
    config_path.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "entries:",
                "  - canonical_key: Invalid Key",
                "    display_name: Valid Name",
                "    aliases:",
                "      - Valid Name",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Name registry validation failed"):
        load_name_registry(config_path)


def test_load_name_registry_rejects_duplicate_aliases_in_entry(tmp_path: Path) -> None:
    config_path = tmp_path / "name_registry.yml"
    config_path.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "entries:",
                "  - canonical_key: sample_name",
                "    display_name: Sample Name",
                "    aliases:",
                "      - Sample Name",
                "      - '  sample   name '",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Name registry validation failed"):
        load_name_registry(config_path)


def test_load_name_registry_rejects_duplicate_aliases_across_entries(tmp_path: Path) -> None:
    config_path = tmp_path / "name_registry.yml"
    config_path.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "entries:",
                "  - canonical_key: first_name",
                "    display_name: First Name",
                "    aliases:",
                "      - Shared Alias",
                "  - canonical_key: second_name",
                "    display_name: Second Name",
                "    aliases:",
                "      - shared alias",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Name registry validation failed"):
        load_name_registry(config_path)
