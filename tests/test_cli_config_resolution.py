"""Explicit caller config and installed layout resolution regressions."""

from pathlib import Path

from counter_risk import cli


def test_explicit_frozen_cwd_config_wins_over_bundle(tmp_path, monkeypatch):
    cwd = tmp_path / "cwd"
    bundle = tmp_path / "bundle"
    cwd.mkdir()
    bundle.mkdir()
    (cwd / "choice.yml").write_text("cwd")
    (bundle / "choice.yml").write_text("bundle")
    monkeypatch.chdir(cwd)
    monkeypatch.setattr(cli.sys, "frozen", True, raising=False)
    monkeypatch.setenv("COUNTER_RISK_BUNDLE_ROOT", str(bundle))
    assert cli._resolved_cli_config_path(Path("choice.yml"), from_cwd=True) == cwd / "choice.yml"
    (cwd / "choice.yml").unlink()
    assert cli._resolved_cli_config_path(Path("choice.yml"), from_cwd=True) == bundle / "choice.yml"


def test_absolute_config_path_bypasses_cwd_and_bundle(tmp_path, monkeypatch):
    """Absolute --config paths must not be rewritten via CWD or frozen bundle roots."""

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    absolute = elsewhere / "explicit.yml"
    absolute.write_text("absolute")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli.sys, "frozen", True, raising=False)
    monkeypatch.setenv("COUNTER_RISK_BUNDLE_ROOT", str(tmp_path / "bundle"))
    assert cli._resolved_cli_config_path(absolute, from_cwd=True) == absolute
    monkeypatch.setattr(cli.sys, "frozen", False, raising=False)
    assert cli._resolved_cli_config_path(absolute) == absolute


def test_explicit_non_frozen_missing_cwd_file_still_resolves_from_cwd(tmp_path, monkeypatch):
    """Caller --config relative paths resolve from CWD even when the file is absent."""

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli.sys, "frozen", False, raising=False)
    assert (
        cli._resolved_cli_config_path(Path("missing.yml"), from_cwd=True)
        == (tmp_path / "missing.yml").resolve()
    )


def test_installed_default_uses_cwd_without_checkout_assumption(tmp_path, monkeypatch):
    installed = tmp_path / "site-packages/counter_risk/cli/__init__.py"
    installed.parent.mkdir(parents=True)
    installed.touch()
    monkeypatch.setattr(cli, "__file__", str(installed))
    monkeypatch.setattr(cli.sys, "frozen", False, raising=False)
    monkeypatch.chdir(tmp_path)
    assert cli._source_checkout_root() is None
    assert (
        cli._resolved_cli_config_path(Path("config/fixture_replay.yml"))
        == tmp_path / "config/fixture_replay.yml"
    )


def test_checkout_default_is_independent_of_cwd(tmp_path, monkeypatch):
    root = cli._source_checkout_root()
    assert root is not None
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli.sys, "frozen", False, raising=False)
    assert (
        cli._resolved_cli_config_path(Path("config/fixture_replay.yml"))
        == root / "config/fixture_replay.yml"
    )
