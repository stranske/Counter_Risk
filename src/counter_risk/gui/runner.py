"""Tkinter operator runner for macro-restricted Counter Risk environments."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import threading
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from counter_risk.io.discover import (
    DiscoveryMatch,
    DiscoverySelectionRequiredError,
    reset_discovery_selection_prompt,
    set_discovery_selection_prompt,
)
from counter_risk.runner_launch import (
    data_quality_status_label,
    format_gui_run_failure,
    parse_as_of_month,
    read_overall_status_color,
    resolve_existing_output_dir,
    resolve_output_dir,
)
from counter_risk.runtime_paths import resolve_runtime_path

if TYPE_CHECKING:
    from collections.abc import Callable

_RUN_MODE_TO_CONFIG: dict[str, str] = {
    "all": "config/all_programs.yml",
    "ex_trend": "config/ex_trend.yml",
    "trend": "config/trend.yml",
}

_GUI_FIELD_HELP: dict[str, str] = {
    "Mode": "Use All for the routine monthly run; Ex-Trend and Trend run only those report groups.",
    "Discovery Mode": (
        "Manual uses the normal saved input layout. Discover searches the selected input folder "
        "for matching files when names vary."
    ),
    "Strict Policy": (
        "Warn lets the run finish while flagging policy issues. Strict stops when a required "
        "policy check fails."
    ),
    "Formatting Profile": (
        "Use default for standard Counter Risk output. Other profiles apply known historical "
        "PowerPoint and PNG formatting variants."
    ),
}


def get_gui_field_help() -> dict[str, str]:
    """Return operator-facing help text for non-obvious GUI fields."""
    return dict(_GUI_FIELD_HELP)


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
    data_quality_status: str = ""
    data_quality_color: str = ""
    error_message: str = ""


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
    return Path(
        resolve_output_dir(
            repo_root=".",
            selected_date=state.as_of_date,
            output_root=state.output_root.strip() or "runs",
            directory_exists=lambda raw_path: Path(raw_path.replace("\\", "/")).is_dir(),
        ).replace("\\", "/")
    )


def _resolve_existing_output_dir(state: GuiRunState) -> Path:
    return Path(
        resolve_existing_output_dir(
            repo_root=".",
            selected_date=state.as_of_date,
            output_root=state.output_root.strip() or "runs",
            directory_exists=lambda raw_path: Path(raw_path.replace("\\", "/")).is_dir(),
        ).replace("\\", "/")
    )


def _resolve_ppt_output_dir(state: GuiRunState) -> Path:
    return _resolve_output_dir(state)


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


def _validate_path_roots(state: GuiRunState) -> tuple[bool, str]:
    raw_input_root = state.input_root.strip()
    input_root = Path(raw_input_root or "inputs")
    output_root = Path(state.output_root.strip() or "runs")
    if not input_root.is_dir():
        if _is_default_input_root(raw_input_root, input_root):
            return False, _format_getting_started_input_root_message()
        return False, _format_missing_input_root_message(input_root)
    if not output_root.is_dir():
        return False, f"Output Root not found: {output_root}"
    return True, ""


def _is_default_input_root(raw_input_root: str, input_root: Path) -> bool:
    return raw_input_root in {"", "inputs"} and input_root == Path("inputs")


def _input_root_layout_hint() -> str:
    return (
        "Expected inputs include this month's Counter Risk source workbooks or exports, "
        "with exposure, collateral, counterparty, and policy/reference files in the "
        "normal runner input layout."
    )


def _format_getting_started_input_root_message() -> str:
    return (
        "Getting started: use Browse... to select this month's input folder before running. "
        f"{_input_root_layout_hint()}"
    )


def _format_missing_input_root_message(input_root: Path) -> str:
    return (
        f"Input Root not found: {input_root}\n"
        "Use Browse... to select this month's input folder. "
        f"{_input_root_layout_hint()}"
    )


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
    output_dir = None if dry_run_discovery else Path(cli_args[cli_args.index("--output-dir") + 1])
    captured_output = io.StringIO()
    error_message = ""
    try:
        with redirect_stdout(captured_output), redirect_stderr(captured_output):
            exit_code = int(runner(cli_args))
    finally:
        if cleanup_settings_file:
            _cleanup_settings_file(settings_path)
    if exit_code != 0:
        error_message = format_gui_run_failure(
            exit_code=exit_code,
            message=captured_output.getvalue().strip() or f"Process exited with code {exit_code}",
            command=" ".join(cli_args),
        )
    data_quality_color = ""
    data_quality_status = ""
    if exit_code == 0:
        data_quality_color = _read_data_quality_status_color(output_dir)
        data_quality_status = data_quality_status_label(data_quality_color)
    return GuiRunResult(
        exit_code=exit_code,
        cli_args=tuple(cli_args),
        settings_path=settings_path,
        output_dir=output_dir,
        data_quality_status=data_quality_status,
        data_quality_color=data_quality_color,
        error_message=error_message,
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


def _read_data_quality_status_color(output_dir: Path | None) -> str:
    if output_dir is None:
        return ""
    return read_overall_status_color(output_dir / "DATA_QUALITY_SUMMARY.txt")


def _load_limit_breach_banner(run_dir: Path) -> str | None:
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    summary = payload.get("limit_breach_summary")
    if not isinstance(summary, dict):
        return None
    warning_banner = summary.get("warning_banner")
    if not isinstance(warning_banner, str):
        return None
    rendered = warning_banner.strip()
    return rendered or None


class _DiscoveryPromptBridge:
    """Marshal discovery selection prompts onto the Tk main thread."""

    def __init__(self, root: object, tk_module: Any) -> None:
        self._root = root
        self._tk = tk_module

    def __call__(self, input_name: str, matches: tuple[DiscoveryMatch, ...]) -> DiscoveryMatch:
        if threading.current_thread() is threading.main_thread():
            return self._choose_match(input_name, matches)

        value_holder: dict[str, DiscoveryMatch] = {}
        error_holder: dict[str, BaseException] = {}
        done = threading.Event()

        def _prompt_on_main_thread() -> None:
            try:
                value_holder["value"] = self._choose_match(input_name, matches)
            except BaseException as exc:
                error_holder["error"] = exc
            finally:
                done.set()

        after = getattr(self._root, "after", None)
        if after is None:
            raise DiscoverySelectionRequiredError(
                f"Multiple files match '{input_name}', but the GUI is unavailable for selection."
            )
        after(0, _prompt_on_main_thread)
        done.wait()
        error = error_holder.get("error")
        if error is not None:
            raise error
        chosen = value_holder.get("value")
        if chosen is None:
            raise DiscoverySelectionRequiredError(
                f"Discovery selection for '{input_name}' did not return a choice."
            )
        return chosen

    def _choose_match(
        self,
        input_name: str,
        matches: tuple[DiscoveryMatch, ...],
    ) -> DiscoveryMatch:
        if len(matches) == 1:
            return matches[0]

        dialog = self._tk.Toplevel(self._root)
        dialog.title("Select Input File")
        dialog.transient(self._root)
        dialog.grab_set()

        selected_index = self._tk.IntVar(value=1)
        self._tk.Label(
            dialog,
            text=f"Multiple matches found for '{input_name}'. Choose one:",
            anchor="w",
            justify="left",
        ).pack(fill="x", padx=12, pady=(12, 4))

        listbox = self._tk.Listbox(
            dialog, width=72, height=min(len(matches), 8), exportselection=False
        )
        for index, match in enumerate(matches, start=1):
            listbox.insert("end", f"[{index}] {match.path}")
        listbox.selection_set(0)
        listbox.pack(fill="both", expand=True, padx=12, pady=4)

        def _accept() -> None:
            selection = listbox.curselection()
            if selection:
                selected_index.set(selection[0] + 1)
            dialog.destroy()

        def _cancel() -> None:
            selected_index.set(0)
            dialog.destroy()

        button_row = self._tk.Frame(dialog)
        button_row.pack(fill="x", padx=12, pady=(4, 12))
        self._tk.Button(button_row, text="Use Selected", command=_accept).pack(side="right")
        self._tk.Button(button_row, text="Cancel", command=_cancel).pack(side="right", padx=(0, 8))

        dialog.wait_window()
        choice = cast(int, selected_index.get())
        if choice < 1 or choice > len(matches):
            raise DiscoverySelectionRequiredError(
                f"Discovery selection canceled for '{input_name}'."
            )
        return matches[choice - 1]


def launch_gui(
    *,
    initial_state: GuiRunState | None = None,
    runner: Callable[[list[str]], int] | None = None,
) -> None:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except Exception as exc:  # pragma: no cover - environment-dependent
        msg = "Tkinter is unavailable; use `counter-risk run` or `counter-risk gui --headless`."
        raise RuntimeError(msg) from exc

    default_as_of_date = parse_as_of_month(date.today().isoformat()).isoformat()
    state = initial_state or GuiRunState(as_of_date=default_as_of_date)
    run_counter_risk = runner or _default_runner

    root = tk.Tk()
    root.title("Counter Risk Runner")
    root.geometry("640x420")

    as_of_var = tk.StringVar(value=state.as_of_date)
    mode_var = tk.StringVar(value=_normalize_run_mode(state.run_mode))
    discovery_var = tk.StringVar(value=state.discovery_mode.strip().casefold() or "manual")
    strict_var = tk.StringVar(value=state.strict_policy)
    format_var = tk.StringVar(value=state.formatting_profile)
    input_root_var = tk.StringVar(value=state.input_root)
    output_root_var = tk.StringVar(value=state.output_root)
    status_var = tk.StringVar(value="Idle")
    result_var = tk.StringVar(value="")
    quality_var = tk.StringVar(value="")
    limit_banner_var = tk.StringVar(value="None")
    path_feedback_var = tk.StringVar(value="")
    last_output_dir: Path | None = None
    run_in_progress = False
    discovery_prompt_bridge = _DiscoveryPromptBridge(root, tk)

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

    def _set_running(active: bool) -> None:
        nonlocal run_in_progress
        run_in_progress = active
        run_state = "disabled" if active else "normal"
        run_button.configure(state=run_state)
        dry_run_button.configure(state=run_state)
        if active:
            status_var.set("Running… this can take a few minutes")
        _refresh_path_feedback()

    def _refresh_path_feedback() -> None:
        current = _state_from_form()
        valid, message = _validate_path_roots(current)
        if run_in_progress:
            path_feedback_var.set("Run in progress…")
            return
        if valid:
            path_feedback_var.set("Paths look good.")
            run_button.configure(state="normal")
            dry_run_button.configure(state="normal")
            return
        path_feedback_var.set(message)
        run_button.configure(state="disabled")
        dry_run_button.configure(state="disabled")

    def _show_operator_error(title: str, message: str) -> None:
        result_var.set(message)
        messagebox.showerror(title, message)

    def _apply_run_result(result: GuiRunResult) -> None:
        nonlocal last_output_dir
        if result.exit_code == 0:
            status_var.set("Complete")
            result_var.set("Success")
            quality_var.set(result.data_quality_status or "UNAVAILABLE - Summary not found")
            if result.output_dir is not None:
                last_output_dir = result.output_dir
                limit_banner_var.set(_load_limit_breach_banner(result.output_dir) or "None")
            return

        status_var.set("Error")
        result_var.set(result.error_message or f"Exit code {result.exit_code}")
        quality_var.set("")
        limit_banner_var.set("None")
        _show_operator_error(
            "Counter Risk Runner", result.error_message or f"Exit code {result.exit_code}"
        )

    def _run_worker(*, dry_run_discovery: bool, state_snapshot: GuiRunState) -> None:
        prompt_token = set_discovery_selection_prompt(discovery_prompt_bridge)
        try:
            result = execute_gui_run(
                state=state_snapshot,
                runner=run_counter_risk,
                dry_run_discovery=dry_run_discovery,
                cleanup_settings_file=True,
            )
        except DiscoverySelectionRequiredError as exc:
            result = GuiRunResult(
                exit_code=1,
                cli_args=(),
                settings_path=Path("."),
                output_dir=None,
                error_message=str(exc),
            )
        except Exception as exc:  # pragma: no cover - UI safety
            result = GuiRunResult(
                exit_code=1,
                cli_args=(),
                settings_path=Path("."),
                output_dir=None,
                error_message=format_gui_run_failure(
                    exit_code=1,
                    message=str(exc),
                ),
            )
        finally:
            reset_discovery_selection_prompt(prompt_token)

        def _finish() -> None:
            _set_running(False)
            _apply_run_result(result)

        root.after(0, _finish)

    def _run(dry_run_discovery: bool = False) -> None:
        current = _state_from_form()
        valid, message = _validate_path_roots(current)
        if not valid:
            status_var.set("Error")
            path_feedback_var.set(message)
            _show_operator_error("Counter Risk Runner", message)
            return

        _set_running(True)
        result_var.set("")
        quality_var.set("")
        limit_banner_var.set("None")
        worker = threading.Thread(
            target=_run_worker,
            kwargs={
                "dry_run_discovery": dry_run_discovery,
                "state_snapshot": current,
            },
            daemon=True,
        )
        worker.start()

    def _resolve_output_dir_for_open() -> Path:
        current = _state_from_form()
        return last_output_dir or _resolve_existing_output_dir(current)

    def _open_with_feedback(label: str, path: Path) -> None:
        try:
            if not _open_path(path):
                message = f"{label} not found: {path}"
                _show_operator_error("Counter Risk Runner", message)
        except Exception as exc:  # pragma: no cover - UI safety
            message = format_gui_run_failure(exit_code=1, message=str(exc))
            _show_operator_error("Counter Risk Runner", message)

    def _open_output() -> None:
        try:
            _open_with_feedback("Output folder", _resolve_output_dir_for_open())
        except Exception as exc:  # pragma: no cover - UI safety
            _show_operator_error(
                "Counter Risk Runner",
                format_gui_run_failure(exit_code=1, message=str(exc)),
            )

    def _open_manifest() -> None:
        try:
            _open_with_feedback("Manifest", _resolve_output_dir_for_open() / "manifest.json")
        except Exception as exc:  # pragma: no cover - UI safety
            _show_operator_error(
                "Counter Risk Runner",
                format_gui_run_failure(exit_code=1, message=str(exc)),
            )

    def _open_summary() -> None:
        try:
            _open_with_feedback(
                "Data quality summary",
                _resolve_output_dir_for_open() / "DATA_QUALITY_SUMMARY.txt",
            )
        except Exception as exc:  # pragma: no cover - UI safety
            _show_operator_error(
                "Counter Risk Runner",
                format_gui_run_failure(exit_code=1, message=str(exc)),
            )

    def _open_ppt() -> None:
        try:
            _open_with_feedback("PPT output folder", _resolve_output_dir_for_open())
        except Exception as exc:  # pragma: no cover - UI safety
            _show_operator_error(
                "Counter Risk Runner",
                format_gui_run_failure(exit_code=1, message=str(exc)),
            )

    def _browse_directory(target_var: tk.StringVar) -> None:
        selected = filedialog.askdirectory(initialdir=target_var.get() or ".")
        if selected:
            target_var.set(selected)
            _refresh_path_feedback()

    def _browse_command(target_var: tk.StringVar) -> Callable[[], None]:
        def _command() -> None:
            _browse_directory(target_var)

        return _command

    def _run_dry_discovery() -> None:
        _run(True)

    # Form rows
    labels = (
        ("As-Of Date (YYYY-MM-DD)", as_of_var, "entry"),
        ("Mode", mode_var, "mode"),
        ("Discovery Mode", discovery_var, "discovery"),
        ("Strict Policy", strict_var, "strict"),
        ("Formatting Profile", format_var, "entry"),
        ("Input Root", input_root_var, "input_root"),
        ("Output Root", output_root_var, "output_root"),
    )
    field_help = get_gui_field_help()
    for row_index, (label, var, field_kind) in enumerate(labels):
        ttk.Label(root, text=label).grid(row=row_index, column=0, sticky="w", padx=8, pady=4)
        if field_kind == "mode":
            ttk.Combobox(
                root,
                textvariable=var,
                state="readonly",
                values=("all", "ex_trend", "trend"),
            ).grid(row=row_index, column=1, sticky="ew", padx=8, pady=4)
        elif field_kind == "discovery":
            ttk.Combobox(
                root,
                textvariable=var,
                state="readonly",
                values=("manual", "discover"),
            ).grid(row=row_index, column=1, sticky="ew", padx=8, pady=4)
        elif field_kind == "strict":
            ttk.Combobox(
                root,
                textvariable=var,
                state="readonly",
                values=("warn", "strict"),
            ).grid(row=row_index, column=1, sticky="ew", padx=8, pady=4)
        elif field_kind in {"input_root", "output_root"}:
            path_row = ttk.Frame(root)
            path_row.grid(row=row_index, column=1, sticky="ew", padx=8, pady=4)
            path_row.columnconfigure(0, weight=1)
            ttk.Entry(path_row, textvariable=var).grid(row=0, column=0, sticky="ew")
            ttk.Button(
                path_row,
                text="Browse…",
                command=_browse_command(var),
            ).grid(row=0, column=1, padx=(8, 0))
        else:
            ttk.Entry(root, textvariable=var, width=42).grid(
                row=row_index,
                column=1,
                sticky="ew",
                padx=8,
                pady=4,
            )
        if label in field_help:
            ttk.Label(root, text=field_help[label], wraplength=240).grid(
                row=row_index,
                column=2,
                sticky="w",
                padx=(0, 8),
                pady=4,
            )

    root.columnconfigure(1, weight=1)

    run_button = ttk.Button(root, text="Run", command=_run)
    run_button.grid(row=8, column=0, padx=8, pady=8, sticky="ew")
    dry_run_button = ttk.Button(
        root,
        text="Dry-Run Discovery",
        command=_run_dry_discovery,
    )
    dry_run_button.grid(row=8, column=1, padx=8, pady=8, sticky="ew")

    ttk.Label(root, textvariable=path_feedback_var).grid(
        row=9, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 4)
    )

    ttk.Button(root, text="Open Output Folder", command=_open_output).grid(
        row=10, column=0, padx=8, pady=4, sticky="ew"
    )
    ttk.Button(root, text="Open Manifest", command=_open_manifest).grid(
        row=10, column=1, padx=8, pady=4, sticky="ew"
    )
    ttk.Button(root, text="Open Summary", command=_open_summary).grid(
        row=11, column=0, padx=8, pady=4, sticky="ew"
    )
    ttk.Button(root, text="Open PPT Folder", command=_open_ppt).grid(
        row=11, column=1, padx=8, pady=4, sticky="ew"
    )

    ttk.Label(root, text="Status").grid(row=12, column=0, sticky="w", padx=8, pady=4)
    ttk.Label(root, textvariable=status_var).grid(row=12, column=1, sticky="w", padx=8, pady=4)
    ttk.Label(root, text="Result").grid(row=13, column=0, sticky="w", padx=8, pady=4)
    ttk.Label(root, textvariable=result_var).grid(row=13, column=1, sticky="w", padx=8, pady=4)
    ttk.Label(root, text="Data Quality").grid(row=14, column=0, sticky="w", padx=8, pady=4)
    ttk.Label(root, textvariable=quality_var).grid(row=14, column=1, sticky="w", padx=8, pady=4)
    ttk.Label(root, text="Limit Breach").grid(row=15, column=0, sticky="w", padx=8, pady=4)
    ttk.Label(root, textvariable=limit_banner_var).grid(
        row=15, column=1, sticky="w", padx=8, pady=4
    )

    for trace_name in (input_root_var, output_root_var):
        trace_name.trace_add("write", lambda *_args: _refresh_path_feedback())
    _refresh_path_feedback()

    root.mainloop()
