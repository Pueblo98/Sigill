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
    "POLYMARKET_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
)


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
