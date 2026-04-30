from __future__ import annotations

import os
from pathlib import Path

import pytest

from sigil import secrets as secrets_module
from sigil.config import config


def test_load_secrets_returns_empty_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SECRETS_ENC_PATH", str(tmp_path / "missing.yaml"))
    result = secrets_module.load_secrets()
    assert result == {}


def test_load_secrets_returns_empty_when_sops_not_on_path(tmp_path, monkeypatch):
    p = tmp_path / "secrets.enc.yaml"
    p.write_text("KALSHI_API_KEY: encrypted\n")
    monkeypatch.setattr(config, "SECRETS_ENC_PATH", str(p))
    monkeypatch.setattr(secrets_module.shutil, "which", lambda _: None)
    result = secrets_module.load_secrets()
    assert result == {}


def test_load_secrets_handles_sops_failure(tmp_path, monkeypatch):
    p = tmp_path / "secrets.enc.yaml"
    p.write_text("KALSHI_API_KEY: enc\n")
    monkeypatch.setattr(config, "SECRETS_ENC_PATH", str(p))
    monkeypatch.setattr(secrets_module.shutil, "which", lambda _: "/fake/sops")

    class _Proc:
        returncode = 1
        stdout = ""
        stderr = "decryption error"

    def _fake_run(*args, **kwargs):
        return _Proc()

    monkeypatch.setattr(secrets_module.subprocess, "run", _fake_run)
    result = secrets_module.load_secrets()
    assert result == {}


def test_load_secrets_parses_yaml_on_success(tmp_path, monkeypatch):
    p = tmp_path / "secrets.enc.yaml"
    p.write_text("placeholder\n")
    monkeypatch.setattr(config, "SECRETS_ENC_PATH", str(p))
    monkeypatch.setattr(secrets_module.shutil, "which", lambda _: "/fake/sops")

    class _Proc:
        returncode = 0
        stdout = "KALSHI_API_KEY: abc\nTELEGRAM_BOT_TOKEN: xyz\n"
        stderr = ""

    monkeypatch.setattr(secrets_module.subprocess, "run", lambda *a, **k: _Proc())
    result = secrets_module.load_secrets()
    assert result == {"KALSHI_API_KEY": "abc", "TELEGRAM_BOT_TOKEN": "xyz"}


def test_inject_into_config_sets_only_missing_values(monkeypatch):
    monkeypatch.setattr(config, "KALSHI_API_KEY", None)
    monkeypatch.setattr(config, "POLYMARKET_API_KEY", "preset")
    # Clear any env-var override
    monkeypatch.delenv("KALSHI_API_KEY", raising=False)
    monkeypatch.delenv("POLYMARKET_API_KEY", raising=False)

    secrets_module.inject_into_config(
        {"KALSHI_API_KEY": "from-sops", "POLYMARKET_API_KEY": "from-sops"}
    )
    assert config.KALSHI_API_KEY == "from-sops"
    # Existing value preserved
    assert config.POLYMARKET_API_KEY == "preset"


def test_inject_into_config_respects_env_var(monkeypatch):
    monkeypatch.setattr(config, "KALSHI_SECRET", None)
    monkeypatch.setenv("KALSHI_SECRET", "from-env")
    secrets_module.inject_into_config({"KALSHI_SECRET": "from-sops"})
    assert config.KALSHI_SECRET is None  # we don't override env-driven values
