"""Directional ("metamorphic") checks: variant vs control on a flat metric.

Each catalog `directionals` entry asserts an economically-expected movement,
e.g. concentrating mass raises HHI; dispersing it lowers HHI / top-share.
"""

from __future__ import annotations

import pytest
from baseline_kit import evaluate_direction, load_catalog

from . import adapter
from .conftest import CATALOG_PATH

_CATALOG = load_catalog(CATALOG_PATH)
_BASE_ROWS = _CATALOG["base"]["exposures"]
_SCENARIOS = {s["id"]: s for s in _CATALOG["scenarios"]}
_DIRECTIONALS = _CATALOG["directionals"]


def _metric(scenario_id: str, key: str) -> float:
    return adapter.run_scenario(_SCENARIOS[scenario_id], _BASE_ROWS)[key]


@pytest.mark.parametrize("scen", _DIRECTIONALS, ids=[s["id"] for s in _DIRECTIONALS])
def test_directional(scen, record_property):
    metric = scen["metric"]
    variant = _metric(scen["scenario"], metric)
    control = _metric(scen["control"], metric)
    holds = evaluate_direction(scen["direction"], variant, control)
    msg = (
        f"{scen['id']}: {metric} variant={variant:.6g} "
        f"{scen['direction']} control={control:.6g} -> {holds}"
    )
    record_property("directional", msg)
    if scen.get("enforce"):
        assert holds, "Economically wrong direction -- " + msg
    elif not holds:
        pytest.skip("[report-only] " + msg)
