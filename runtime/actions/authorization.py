"""Stable authorization boundaries for jobs and execution requests."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from runtime.continuation.models import continuation_plan_digest


def authorization_fingerprint(value: Mapping[str, Any]) -> str:
    boundary = {
        "job_id": value.get("job_id"),
        "attempt": value.get("attempt"),
        "task_class": value.get("task_class"),
        "project_id": value.get("project_id"),
        "agent": value.get("agent"),
        "skill": value.get("skill"),
        "workflow": value.get("workflow"),
        "capability": value.get("capability"),
        "risk_level": value.get("risk_level"),
        "review_required": value.get("review_required"),
        "execution_mode": value.get("execution_mode", "READ_ONLY"),
        "execution_scope": value.get("execution_scope"),
        "task": value.get("task"),
        "input_refs": value.get("input_refs", []),
    }
    if value.get("task_contract") is not None:
        boundary["task_contract"] = value["task_contract"]
    continuation = value.get("continuation")
    if isinstance(continuation, Mapping):
        boundary["continuation"] = {
            "plan_digest": continuation.get("plan_digest"),
            "logical_job_id": continuation.get("logical_job_id"),
            "sequence": continuation.get("sequence"),
            "current_step_id": continuation.get("current_step_id"),
        }
    else:
        explicit_digest = value.get("continuation_plan_digest")
        if explicit_digest is not None:
            boundary["continuation"] = {
                "plan_digest": explicit_digest,
                "logical_job_id": value.get("continuation_logical_job_id"),
                "sequence": value.get("continuation_sequence"),
                "current_step_id": value.get("continuation_step_id"),
            }
    plan = value.get("continuation_plan")
    if plan is not None:
        computed_digest = continuation_plan_digest(plan)
        existing = boundary.get("continuation")
        if isinstance(existing, dict):
            existing["plan_digest"] = computed_digest
        else:
            boundary["continuation"] = {"plan_digest": computed_digest}
    if value.get("dry_run", False) is True:
        boundary["dry_run"] = True
    encoded = json.dumps(
        boundary, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
