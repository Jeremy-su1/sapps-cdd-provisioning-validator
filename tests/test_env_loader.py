import os
from pathlib import Path

from src.config import load_env_file


def test_load_env_file_populates_missing_variables(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("SCP_ENDPOINT=https://example.test\nSCP_ACCESS_KEY=abc\nSCP_SECRET_KEY=xyz\n", encoding="utf-8")

    monkeypatch.delenv("SCP_ENDPOINT", raising=False)
    monkeypatch.delenv("SCP_ACCESS_KEY", raising=False)
    monkeypatch.delenv("SCP_SECRET_KEY", raising=False)

    load_env_file(env_file)

    assert os.environ["SCP_ENDPOINT"] == "https://example.test"
    assert os.environ["SCP_ACCESS_KEY"] == "abc"
    assert os.environ["SCP_SECRET_KEY"] == "xyz"


def test_load_env_file_does_not_override_existing_variables(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("SCP_ENDPOINT=https://from-file.test\n", encoding="utf-8")

    monkeypatch.setenv("SCP_ENDPOINT", "https://already-set.test")

    load_env_file(env_file)

    assert os.environ["SCP_ENDPOINT"] == "https://already-set.test"
