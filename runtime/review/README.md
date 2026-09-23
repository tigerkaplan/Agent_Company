# Reviewer Runtime

Phase 6F separates provider execution from verified completion. A successful `ExecutionResult` is evidence to review; it is not authority to complete a review-required job.

## Flow

```text
execution success -> reviewing -> deterministic verification -> reviewer -> decision
```

Deterministic verification runs first. It checks normalized success, canonical identity and execution mode, the `reviewing` gate, immutable execution evidence, job evidence references, and bounded provider evidence when a provider executed the job. For controlled writes it also requires runtime-observed mutation evidence, no scope/protected-path violation, an applied mutation, and matching staged/target post-fingerprints. A conclusive deterministic failure returns `FAIL` without consuming reviewer-provider usage.

The reviewer receives a bounded package containing job intent, normalized execution metadata, deterministic checks, runtime-owned artifacts, canonical reviewer rules, the applicable original workflow/skill context, and relevant project state. Arbitrary input references are not loaded.

## Decisions

- `PASS`: evidence supports the execution; the reviewing job may complete.
- `FAIL`: the current attempt is invalid and fails without automatic retry.
- `RETRY`: the current attempt fails and the existing `max_attempts` budget may create one traceable child attempt.
- `NEEDS_HUMAN`: automation cannot decide safely; the job enters the existing `waiting_approval` boundary for later human handling.

Provider text cannot transition lifecycle state directly. Provider-backed output must be exactly one JSON object with `decision`, `reason`, and package-owned `evidence_refs`. Invalid, unavailable, timed-out, or failed review execution normalizes to `NEEDS_HUMAN` with a distinct error category.

## Provider Independence

Reviewer selection uses the Phase 6E provider registry, eligibility, weights, availability, and adapters. A different eligible provider is preferred. If none is available, lower-risk work may use the executor provider through a separate reviewer invocation and records `same_provider_review: true`. High-risk work without a different provider returns `NEEDS_HUMAN` under canonical escalation policy.

## Artifacts And Safety

Review artifacts live under `state/executions/reviews/` and are Git-ignored. They contain a bounded sanitized package, bounded sanitized raw output, and the compact normalized result. Job state stores only the review reference and resulting lifecycle/error state.

When a later review package explicitly references Phase 6I `runtime-git-change-set:` or `runtime-git-commit:` artifacts, ReviewerRuntime may load their bounded persisted evidence. Review remains evidence assessment only: `PASS`, `FAIL`, `RETRY`, and `NEEDS_HUMAN` cannot authorize `COMMIT_CHANGE_SET`, stage files, or invoke Git.

Reviewer execution remains read-only/plan-mode. Phase 6H supplies bounded mutation evidence to the reviewer but reviewer text still has no approval or scope-override authority. Provider SDKs, deployment, connector execution, and arbitrary shell commands remain out of scope.
