from __future__ import annotations

from pathlib import Path
from typing import Literal

import pytest

import counter_risk.pipeline.run as run_module
from counter_risk.config import WorkflowConfig
from counter_risk.pipeline.run import PptProcessingResult, PptProcessingStatus


def _write_placeholder(path: Path, *, payload: bytes = b"fixture") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _build_config(
    *,
    tmp_path: Path,
    enable_screenshot_replacement: bool,
    screenshot_replacement_implementation: Literal["zip", "python-pptx"] = "zip",
    screenshot_inputs: dict[str, Path] | None = None,
) -> WorkflowConfig:
    inputs_dir = tmp_path / "inputs"
    files = {
        "all_programs": inputs_dir / "all_programs.xlsx",
        "ex_trend": inputs_dir / "ex_trend.xlsx",
        "trend": inputs_dir / "trend.xlsx",
        "hist_all": inputs_dir / "hist_all.xlsx",
        "hist_ex": inputs_dir / "hist_ex.xlsx",
        "hist_llc": inputs_dir / "hist_llc.xlsx",
        "monthly_pptx": inputs_dir / "monthly.pptx",
    }
    for path in files.values():
        _write_placeholder(path)

    return WorkflowConfig(
        mosers_all_programs_xlsx=files["all_programs"],
        mosers_ex_trend_xlsx=files["ex_trend"],
        mosers_trend_xlsx=files["trend"],
        hist_all_programs_3yr_xlsx=files["hist_all"],
        hist_ex_llc_3yr_xlsx=files["hist_ex"],
        hist_llc_3yr_xlsx=files["hist_llc"],
        monthly_pptx=files["monthly_pptx"],
        output_root=tmp_path / "ignored-output-root",
        enable_screenshot_replacement=enable_screenshot_replacement,
        screenshot_replacement_implementation=screenshot_replacement_implementation,
        screenshot_inputs=screenshot_inputs or {},
    )


def test_write_outputs_calls_zip_backend_once_when_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    image_1 = tmp_path / "screenshots" / "slide_1.png"
    image_2 = tmp_path / "screenshots" / "slide_2.png"
    _write_placeholder(image_1, payload=b"img-1")
    _write_placeholder(image_2, payload=b"img-2")

    config = _build_config(
        tmp_path=tmp_path,
        enable_screenshot_replacement=True,
        screenshot_replacement_implementation="zip",
        screenshot_inputs={"slide2": image_2, "slide1": image_1},
    )

    calls: list[dict[str, object]] = []

    def _fake_zip_backend(source: Path, output: Path, mapping: dict[str, Path]) -> None:
        calls.append({"source": source, "output": output, "mapping": mapping})
        output.write_bytes(source.read_bytes() + b"-replaced")

    monkeypatch.setattr(run_module, "_replace_screenshots_with_zip_backend", _fake_zip_backend)
    monkeypatch.setattr(
        run_module,
        "_refresh_ppt_links",
        lambda _path: PptProcessingResult(status=PptProcessingStatus.SUCCESS),
    )

    warnings: list[str] = []
    output_paths, _ = run_module._write_outputs(run_dir=run_dir, config=config, warnings=warnings)

    assert len(calls) == 1
    assert calls[0]["output"] == run_dir / "monthly.pptx"
    assert list(calls[0]["mapping"]) == ["slide1", "slide2"]
    assert len(calls[0]["mapping"]) == 2
    assert all(path.suffix.lower() == ".png" for path in calls[0]["mapping"].values())
    assert output_paths[-1] == run_dir / "monthly.pptx"
    assert (run_dir / "monthly.pptx").exists()
    assert all("not implemented" not in warning for warning in warnings)
    assert all("disabled; copied source deck unchanged" not in warning for warning in warnings)


def test_write_outputs_routes_python_pptx_backend_when_selected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    image_1 = tmp_path / "screenshots" / "all_programs.png"
    _write_placeholder(image_1, payload=b"img-1")

    config = _build_config(
        tmp_path=tmp_path,
        enable_screenshot_replacement=True,
        screenshot_replacement_implementation="python-pptx",
        screenshot_inputs={"All Programs": image_1},
    )

    called = {"python_pptx": 0, "zip": 0}

    def _fake_python_pptx_backend(source: Path, output: Path, mapping: dict[str, Path]) -> None:
        _ = mapping
        called["python_pptx"] += 1
        output.write_bytes(source.read_bytes() + b"-replaced")

    def _fake_zip_backend(_source: Path, _output: Path, _mapping: dict[str, Path]) -> None:
        called["zip"] += 1

    monkeypatch.setattr(
        run_module,
        "_replace_screenshots_with_python_pptx_backend",
        _fake_python_pptx_backend,
    )
    monkeypatch.setattr(run_module, "_replace_screenshots_with_zip_backend", _fake_zip_backend)
    monkeypatch.setattr(
        run_module,
        "_refresh_ppt_links",
        lambda _path: PptProcessingResult(status=PptProcessingStatus.SUCCESS),
    )

    warnings: list[str] = []
    run_module._write_outputs(run_dir=run_dir, config=config, warnings=warnings)

    assert called["python_pptx"] == 1
    assert called["zip"] == 0
    assert all("not implemented" not in warning for warning in warnings)


def test_resolve_screenshot_input_mapping_rejects_non_png_paths(tmp_path: Path) -> None:
    text_path = tmp_path / "screenshots" / "slide_1.jpg"
    _write_placeholder(text_path, payload=b"not-png")
    config = _build_config(
        tmp_path=tmp_path,
        enable_screenshot_replacement=True,
        screenshot_replacement_implementation="zip",
        screenshot_inputs={"slide1": text_path},
    )

    with pytest.raises(ValueError, match="must point to a PNG file"):
        run_module._resolve_screenshot_input_mapping(config)


def test_resolve_screenshot_input_mapping_sorts_by_normalized_keys(tmp_path: Path) -> None:
    image_1 = tmp_path / "screenshots" / "slide_1.png"
    image_2 = tmp_path / "screenshots" / "slide_2.png"
    _write_placeholder(image_1, payload=b"img-1")
    _write_placeholder(image_2, payload=b"img-2")
    config = _build_config(
        tmp_path=tmp_path,
        enable_screenshot_replacement=False,
        screenshot_inputs={"  slide2  ": image_2, "slide1": image_1},
    )

    mapping = run_module._resolve_screenshot_input_mapping(config)

    assert list(mapping.keys()) == ["slide1", "slide2"]


def test_resolve_screenshot_input_mapping_rejects_duplicate_normalized_keys(tmp_path: Path) -> None:
    image_1 = tmp_path / "screenshots" / "slide_1.png"
    image_2 = tmp_path / "screenshots" / "slide_2.png"
    _write_placeholder(image_1, payload=b"img-1")
    _write_placeholder(image_2, payload=b"img-2")
    config = _build_config(
        tmp_path=tmp_path,
        enable_screenshot_replacement=True,
        screenshot_inputs={"slide1": image_1, " slide1 ": image_2},
    )

    with pytest.raises(ValueError, match="duplicated after normalization"):
        run_module._resolve_screenshot_input_mapping(config)
