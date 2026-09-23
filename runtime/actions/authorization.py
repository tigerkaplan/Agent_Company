"""Stable authorization boundaries for jobs and execution requests."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


def authorization_fingerprint(value: Mapping[str, Any]) -> str:
    boundary = {
        "job_id": value.get("job_id"),
        "attempt": value.get("attempt"),
        "project_id": value.get("project_id"),
        "capability": value.get("capability"),
        "risk_level": value.get("risk_level"),
        "execution_mode": value.get("execution_mode", "READ_ONLY"),
        "execution_scope": value.get("execution_scope"),
    }
    if value.get("dry_run", False) is True:
        boundary["dry_run"] = True
    encoded = json.dumps(
        boundary, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
