"""Report renderers — JSON and Markdown outputs."""

import json
from typing import Any


def to_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def to_markdown(data: dict[str, Any]) -> str:
    """Render data as a Markdown report. Not yet implemented."""
    raise NotImplementedError("report-generator markdown renderer not yet implemented")
