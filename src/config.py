"""Small environment-loader helper for local SCP credentials."""

from __future__ import annotations

import os
from pathlib import Path


def load_env_file(path: str | Path | None = None) -> dict[str, str]:
    """Load key/value pairs from a local .env-style file into os.environ.

    Existing environment variables are preserved.
    """
    env_path = Path(path) if path is not None else Path(".env")
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"\'')
        if key and key not in os.environ:
            os.environ[key] = value
            values[key] = value

    return values
