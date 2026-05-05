"""NSX-T DFW actual state collector.

In dry-run mode: returns an empty list (no API calls made).
In real mode: raises CollectorError if credentials are missing;
              otherwise would call NSX-T Manager REST API (not yet implemented).
"""

from __future__ import annotations


class CollectorError(Exception):
    """Raised when collection cannot proceed."""


class NsxtDfwCollector:
    """Collect actual NSX-T DFW rule state from NSX-T Manager.

    Args:
        host:     NSX-T Manager hostname or IP.
        token:    Bearer token for API authentication.
        dry_run:  When True, skip all API calls and return empty list.
    """

    def __init__(self, host: str | None, token: str | None, dry_run: bool = False) -> None:
        self.host    = host
        self.token   = token
        self.dry_run = dry_run

    def collect(self) -> list[dict]:
        """Return list of actual DFW rule dicts from NSX-T Manager.

        Returns:
            Empty list in dry_run mode; raises CollectorError if credentials absent.
        """
        if self.dry_run:
            return []

        if not self.host or not self.token:
            raise CollectorError(
                "NSX-T Manager host and token are required for real collection. "
                "Set dry_run=True to skip API calls."
            )

        raise NotImplementedError(
            "Live NSX-T DFW collection not yet implemented. Use dry_run=True."
        )
