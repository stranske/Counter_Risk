"""Registry validation after Pydantic's field type checks."""

import pytest
from pydantic import ValidationError

from counter_risk.name_registry import NameRegistryEntry, SeriesIncludedFlags


@pytest.mark.parametrize(
    ("flags", "message"),
    [
        ({" ": {"repo": True}}, "variant keys cannot be blank"),
        ({"trend": {" ": True}}, "segment keys cannot be blank"),
        ({"trend": {"Repo": True, " repo ": False}}, "duplicate segment key"),
    ],
)
def test_series_flags_reject_blank_and_duplicate_normalized_keys(flags, message):
    with pytest.raises(ValidationError, match=message):
        SeriesIncludedFlags(by_segment=flags)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("aliases", ["  "], "aliases cannot contain blank values"),
        ("display_name", "  ", "display_name cannot be blank"),
    ],
)
def test_registry_entry_rejects_whitespace_only_labels(field, value, message):
    payload = {"canonical_key": "bank", "aliases": ["Bank"], "display_name": "Bank"}
    payload[field] = value
    with pytest.raises(ValidationError, match=message):
        NameRegistryEntry.model_validate(payload)
