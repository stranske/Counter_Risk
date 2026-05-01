from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path

from counter_risk.config import WorkflowConfig
from counter_risk.outputs import OutputContext, PptScreenshotOutputGenerator
from counter_risk.outputs.ppt_screenshot import export_ppt_slides_as_png_via_com
from counter_risk.pipeline.ppt_naming import resolve_ppt_output_names


def _minimal_config(tmp_path: Path, *, enable_screenshot_replacement: bool) -> WorkflowConfig:
    for filename in (
        "all.xlsx",
        "ex.xlsx",
        "trend.xlsx",
        "hist_all.xlsx",
        "hist_ex.xlsx",
        "hist_llc.xlsx",
        "monthly.pptx",
    ):
        (tmp_path / filename).write_bytes(b"placeholder")

    screenshot = tmp_path / "slide_1.png"
    screenshot.write_bytes(b"png")

    return WorkflowConfig(
        mosers_all_programs_xlsx=tmp_path / "all.xlsx",
        mosers_ex_trend_xlsx=tmp_path / "ex.xlsx",
        mosers_trend_xlsx=tmp_path / "trend.xlsx",
        hist_all_programs_3yr_xlsx=tmp_path / "hist_all.xlsx",
        hist_ex_llc_3yr_xlsx=tmp_path / "hist_ex.xlsx",
        hist_llc_3yr_xlsx=tmp_path / "hist_llc.xlsx",
        monthly_pptx=tmp_path / "monthly.pptx",
        enable_screenshot_replacement=enable_screenshot_replacement,
        screenshot_inputs={"slide1": screenshot},
    )


def _output_context(tmp_path: Path, *, enable_screenshot_replacement: bool) -> OutputContext:
    return OutputContext(
        config=_minimal_config(
            tmp_path, enable_screenshot_replacement=enable_screenshot_replacement
        ),
        run_dir=tmp_path / "run",
        as_of_date=date(2026, 1, 31),
        run_date=date(2026, 2, 1),
    )


def test_ppt_screenshot_generator_routes_to_replacer_when_enabled(tmp_path: Path) -> None:
    context = _output_context(tmp_path, enable_screenshot_replacement=True)
    warnings: list[str] = []
    calls: list[tuple[Path, Path, dict[str, Path]]] = []

    def _mapping_resolver(_config: WorkflowConfig) -> dict[str, Path]:
        return {"slide1": context.config.screenshot_inputs["slide1"]}

    def _replacer(source: Path, output: Path, mapping: dict[str, Path]) -> None:
        calls.append((source, output, mapping))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(source.read_bytes() + b"-replaced")

    def _replacer_resolver(_implementation: str) -> Callable[[Path, Path, dict[str, Path]], None]:
        return _replacer

    def _validator(*, source_pptx_path: Path, master_pptx_path: Path) -> None:
        assert source_pptx_path == context.config.monthly_pptx
        assert master_pptx_path.read_bytes().endswith(b"-replaced")

    generator = PptScreenshotOutputGenerator(
        warnings=warnings,
        screenshot_input_mapping_resolver=_mapping_resolver,
        screenshot_replacer_resolver=_replacer_resolver,
        master_link_target_validator=_validator,
    )

    generated = generator.generate(context=context)
    expected_output = context.run_dir / resolve_ppt_output_names(context.as_of_date).master_filename

    assert generated == (expected_output,)
    assert calls == [
        (
            context.config.monthly_pptx,
            expected_output,
            {"slide1": context.config.screenshot_inputs["slide1"]},
        )
    ]
    assert warnings == []


def test_ppt_screenshot_generator_copies_source_when_replacement_disabled(tmp_path: Path) -> None:
    context = _output_context(tmp_path, enable_screenshot_replacement=False)
    warnings: list[str] = []

    def _mapping_resolver(_config: WorkflowConfig) -> dict[str, Path]:
        return {"slide1": context.config.screenshot_inputs["slide1"]}

    def _replacer_resolver(_implementation: str) -> Callable[[Path, Path, dict[str, Path]], None]:
        raise AssertionError(
            "Replacer should not be resolved when screenshot replacement is disabled"
        )

    def _validator(*, source_pptx_path: Path, master_pptx_path: Path) -> None:
        assert master_pptx_path.read_bytes() == source_pptx_path.read_bytes()

    generator = PptScreenshotOutputGenerator(
        warnings=warnings,
        screenshot_input_mapping_resolver=_mapping_resolver,
        screenshot_replacer_resolver=_replacer_resolver,
        master_link_target_validator=_validator,
    )

    generated = generator.generate(context=context)
    expected_output = context.run_dir / resolve_ppt_output_names(context.as_of_date).master_filename

    assert generated == (expected_output,)
    assert warnings == [
        "PPT screenshots replacement disabled; copied source deck to Master unchanged"
    ]


def test_export_ppt_slides_as_png_via_com_exports_all_slides(tmp_path: Path, monkeypatch) -> None:
    source_pptx = tmp_path / "source.pptx"
    source_pptx.write_bytes(b"pptx")
    slide_images_dir = tmp_path / "slides"
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\xf0\x1f\x00\x05\x00\x01\xff\x89\x99=\x1d"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    class _FakeSlide:
        def __init__(self, index: int) -> None:
            self.index = index

        def Export(self, path: str, fmt: str) -> None:  # noqa: N802
            assert fmt == "PNG"
            Path(path).write_bytes(png_bytes + bytes(str(self.index), encoding="ascii"))

    class _FakeSlides:
        def __init__(self) -> None:
            self.Count = 2

        def __getitem__(self, idx: int) -> _FakeSlide:
            return _FakeSlide(idx)

    class _FakePresentation:
        def __init__(self) -> None:
            self.Slides = _FakeSlides()

        def Close(self) -> None:  # noqa: N802
            return None

    class _FakePowerPointApplication:
        def __init__(self) -> None:
            self.Visible = 1
            self.Presentations = type(
                "_Presentations",
                (),
                {"Open": staticmethod(lambda *_args, **_kwargs: _FakePresentation())},
            )

        def Quit(self) -> None:  # noqa: N802
            return None

    monkeypatch.setattr(
        "counter_risk.integrations.powerpoint_com.initialize_powerpoint_application",
        lambda: _FakePowerPointApplication(),
    )

    exported = export_ppt_slides_as_png_via_com(
        source_pptx=source_pptx,
        slide_images_dir=slide_images_dir,
    )

    assert exported == [slide_images_dir / "slide_0001.png", slide_images_dir / "slide_0002.png"]
    assert all(path.exists() for path in exported)
