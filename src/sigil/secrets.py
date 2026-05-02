"""
Secrets loader: sops + age (REVIEW-DECISIONS.md 1F).

Workflow:
    Encrypted via `sops -e -i secrets.enc.yaml` with age key from
    `~/.config/sigil/age.key`. To decrypt for editing: `sops secrets.enc.yaml`.
    On startup, the API process calls `load_secrets()` which shells out to
    `sops -d <path>` using the env var `SOPS_AGE_KEY_FILE` to locate the age key.
    `inject_into_config()` then maps recognized keys onto the in-memory `config`
    object, but never overrides values already supplied via environment variables.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from typing import Any, Dict

import yaml

from sigil.config import config

logger = logging.getLogger(__name__)


_INJECTABLE_KEYS = (
    "KALSHI_API_KEY",
    "KALSHI_SECRET",
    "KALSHI_KEY_ID",
    "KALSHI_PRIVATE_KEY_PEM",
    "KALSHI_PRIVATE_KEY_PATH",
    "POLYMARKET_API_KEY",
    "ODDSPIPE_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    # Operational flags that often differ between dev + prod. Same
    # injection mechanism as secrets — just lets the operator flip them
    # via secrets.local.yaml without editing config.py.
    "DASHBOARD_ENABLED",
    "DIRECT_EXCHANGE_WS_ENABLED",
    "DEFAULT_MODE",
    "API_BIND_HOST",
    "API_BIND_PORT",
)


_LOCAL_SECRETS_PATH = "secrets.local.yaml"


def load_local_secrets() -> Dict[str, Any]:
    """Plain-YAML fallback for dev when sops/age aren't set up.

    Reads ``./secrets.local.yaml`` (gitignored) if present. Returns ``{}``
    when missing or malformed. ``load_secrets`` already wins over this
    (sops-encrypted secrets take precedence) when both exist.
    """
    if not os.path.exists(_LOCAL_SECRETS_PATH):
        return {}
    try:
        with open(_LOCAL_SECRETS_PATH, "r", encoding="utf-8") as f:
            parsed = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as exc:
        logger.warning("Failed to read %s: %s", _LOCAL_SECRETS_PATH, exc)
        return {}
    if not isinstance(parsed, dict):
        logger.warning("%s did not parse as a mapping; ignoring.", _LOCAL_SECRETS_PATH)
        return {}
    return parsed


def load_secrets() -> Dict[str, Any]:
    """Decrypt `config.SECRETS_ENC_PATH` via sops and parse to dict.

    Returns an empty dict when the file does not exist, or when sops is not on
    PATH. Errors during decryption or YAML parsing are logged and return {}.
    """
    path = config.SECRETS_ENC_PATH
    if not os.path.exists(path):
        logger.info(f"No encrypted secrets file at {path}; skipping sops decrypt.")
        return {}

    if shutil.which("sops") is None:
        logger.warning(
            "sops binary not found on PATH; cannot decrypt %s. "
            "Continuing with env-var-only secrets.",
            path,
        )
        return {}

    env = os.environ.copy()
    if config.SOPS_AGE_KEY_FILE:
        env.setdefault("SOPS_AGE_KEY_FILE", config.SOPS_AGE_KEY_FILE)

    try:
        proc = subprocess.run(
            ["sops", "-d", path],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning(f"sops invocation failed: {exc}")
        return {}

    if proc.returncode != 0:
        logger.warning(
            "sops -d %s exited %d: %s",
            path,
            proc.returncode,
            (proc.stderr or "").strip(),
        )
        return {}

    try:
        parsed = yaml.safe_load(proc.stdout) or {}
    except yaml.YAMLError as exc:
        logger.warning(f"Failed to parse decrypted YAML: {exc}")
        return {}

    if not isinstance(parsed, dict):
        logger.warning("Decrypted secrets did not parse as a mapping; ignoring.")
        return {}

    return parsed


def inject_into_config(secrets: Dict[str, Any]) -> None:
    """Map known secret keys onto the global `config` object.

    Env-var-supplied values win over decrypted secrets.
    """
    for key in _INJECTABLE_KEYS:
        if key not in secrets:
            continue
        if os.environ.get(key):
            continue
        existing = getattr(config, key, None)
        if existing:
            continue
        try:
            setattr(config, key, secrets[key])
        except Exception as exc:
            logger.warning(f"Could not set config.{key}: {exc}")


def load_and_inject() -> int:
    """One-call helper: read sops + ``secrets.local.yaml`` and inject.

    sops-decrypted values take precedence over the local YAML; existing
    config / env values still win over both. Returns the number of
    distinct secret keys that ended up applied to the in-memory config.
    """
    local = load_local_secrets()
    sops = load_secrets()
    merged = {**local, **sops}  # sops wins on conflict
    inject_into_config(merged)
    applied = sum(1 for k in _INJECTABLE_KEYS if k in merged and getattr(config, k, None))
    if applied:
        logger.info("loaded %d secret(s) from sops/local YAML", applied)
    return applied
