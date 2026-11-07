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
