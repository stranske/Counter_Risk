"""Unit tests for the Tkinter runner orchestration helpers."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from counter_risk.gui import runner as gui_runner
from counter_risk.gui.runner import GuiRunState, execute_gui_run, launch_gui
from counter_risk.io.discover import (
    DiscoveryMatch,
    DiscoveryResult,
    DiscoverySelectionRequiredError,
    non_interactive_discovery_prompt,
    reset_discovery_selection_prompt,
    resolve_discovery_selections,
    set_discovery_selection_prompt,
)
from counter_risk.runner_launch import resolve_ppt_output_dir


def test_load_limit_breach_banner_returns_warning_banner(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "limit_breach_summary": {
                    "has_breaches": True,
                    "breach_count": 2,
                    "report_path": "limit_breaches.csv",
                    "warning_banner": "2 fail limit breaches detected. Review limit_breaches.csv.",
                }
            }
        ),
        encoding="utf-8",
    )

    assert (
        gui_runner._load_limit_breach_banner(run_dir)
        == "2 fail limit breaches detected. Review limit_breaches.csv."
    )


def test_load_limit_breach_banner_returns_none_for_missing_or_invalid_manifest(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    assert gui_runner._load_limit_breach_banner(run_dir) is None

    (run_dir / "manifest.json").write_text("{not json", encoding="utf-8")
    assert gui_runner._load_limit_breach_banner(run_dir) is None

    (run_dir / "manifest.json").write_text(
        json.dumps({"limit_breach_summary": {"warning_banner": "  "}}),
        encoding="utf-8",
    )
    assert gui_runner._load_limit_breach_banner(run_dir) is None


def test_execute_gui_run_builds_run_args_and_writes_settings(tmp_path: Path) -> None:
    captured: dict[str, list[str]] = {}

    def fake_runner(argv: list[str]) -> int:
        captured["argv"] = argv
        return 0

    state = GuiRunState(
        as_of_date="2025-12-31",
        run_mode="ex_trend",
        discovery_mode="manual",
        strict_policy="strict",
        formatting_profile="accounting",
        input_root="shared-inputs",
        output_root=str(tmp_path / "runs"),
    )
    result = execute_gui_run(state=state, runner=fake_runner, temp_dir=tmp_path)

    assert result.exit_code == 0
    assert result.output_dir == Path(tmp_path / "runs" / "2025-12-31")
    assert result.settings_path.parent == tmp_path
    assert result.settings_path.name.startswith("counter-risk-runner-settings-")
    assert result.settings_path.suffix == ".json"
    assert result.settings_path.is_file()
    settings_payload = json.loads(result.settings_path.read_text(encoding="utf-8"))
    assert settings_payload["strict_policy"] == "strict"
    assert settings_payload["formatting_profile"] == "accounting"
    assert settings_payload["input_root"] == "shared-inputs"
    assert settings_payload["output_root"] == str(tmp_path / "runs")

    assert captured["argv"] == list(result.cli_args)
    assert captured["argv"][0] == "run"
    assert captured["argv"][2] == "config/ex_trend.yml"
    assert "--as-of-date" in captured["argv"]
    assert "--output-dir" in captured["argv"]
    assert "--settings" in captured["argv"]
    assert "--strict-policy" in captured["argv"]


def test_execute_gui_run_same_date_does_not_produce_fixed_000000_path(tmp_path: Path) -> None:
    existing_run = tmp_path / "runs" / "2025-12-31"
    existing_run.mkdir(parents=True)

    def fake_runner(argv: list[str]) -> int:
        output_dir = Path(argv[argv.index("--output-dir") + 1])
        output_dir.mkdir(parents=True)
        return 0

    state = GuiRunState(as_of_date="2025-12-31", output_root=str(tmp_path / "runs"))

    result = execute_gui_run(state=state, runner=fake_runner, temp_dir=tmp_path)

    assert result.output_dir == Path(tmp_path / "runs" / "2025-12-31_1")
    assert "_000000" not in str(result.output_dir)


def test_execute_gui_run_reads_data_quality_status_after_success(tmp_path: Path) -> None:
    def fake_runner(argv: list[str]) -> int:
        output_dir = Path(argv[argv.index("--output-dir") + 1])
        output_dir.mkdir(parents=True)
        (output_dir / "DATA_QUALITY_SUMMARY.txt").write_text(
            "Counterparty Risk Data Quality Summary\n\n"
            "Overall status: warn (YELLOW) - Review warnings before sending.\n",
            encoding="utf-8",
        )
        return 0

    state = GuiRunState(as_of_date="2025-12-31", output_root=str(tmp_path / "runs"))

    result = execute_gui_run(state=state, runner=fake_runner, temp_dir=tmp_path)

    assert result.data_quality_color == "YELLOW"
    assert result.data_quality_status == "YELLOW - Review warnings"


def test_execute_gui_run_leaves_data_quality_status_empty_on_failure(tmp_path: Path) -> None:
    def fake_runner(_argv: list[str]) -> int:
        print("input validation failed: missing required input")
        return 2

    state = GuiRunState(as_of_date="2025-12-31", output_root=str(tmp_path / "runs"))

    result = execute_gui_run(state=state, runner=fake_runner, temp_dir=tmp_path)

    assert result.exit_code == 2
    assert result.data_quality_color == ""
    assert result.data_quality_status == ""
    assert "Operator action:" in result.error_message
    assert "verify required input files" in result.error_message


def test_execute_gui_run_returns_empty_data_quality_when_summary_missing(tmp_path: Path) -> None:
    def fake_runner(argv: list[str]) -> int:
        output_dir = Path(argv[argv.index("--output-dir") + 1])
        output_dir.mkdir(parents=True)
        return 0

    state = GuiRunState(as_of_date="2025-12-31", output_root=str(tmp_path / "runs"))

    result = execute_gui_run(state=state, runner=fake_runner, temp_dir=tmp_path)

    assert result.exit_code == 0
    assert result.data_quality_color == ""
    assert result.data_quality_status == ""


def test_execute_gui_run_returns_empty_status_for_unknown_data_quality_color(
    tmp_path: Path,
) -> None:
    def fake_runner(argv: list[str]) -> int:
        output_dir = Path(argv[argv.index("--output-dir") + 1])
        output_dir.mkdir(parents=True)
        (output_dir / "DATA_QUALITY_SUMMARY.txt").write_text(
            "Counterparty Risk Data Quality Summary\n\n"
            "Overall status: custom (BLUE) - Custom state.\n",
            encoding="utf-8",
        )
        return 0

    state = GuiRunState(as_of_date="2025-12-31", output_root=str(tmp_path / "runs"))

    result = execute_gui_run(state=state, runner=fake_runner, temp_dir=tmp_path)

    assert result.exit_code == 0
    assert result.data_quality_color == ""
    assert result.data_quality_status == ""


def test_execute_gui_run_resolves_runtime_config_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, list[str]] = {}

    def fake_runner(argv: list[str]) -> int:
        captured["argv"] = argv
        return 0

    monkeypatch.setattr(
        "counter_risk.gui.runner.resolve_runtime_path",
        lambda path: Path("/bundle") / Path(path),
    )
    state = GuiRunState(as_of_date="2025-12-31", run_mode="trend")

    result = execute_gui_run(state=state, runner=fake_runner, temp_dir=tmp_path)

    assert result.exit_code == 0
    assert captured["argv"][2] == str(Path("/bundle/config/trend.yml"))


def test_execute_gui_run_supports_discovery_and_dry_run(tmp_path: Path) -> None:
    captured: list[list[str]] = []

    def fake_runner(argv: list[str]) -> int:
        captured.append(argv)
        return 0

    discover_state = GuiRunState(
        as_of_date="2025-11-15",
        run_mode="all",
        discovery_mode="discover",
        output_root=str(tmp_path / "runs"),
    )
    discover_result = execute_gui_run(state=discover_state, runner=fake_runner, temp_dir=tmp_path)

    assert discover_result.exit_code == 0
    assert "--discover" in discover_result.cli_args
    assert "--as-of-month" in discover_result.cli_args
    assert "--dry-run-discovery" not in discover_result.cli_args

    dry_run_result = execute_gui_run(
        state=discover_state,
        runner=fake_runner,
        dry_run_discovery=True,
        temp_dir=tmp_path,
    )
    assert dry_run_result.exit_code == 0
    assert "--dry-run-discovery" in dry_run_result.cli_args
    assert "--discover" not in dry_run_result.cli_args
    assert dry_run_result.output_dir is None


def test_execute_gui_run_validates_dates_before_runner_call(tmp_path: Path) -> None:
    calls = 0

    def fake_runner(_argv: list[str]) -> int:
        nonlocal calls
        calls += 1
        return 0

    bad_state = GuiRunState(as_of_date="not-a-date")

    try:
        execute_gui_run(state=bad_state, runner=fake_runner, temp_dir=tmp_path)
    except ValueError:
        pass
    else:  # pragma: no cover - defensive branch
        raise AssertionError("Expected ValueError for invalid date input.")

    assert calls == 0


def test_execute_gui_run_cleanup_flag_removes_settings_file(tmp_path: Path) -> None:
    def fake_runner(_argv: list[str]) -> int:
        return 0

    state = GuiRunState(as_of_date="2025-12-31")
    result = execute_gui_run(
        state=state,
        runner=fake_runner,
        temp_dir=tmp_path,
        cleanup_settings_file=True,
    )

    assert result.exit_code == 0
    assert result.settings_path.exists() is False


def test_validate_path_roots_requires_existing_directories(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    runs = tmp_path / "runs"
    inputs.mkdir()
    runs.mkdir()

    valid_state = GuiRunState(
        as_of_date="2025-12-31",
        input_root=str(inputs),
        output_root=str(runs),
    )
    assert gui_runner._validate_path_roots(valid_state) == (True, "")

    missing_state = GuiRunState(
        as_of_date="2025-12-31",
        input_root=str(tmp_path / "missing-inputs"),
        output_root=str(runs),
    )
    valid, message = gui_runner._validate_path_roots(missing_state)
    assert valid is False
    assert "Input Root not found" in message


def test_headless_discover_resolution_never_calls_stdin_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_calls: list[str] = []

    def _fail_if_called(_prompt: str = "") -> str:
        input_calls.append(_prompt)
        raise AssertionError("stdin input() must not be called in GUI/headless discovery")

    monkeypatch.setattr("builtins.input", _fail_if_called)

    file_a = tmp_path / "Report.pptx"
    file_b = tmp_path / "Report - v2.pptx"
    file_a.write_text("x", encoding="utf-8")
    file_b.write_text("x", encoding="utf-8")
    matches = (
        DiscoveryMatch(
            input_name="monthly_pptx",
            path=file_a,
            root_name="template_inputs",
            pattern="Report*.pptx",
        ),
        DiscoveryMatch(
            input_name="monthly_pptx",
            path=file_b,
            root_name="template_inputs",
            pattern="Report*.pptx",
        ),
    )
    result = DiscoveryResult(matches_by_input={"monthly_pptx": matches})

    token = set_discovery_selection_prompt(non_interactive_discovery_prompt)
    try:
        with pytest.raises(DiscoverySelectionRequiredError):
            resolve_discovery_selections(result)
    finally:
        reset_discovery_selection_prompt(token)

    assert input_calls == []


def test_launch_gui_starts_tk_mainloop_with_headless_stubs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: dict[str, object] = {"widgets": []}
    opened_paths: list[Path] = []

    class _FakeStringVar:
        def __init__(self, value: str = "") -> None:
            self._value = value
            self._traces: list[Callable[[], None]] = []

        def get(self) -> str:
            return self._value

        def set(self, value: str) -> None:
            self._value = value
            for callback in self._traces:
                callback()

        def trace_add(self, _mode: str, callback: Callable[..., None]) -> None:
            self._traces.append(lambda: callback())

    class _FakeWidget:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.args = args
            self.kwargs = kwargs
            self.grid_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
            widgets = created["widgets"]
            assert isinstance(widgets, list)
            widgets.append(self)

        def grid(self, *args: object, **kwargs: object) -> None:
            self.grid_calls.append((args, kwargs))

        def configure(self, **kwargs: object) -> None:
            self.kwargs.update(kwargs)

    class _FakeTk:
        def __init__(self) -> None:
            created["root"] = self
            self.title_value = ""
            self.geometry_value = ""
            self.mainloop_called = False
            self.idle_updates = 0
            self.column_config_calls: list[tuple[int, int]] = []

        def title(self, value: str) -> None:
            self.title_value = value

        def geometry(self, value: str) -> None:
            self.geometry_value = value

        def update_idletasks(self) -> None:
            self.idle_updates += 1

        def columnconfigure(self, column: int, weight: int) -> None:
            self.column_config_calls.append((column, weight))

        def after(self, _delay_ms: int, callback: Callable[[], None]) -> None:
            callback()

        def mainloop(self) -> None:
            self.mainloop_called = True

    class _FakeFrame(_FakeWidget):
        def columnconfigure(self, column: int, weight: int) -> None:
            self.column_config_calls = getattr(self, "column_config_calls", [])
            self.column_config_calls.append((column, weight))

    tkinter_module: Any = ModuleType("tkinter")
    tkinter_module.Tk = _FakeTk
    tkinter_module.Toplevel = _FakeWidget
    tkinter_module.Frame = _FakeFrame
    tkinter_module.Label = _FakeWidget
    tkinter_module.Listbox = _FakeWidget
    tkinter_module.Button = _FakeWidget
    tkinter_module.IntVar = _FakeStringVar
    tkinter_module.StringVar = _FakeStringVar
    tkinter_module.messagebox = SimpleNamespace(showerror=lambda *_args, **_kwargs: None)
    tkinter_module.filedialog = SimpleNamespace(askdirectory=lambda **_kwargs: "")

    ttk_module: Any = ModuleType("tkinter.ttk")
    ttk_module.Label = _FakeWidget
    ttk_module.Combobox = _FakeWidget
    ttk_module.Entry = _FakeWidget
    ttk_module.Button = _FakeWidget
    ttk_module.Frame = _FakeFrame
    tkinter_module.ttk = ttk_module

    monkeypatch.setitem(sys.modules, "tkinter", tkinter_module)
    monkeypatch.setitem(sys.modules, "tkinter.ttk", ttk_module)
    monkeypatch.setitem(sys.modules, "tkinter.filedialog", tkinter_module.filedialog)
    monkeypatch.setitem(sys.modules, "tkinter.messagebox", tkinter_module.messagebox)
    monkeypatch.setattr(gui_runner, "_open_path", lambda path: opened_paths.append(path))
    monkeypatch.setattr(gui_runner, "_validate_path_roots", lambda _state: (True, ""))

    launch_gui(
        initial_state=GuiRunState(as_of_date="2025-12-31"),
        runner=lambda _argv: 0,
    )

    fake_root = created.get("root")
    assert fake_root is not None
    assert isinstance(fake_root, _FakeTk)
    assert fake_root.title_value == "Counter Risk Runner"
    assert fake_root.geometry_value == "640x420"
    assert fake_root.mainloop_called is True
    assert (1, 1) in fake_root.column_config_calls
    widgets = created["widgets"]
    assert isinstance(widgets, list)
    ppt_buttons = [
        widget
        for widget in widgets
        if isinstance(widget, _FakeWidget) and widget.kwargs.get("text") == "Open PPT Folder"
    ]
    assert len(ppt_buttons) == 1

    ppt_buttons[0].kwargs["command"]()

    assert opened_paths == [Path("runs/2025-12-31")]


def test_gui_ppt_folder_target_matches_runner_launch_contract() -> None:
    state = GuiRunState(as_of_date="2025-12-31", output_root="runs")

    gui_path = gui_runner._resolve_ppt_output_dir(state)
    runner_launch_path = Path(
        resolve_ppt_output_dir(repo_root=".", selected_date="2025-12-31", output_root="runs")
    )

    normalized_runner_launch_path = Path(
        str(runner_launch_path).replace("\\", "/").removeprefix("./")
    )

    assert gui_path == Path("runs/2025-12-31")
    assert gui_path == normalized_runner_launch_path


def test_main_gui_non_headless_path_calls_launch_gui(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    launch_invocations: list[tuple[GuiRunState, Callable[[list[str]], int] | None]] = []

    def fake_launch_gui(
        *,
        initial_state: GuiRunState | None = None,
        runner: Callable[[list[str]], int] | None = None,
    ) -> None:
        launch_invocations.append((initial_state or GuiRunState(as_of_date="1970-01-31"), runner))

    monkeypatch.setattr(gui_runner, "launch_gui", fake_launch_gui)
    monkeypatch.setattr(gui_runner, "execute_gui_run", lambda **_kwargs: None)

    from counter_risk import cli

    result = cli.main(["gui", "--as-of-date", "2025-12-31"])
    captured = capsys.readouterr()

    assert result == 0
    assert "gui headless run completed" not in captured.out.lower()
    assert len(launch_invocations) == 1
    assert launch_invocations[0][0].as_of_date == "2025-12-31"
