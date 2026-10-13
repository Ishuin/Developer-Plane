"""Tests for environment-driven configuration defaults."""

from pathlib import Path

from dcp.config import Settings, _default_db_path


def test_env_var_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("DCP_DB_PATH", str(tmp_path / "explicit.db"))
    assert _default_db_path() == str(tmp_path / "explicit.db")


def test_legacy_cwd_db_is_preserved(monkeypatch, tmp_path):
    """A pre-existing ./context_fabric.db keeps being used (back-compat)."""
    monkeypatch.delenv("DCP_DB_PATH", raising=False)
    (tmp_path / "context_fabric.db").write_bytes(b"")
    monkeypatch.chdir(tmp_path)
    assert _default_db_path() == str(tmp_path / "context_fabric.db")


def test_new_installs_default_to_home(monkeypatch, tmp_path):
    """No legacy db → single canonical location under ~/.dcp."""
    monkeypatch.delenv("DCP_DB_PATH", raising=False)
    monkeypatch.chdir(tmp_path)  # empty dir, no legacy db
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    assert _default_db_path() == str(home / ".dcp" / "context_fabric.db")


def test_settings_exposes_resolved_db_path(monkeypatch, tmp_path):
    monkeypatch.setenv("DCP_DB_PATH", str(tmp_path / "s.db"))
    assert Settings().db_path == str(tmp_path / "s.db")
