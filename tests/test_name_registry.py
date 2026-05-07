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
    assert ice_euro.series_included.by_segment == {"trend": {"futures": False}}

    bank_of_america = next(
        entry for entry in registry.entries if entry.canonical_key == "bank_of_america"
    )
    assert bank_of_america.series_included is None


def test_load_name_registry_accepts_series_included_by_segment(tmp_path: Path) -> None:
    config_path = tmp_path / "name_registry.yml"
    config_path.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "entries:",
                "  - canonical_key: ice_euro",
                "    display_name: ICE Euro",
                "    aliases:",
                "      - ICE Clear Europe",
                "    series_included:",
                "      trend: true",
                "      by_segment:",
                "        trend:",
                "          futures: false",
                "          total: true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    registry = load_name_registry(config_path)
    flags = registry.entries[0].series_included
    assert flags is not None
    assert flags.by_segment == {"trend": {"futures": False, "total": True}}


def test_load_name_registry_rejects_series_included_by_segment_invalid_variant(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "name_registry.yml"
    config_path.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "entries:",
                "  - canonical_key: ice_euro",
                "    display_name: ICE Euro",
                "    aliases:",
                "      - ICE Clear Europe",
                "    series_included:",
                "      by_segment:",
                "        invalid_variant:",
                "          futures: false",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Name registry validation failed"):
        load_name_registry(config_path)


@pytest.mark.parametrize(
    "canonical_key",
    [
        "Invalid Key",
        "invalid-key",
        "_leading",
        "trailing_",
        "two__underscores",
        "MixedCase",
        "contains.dot",
    ],
)
def test_load_name_registry_rejects_invalid_canonical_key(
    tmp_path: Path, canonical_key: str
) -> None:
    config_path = tmp_path / "name_registry.yml"
    config_path.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "entries:",
                f"  - canonical_key: {canonical_key}",
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


@pytest.mark.parametrize(
    "canonical_key",
    ["a", "bank_of_america", "cme2", "name_1", "counterparty_v2_key"],
)
def test_load_name_registry_accepts_valid_canonical_key(tmp_path: Path, canonical_key: str) -> None:
    config_path = tmp_path / "name_registry.yml"
    config_path.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "entries:",
                f"  - canonical_key: {canonical_key}",
                "    display_name: Valid Name",
                "    aliases:",
                "      - Valid Name",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    registry = load_name_registry(config_path)

    assert registry.entries[0].canonical_key == canonical_key


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


def test_load_name_registry_rejects_duplicate_canonical_keys(tmp_path: Path) -> None:
    config_path = tmp_path / "name_registry.yml"
    config_path.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "entries:",
                "  - canonical_key: duplicate_name",
                "    display_name: Duplicate Name One",
                "    aliases:",
                "      - Duplicate Name One",
                "  - canonical_key: duplicate_name",
                "    display_name: Duplicate Name Two",
                "    aliases:",
                "      - Duplicate Name Two",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate canonical_key found"):
        load_name_registry(config_path)


def test_load_name_registry_rejects_unsupported_schema_version(tmp_path: Path) -> None:
    config_path = tmp_path / "name_registry.yml"
    config_path.write_text(
        "\n".join(
            [
                "schema_version: 2",
                "entries:",
                "  - canonical_key: sample_name",
                "    display_name: Sample Name",
                "    aliases:",
                "      - Sample Name",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Name registry validation failed"):
        load_name_registry(config_path)


def test_load_name_registry_rejects_missing_top_level_entries(tmp_path: Path) -> None:
    config_path = tmp_path / "name_registry.yml"
    config_path.write_text("schema_version: 1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Name registry validation failed"):
        load_name_registry(config_path)


# ---------------------------------------------------------------------------
# Punctuation-variant deduplication in aliases
# ---------------------------------------------------------------------------


def test_load_name_registry_rejects_apostrophe_variant_duplicate_within_entry(
    tmp_path: Path,
) -> None:
    """ASCII apostrophe and curly apostrophe in the same entry must be rejected."""
    config_path = tmp_path / "name_registry.yml"
    config_path.write_text(
        "schema_version: 1\n"
        "entries:\n"
        "  - canonical_key: goldman_sachs\n"
        "    display_name: Goldman Sachs\n"
        "    aliases:\n"
        "      - Goldman Sachs Int'l\n"
        '      - "Goldman Sachs Int’l"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Name registry validation failed"):
        load_name_registry(config_path)


def test_load_name_registry_rejects_apostrophe_variant_duplicate_across_entries(
    tmp_path: Path,
) -> None:
    """Same alias spelled with ASCII vs curly apostrophe across two entries must be rejected."""
    config_path = tmp_path / "name_registry.yml"
    config_path.write_text(
        "schema_version: 1\n"
        "entries:\n"
        "  - canonical_key: first_entry\n"
        "    display_name: First Entry\n"
        "    aliases:\n"
        "      - Goldman Sachs Int'l\n"
        "  - canonical_key: second_entry\n"
        "    display_name: Second Entry\n"
        "    aliases:\n"
        '      - "Goldman Sachs Int’l"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Name registry validation failed"):
        load_name_registry(config_path)


def test_load_name_registry_rejects_dash_variant_duplicate_within_entry(tmp_path: Path) -> None:
    """ASCII hyphen and en-dash for the same alias in the same entry must be rejected."""
    config_path = tmp_path / "name_registry.yml"
    config_path.write_text(
        "schema_version: 1\n"
        "entries:\n"
        "  - canonical_key: korea_exchange\n"
        "    display_name: Korea Exchange\n"
        "    aliases:\n"
        "      - Korea Exchange-Seoul\n"
        '      - "Korea Exchange–Seoul"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Name registry validation failed"):
        load_name_registry(config_path)


def test_load_name_registry_rejects_dash_variant_duplicate_across_entries(tmp_path: Path) -> None:
    """Same alias spelled with ASCII hyphen vs en-dash across entries must be rejected."""
    config_path = tmp_path / "name_registry.yml"
    config_path.write_text(
        "schema_version: 1\n"
        "entries:\n"
        "  - canonical_key: first_entry\n"
        "    display_name: First Entry\n"
        "    aliases:\n"
        "      - Korea Exchange-Seoul\n"
        "  - canonical_key: second_entry\n"
        "    display_name: Second Entry\n"
        "    aliases:\n"
        '      - "Korea Exchange–Seoul"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Name registry validation failed"):
        load_name_registry(config_path)
