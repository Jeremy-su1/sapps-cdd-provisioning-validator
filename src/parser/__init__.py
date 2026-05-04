"""S2D Excel parser — converts spreadsheet rows to desired_state dict."""

from typing import Any

ParseResult = dict[str, Any]
ParseWarnings = list[str]


def parse_s2d(workbook_path: str) -> tuple[ParseResult, ParseWarnings]:
    """Return (desired_state, warnings). Not yet implemented."""
    raise NotImplementedError("s2d-parser not yet implemented")
