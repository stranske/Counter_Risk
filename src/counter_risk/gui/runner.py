"""Tkinter operator runner for macro-restricted Counter Risk environments."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from counter_risk.runner_launch import parse_as_of_month
from counter_risk.runtime_paths import resolve_runtime_path

if TYPE_CHECKING:
    from collections.abc import Callable

_RUN_MODE_TO_CONFIG: dict[str, str] = {
    "all": "config/all_programs.yml",
    "ex_trend": "config/ex_trend.yml",
    "trend": "config/trend.yml",
}


@dataclass(frozen=True)
class GuiRunState:
    as_of_date: str
    run_mode: str = "all"
    discovery_mode: str = "manual"
    strict_policy: str = "warn"
    formatting_profile: str = "default"
    input_root: str = "inputs"
    output_root: str = "runs"
    config_path: Path | None = None
    export_pdf: bool | None = None


@dataclass(frozen=True)
class GuiRunResult:
    exit_code: int
    cli_args: tuple[str, ...]
    settings_path: Path
    output_dir: Path | None


def _normalize_run_mode(raw_mode: str) -> str:
    normalized = raw_mode.strip().casefold().replace("-", "_").replace(" ", "_")
    if normalized not in _RUN_MODE_TO_CONFIG:
        return "all"
    return normalized


def _resolve_config_path(state: GuiRunState) -> Path:
    if state.config_path is not None:
        return resolve_runtime_path(state.config_path)
    run_mode = _normalize_run_mode(state.run_mode)
    return resolve_runtime_path(_RUN_MODE_TO_CONFIG[run_mode])


def _resolve_output_dir(state: GuiRunState) -> Path:
    month_end = parse_as_of_month(state.as_of_date)
    output_root = Path(state.output_root.strip() or "runs")
    return output_root / f"{month_end.isoformat()}_000000"


def _build_settings_payload(state: GuiRunState) -> str:
    payload = {
        "input_root": state.input_root.strip() or "inputs",
        "discovery_mode": state.discovery_mode.strip() or "manual",
        "strict_policy": state.strict_policy.strip() or "warn",
        "formatting_profile": state.formatting_profile.strip() or "default",
        "output_root": state.output_root.strip() or "runs",
    }
    return json.dumps(payload, sort_keys=True)


def _write_settings_file(payload: str, temp_dir: Path | None = None) -> Path:
    settings_root = temp_dir or Path(tempfile.gettempdir())
    settings_root.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".json",
        prefix="counter-risk-runner-settings-",
        dir=settings_root,
        delete=False,
    ) as handle:
        handle.write(payload)
        return Path(handle.name)


def _cleanup_settings_file(settings_path: Path) -> None:
    try:
        settings_path.unlink(missing_ok=True)
    except OSError:
        # Best-effort cleanup; run execution result is more important than temp file deletion.
        return


def _build_cli_args(
    *,
    state: GuiRunState,
    settings_path: Path,
    dry_run_discovery: bool,
) -> list[str]:
    config_path = _resolve_config_path(state)
    month_end = parse_as_of_month(state.as_of_date).isoformat()
    cli_args: list[str] = [
        "run",
        "--config",
        str(config_path),
        "--settings",
        str(settings_path),
    ]
    if dry_run_discovery:
        cli_args.extend(["--dry-run-discovery", "--as-of-month", month_end])
    else:
        if state.discovery_mode.strip().casefold() == "discover":
            cli_args.extend(["--discover", "--as-of-month", month_end])
        else:
            cli_args.extend(["--as-of-date", month_end])
        cli_args.extend(["--output-dir", str(_resolve_output_dir(state))])

    if state.strict_policy.strip() in {"warn", "strict"}:
        cli_args.extend(["--strict-policy", state.strict_policy.strip()])
    if state.formatting_profile.strip():
        cli_args.extend(["--formatting-profile", state.formatting_profile.strip()])
    if state.export_pdf is True:
        cli_args.append("--export-pdf")
    if state.export_pdf is False:
        cli_args.append("--no-export-pdf")
    return cli_args


def execute_gui_run(
    *,
    state: GuiRunState,
    runner: Callable[[list[str]], int],
    dry_run_discovery: bool = False,
    temp_dir: Path | None = None,
    cleanup_settings_file: bool = False,
) -> GuiRunResult:
    # Re-using parse_as_of_month keeps validation behavior aligned with Runner.xlsm.
    parse_as_of_month(state.as_of_date)
    settings_payload = _build_settings_payload(state)
    settings_path = _write_settings_file(settings_payload, temp_dir=temp_dir)
    cli_args = _build_cli_args(
        state=state,
        settings_path=settings_path,
        dry_run_discovery=dry_run_discovery,
    )
    try:
        exit_code = int(runner(cli_args))
    finally:
        if cleanup_settings_file:
            _cleanup_settings_file(settings_path)
    output_dir = None if dry_run_discovery else _resolve_output_dir(state)
    return GuiRunResult(
        exit_code=exit_code,
        cli_args=tuple(cli_args),
        settings_path=settings_path,
        output_dir=output_dir,
    )


def _open_path(path: Path) -> bool:
    if not path.exists():
        return False
    if os.name == "nt":
        os.startfile(path)  # type: ignore[attr-defined]
        return True
    command = ["open", str(path)] if sys.platform == "darwin" else ["xdg-open", str(path)]
    subprocess.run(command, check=False)
    return True


def _default_runner(cli_args: list[str]) -> int:
    from counter_risk.cli import main

    return int(main(cli_args))


def launch_gui(
    *,
    initial_state: GuiRunState | None = None,
    runner: Callable[[list[str]], int] | None = None,
) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except Exception as exc:  # pragma: no cover - environment-dependent
        msg = "Tkinter is unavailable; use `counter-risk run` or `counter-risk gui --headless`."
        raise RuntimeError(msg) from exc

    default_as_of_date = parse_as_of_month(date.today().isoformat()).isoformat()
    state = initial_state or GuiRunState(as_of_date=default_as_of_date)
    run_counter_risk = runner or _default_runner

    root = tk.Tk()
    root.title("Counter Risk Runner")
    root.geometry("640x380")

    as_of_var = tk.StringVar(value=state.as_of_date)
    mode_var = tk.StringVar(value=_normalize_run_mode(state.run_mode))
    discovery_var = tk.StringVar(value=state.discovery_mode.strip().casefold() or "manual")
    strict_var = tk.StringVar(value=state.strict_policy)
    format_var = tk.StringVar(value=state.formatting_profile)
    input_root_var = tk.StringVar(value=state.input_root)
    output_root_var = tk.StringVar(value=state.output_root)
    status_var = tk.StringVar(value="Idle")
    result_var = tk.StringVar(value="")

    def _state_from_form() -> GuiRunState:
        return GuiRunState(
            as_of_date=as_of_var.get().strip(),
            run_mode=mode_var.get().strip(),
            discovery_mode=discovery_var.get().strip(),
            strict_policy=strict_var.get().strip(),
            formatting_profile=format_var.get().strip(),
            input_root=input_root_var.get().strip(),
            output_root=output_root_var.get().strip(),
            config_path=None,
        )

    def _run(dry_run_discovery: bool = False) -> None:
        try:
            current = _state_from_form()
            status_var.set("Running...")
            root.update_idletasks()
            result = execute_gui_run(
                state=current,
                runner=run_counter_risk,
                dry_run_discovery=dry_run_discovery,
                cleanup_settings_file=True,
            )
            if result.exit_code == 0:
                status_var.set("Complete")
                result_var.set("Success")
            else:
                status_var.set("Error")
                result_var.set(f"Exit code {result.exit_code}")
        except Exception as exc:  # pragma: no cover - UI safety
            status_var.set("Error")
            result_var.set(str(exc))
            messagebox.showerror("Counter Risk Runner", str(exc))

    def _open_output() -> None:
        current = _state_from_form()
        _open_path(_resolve_output_dir(current))

    def _open_manifest() -> None:
        current = _state_from_form()
        _open_path(_resolve_output_dir(current) / "manifest.json")

    def _open_summary() -> None:
        current = _state_from_form()
        _open_path(_resolve_output_dir(current) / "DATA_QUALITY_SUMMARY.txt")

    def _open_ppt() -> None:
        current = _state_from_form()
        _open_path(_resolve_output_dir(current) / "distribution_static")

    # Form rows
    labels = (
        ("As-Of Date (YYYY-MM-DD)", as_of_var),
        ("Mode", mode_var),
        ("Discovery Mode", discovery_var),
        ("Strict Policy", strict_var),
        ("Formatting Profile", format_var),
        ("Input Root", input_root_var),
        ("Output Root", output_root_var),
    )
    for row_index, (label, var) in enumerate(labels):
        ttk.Label(root, text=label).grid(row=row_index, column=0, sticky="w", padx=8, pady=4)
        if label == "Mode":
            ttk.Combobox(
                root,
                textvariable=var,
                state="readonly",
                values=("all", "ex_trend", "trend"),
            ).grid(row=row_index, column=1, sticky="ew", padx=8, pady=4)
        elif label == "Discovery Mode":
            ttk.Combobox(
                root,
                textvariable=var,
                state="readonly",
                values=("manual", "discover"),
            ).grid(row=row_index, column=1, sticky="ew", padx=8, pady=4)
        elif label == "Strict Policy":
            ttk.Combobox(
                root,
                textvariable=var,
                state="readonly",
                values=("warn", "strict"),
            ).grid(row=row_index, column=1, sticky="ew", padx=8, pady=4)
        else:
            ttk.Entry(root, textvariable=var, width=42).grid(
                row=row_index,
                column=1,
                sticky="ew",
                padx=8,
                pady=4,
            )

    root.columnconfigure(1, weight=1)

    ttk.Button(root, text="Run", command=_run).grid(row=8, column=0, padx=8, pady=8, sticky="ew")
    ttk.Button(root, text="Dry-Run Discovery", command=lambda: _run(True)).grid(
        row=8, column=1, padx=8, pady=8, sticky="ew"
    )

    ttk.Button(root, text="Open Output Folder", command=_open_output).grid(
        row=9, column=0, padx=8, pady=4, sticky="ew"
    )
    ttk.Button(root, text="Open Manifest", command=_open_manifest).grid(
        row=9, column=1, padx=8, pady=4, sticky="ew"
    )
    ttk.Button(root, text="Open Summary", command=_open_summary).grid(
        row=10, column=0, padx=8, pady=4, sticky="ew"
    )
    ttk.Button(root, text="Open PPT Folder", command=_open_ppt).grid(
        row=10, column=1, padx=8, pady=4, sticky="ew"
    )

    ttk.Label(root, text="Status").grid(row=11, column=0, sticky="w", padx=8, pady=4)
    ttk.Label(root, textvariable=status_var).grid(row=11, column=1, sticky="w", padx=8, pady=4)
    ttk.Label(root, text="Result").grid(row=12, column=0, sticky="w", padx=8, pady=4)
    ttk.Label(root, textvariable=result_var).grid(row=12, column=1, sticky="w", padx=8, pady=4)

    root.mainloop()
