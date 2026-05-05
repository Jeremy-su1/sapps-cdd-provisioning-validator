"""Typed data quality issue model — used by parser, classifier, and planner."""

from dataclasses import dataclass
from typing import Literal

IssueType = Literal[
    "placeholder_ip",
    "malformed_cidr",
    "unresolved_endpoint",
    "unmatched_filesystem",
    "missing_required_field",
    "duplicate_resource_id",
]

IssueSeverity = Literal["error", "warning", "info"]

IssueResource = Literal["vmware_vm", "subnet", "firewall_rule", "filesystem"]


@dataclass
class DataQualityIssue:
    issue_type: IssueType
    severity: IssueSeverity
    resource: IssueResource
    resource_id: str
    field: str | None
    raw_value: object          # any scalar from Excel; serialized in to_dict()
    message: str

    def to_dict(self) -> dict:
        return {
            "issue_type":  self.issue_type,
            "severity":    self.severity,
            "resource":    self.resource,
            "resource_id": self.resource_id,
            "field":       self.field,
            "raw_value":   str(self.raw_value) if self.raw_value is not None else None,
            "message":     self.message,
        }
