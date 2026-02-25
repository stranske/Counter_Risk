from __future__ import annotations

import ast
from pathlib import Path


def _iter_src_python_files() -> list[Path]:
    src_root = Path(__file__).resolve().parents[2] / "src" / "counter_risk"
    return [path for path in src_root.rglob("*.py") if path.name != "futures_delta.py"]


def _target_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def test_compute_futures_delta_callers_unpack_result_and_warnings() -> None:
    call_sites: list[tuple[Path, int]] = []
    violations: list[str] = []

    for py_file in _iter_src_python_files():
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if not isinstance(node.value, ast.Call):
                continue
            if _target_name(node.value.func) != "compute_futures_delta":
                continue

            call_sites.append((py_file, node.lineno))
            if len(node.targets) != 1:
                violations.append(f"{py_file}:{node.lineno}")
                continue

            target = node.targets[0]
            if not isinstance(target, (ast.Tuple, ast.List)) or len(target.elts) != 2:
                violations.append(f"{py_file}:{node.lineno}")

    assert call_sites, "No compute_futures_delta call sites found in src/"
    assert not violations, (
        "compute_futures_delta callers must unpack exactly two values "
        f"(result, warnings). Offending call sites: {violations}"
    )
