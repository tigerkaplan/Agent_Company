# Reviewer Runtime

## Opt-in MEM-02B preparation coverage

An explicitly installed LearningReviewInterface reads one complete declared
intent output inside its project. The ordinary Task Contract must declare the
absolute output file and pin its bytes through existing GOV-01 FILE_DIGEST
verification. The verifier checks the whole operation/proposal/scoped evidence
and binds coverage to both the full intent digest and the exact packaged content.
The package carries the complete untrusted intent, memory records, and bounded
source bodies for evidence and counterevidence. Raw bodies and encoded content
must each fit the existing 128 KiB record ceiling; incomplete content is rejected
without truncation. Ambiguous duplicate JSON fields and excessive nesting fail
closed rather than discarding evidence. String values are sanitized before JSON encoding so escaped
newlines cannot conceal credentials. Source pins remain bound to original bytes.
The disposition owner rechecks coverage and the actual persisted external-evidence
envelope. Missing bodies, stale sources or substituted inputs fail closed.

Learning disposition requires persisted independent PASS and passing required
checks. NEEDS_HUMAN completion acceptance cannot bypass that gate. Review grants no
authority; default review behavior remains unchanged without installation. Test
fixture reviewers are deterministic validation, never independent acceptance of
the implementation. BUILD-64 stops before independent review.

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
