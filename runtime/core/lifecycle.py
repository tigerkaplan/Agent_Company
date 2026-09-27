"""Loader and validator for the canonical runtime job lifecycle."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class LifecycleError(ValueError):
    """Raised for an invalid lifecycle definition or transition."""


def default_lifecycle_path() -> Path:
    return Path(__file__).resolve().parents[1] / "jobs" / "lifecycle.yaml"


class Lifecycle:
    """Read transitions from the canonical JSON-compatible YAML document."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_lifecycle_path()
        with self.path.open("r", encoding="utf-8") as handle:
            self.definition: dict[str, Any] = json.load(handle)
        self._validate_definition()

    @property
    def statuses(self) -> tuple[str, ...]:
        return tuple(self.definition["states"])

    def allowed_targets(self, current: str) -> tuple[str, ...]:
        if current not in self.definition["transitions"]:
            raise LifecycleError(f"Unknown lifecycle status: {current}")
        return tuple(self.definition["transitions"][current])

    def require_transition(self, current: str, target: str) -> None:
        if target not in self.definition["states"]:
            raise LifecycleError(f"Unknown lifecycle status: {target}")
        if target not in self.allowed_targets(current):
            raise LifecycleError(f"Invalid lifecycle transition: {current} -> {target}")

    @property
    def approval_resolution_rule(self) -> dict[str, Any]:
        return self.definition["approval_resolution_rule"]

    @property
    def review_completion_rule(self) -> dict[str, Any]:
        return self.definition["review_completion_rule"]

    @property
    def review_decision_rule(self) -> dict[str, Any]:
        return self.definition["review_decision_rule"]

    def _validate_definition(self) -> None:
        states = self.definition.get("states")
        transitions = self.definition.get("transitions")
        if not isinstance(states, dict) or not isinstance(transitions, dict):
            raise LifecycleError("Lifecycle must define object-valued states and transitions")
        if set(states) != set(transitions):
            raise LifecycleError("Lifecycle states and transition sources must match")
        for source, targets in transitions.items():
            if not isinstance(targets, list) or any(target not in states for target in targets):
                raise LifecycleError(f"Lifecycle has invalid targets for {source}")
        rule = self.definition.get("approval_resolution_rule", {})
        actions = rule.get("actions")
        if rule.get("from") not in states or not isinstance(actions, dict):
            raise LifecycleError("Lifecycle approval resolution rule is invalid")
        if set(actions) != {
            "EXECUTE_JOB",
            "COMPLETE_REVIEWED_JOB",
            "RESOLVE_HUMAN_CONDITION",
        }:
            raise LifecycleError("Lifecycle approval actions are incomplete")
        for action, decisions in actions.items():
            if not isinstance(decisions, dict) or set(decisions) != {
                "APPROVED",
                "REJECTED",
            }:
                raise LifecycleError(
                    f"Lifecycle approval action {action} has invalid decisions"
                )
            for decision, behavior in decisions.items():
                if (
                    not isinstance(behavior, dict)
                    or behavior.get("target") not in states
                ):
                    raise LifecycleError(
                        f"Lifecycle approval {action} {decision} target is invalid"
                    )
        review_rule = self.definition.get("review_completion_rule", {})
        if (
            not isinstance(review_rule.get("condition_field"), str)
            or review_rule.get("target") not in states
            or not isinstance(review_rule.get("allowed_from"), list)
            or any(source not in states for source in review_rule.get("allowed_from", []))
        ):
            raise LifecycleError("Lifecycle review completion rule is invalid")
        decision_rule = self.definition.get("review_decision_rule", {})
        decisions = decision_rule.get("decisions")
        if decision_rule.get("from") not in states or not isinstance(decisions, dict):
            raise LifecycleError("Lifecycle review decision rule is invalid")
        if set(decisions) != {"PASS", "FAIL", "RETRY", "NEEDS_HUMAN"}:
            raise LifecycleError("Lifecycle review decisions are incomplete")
        for decision, behavior in decisions.items():
            if not isinstance(behavior, dict) or not isinstance(
                behavior.get("action"), str
            ):
                raise LifecycleError(
                    f"Lifecycle review decision {decision} is invalid"
                )
            if behavior.get("action") == "transition" and behavior.get("target") not in states:
                raise LifecycleError(
                    f"Lifecycle review decision {decision} has an invalid target"
                )
