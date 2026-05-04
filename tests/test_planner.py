import json
import pytest
from pathlib import Path
from src.planner import build_action_plan

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_build_action_plan_not_yet_implemented():
    desired = load("sample_desired_state.json")
    with pytest.raises(NotImplementedError):
        build_action_plan(desired, current_state=None)
