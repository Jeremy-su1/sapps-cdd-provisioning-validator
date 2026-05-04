import json
import pytest
from pathlib import Path
from src.validator import detect_drift

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_detect_drift_not_yet_implemented():
    desired = load("sample_desired_state.json")
    actual = load("sample_actual_state.json")
    with pytest.raises(NotImplementedError):
        detect_drift(desired, actual)
