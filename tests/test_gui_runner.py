"""Unit tests for the Tkinter runner orchestration helpers."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

from counter_risk.gui import runner as gui_runner
from counter_risk.gui.runner import GuiRunState, execute_gui_run, launch_gui


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
    assert result.output_dir == Path(tmp_path / "runs" / "2025-12-31_000000")
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


def test_execute_gui_run_resolves_runtime_config_path(
    tmp_path: Path,
    monkeypatch,
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


def test_launch_gui_starts_tk_mainloop_with_headless_stubs(monkeypatch) -> None:
    created: dict[str, object] = {}

    class _FakeStringVar:
        def __init__(self, value: str = "") -> None:
            self._value = value

        def get(self) -> str:
            return self._value

        def set(self, value: str) -> None:
            self._value = value

    class _FakeWidget:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.args = args
            self.kwargs = kwargs
            self.grid_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def grid(self, *args: object, **kwargs: object) -> None:
            self.grid_calls.append((args, kwargs))

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

        def mainloop(self) -> None:
            self.mainloop_called = True

    tkinter_module = ModuleType("tkinter")
    tkinter_module.Tk = _FakeTk
    tkinter_module.StringVar = _FakeStringVar
    tkinter_module.messagebox = SimpleNamespace(showerror=lambda *_args, **_kwargs: None)

    ttk_module = ModuleType("tkinter.ttk")
    ttk_module.Label = _FakeWidget
    ttk_module.Combobox = _FakeWidget
    ttk_module.Entry = _FakeWidget
    ttk_module.Button = _FakeWidget
    tkinter_module.ttk = ttk_module

    monkeypatch.setitem(sys.modules, "tkinter", tkinter_module)
    monkeypatch.setitem(sys.modules, "tkinter.ttk", ttk_module)

    launch_gui(
        initial_state=GuiRunState(as_of_date="2025-12-31"),
        runner=lambda _argv: 0,
    )

    fake_root = created.get("root")
    assert fake_root is not None
    assert isinstance(fake_root, _FakeTk)
    assert fake_root.title_value == "Counter Risk Runner"
    assert fake_root.geometry_value == "640x380"
    assert fake_root.mainloop_called is True
    assert (1, 1) in fake_root.column_config_calls


def test_main_gui_non_headless_path_calls_launch_gui(
    monkeypatch,
    capsys,
) -> None:
    launch_invocations: list[tuple[GuiRunState, object | None]] = []

    def fake_launch_gui(*, initial_state: GuiRunState | None = None, runner=None) -> None:
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
