# Eval Framework

CORE-03 Eval Framework is COMPLETED / CLOSED / READY TO COMMIT after CORE-03R5
PASS with no Critical, Major, or Minor findings. CORE-04 is NOT STARTED.

CORE-03 adds a provider-independent deterministic measurement layer. Eval asks
what was expected, what was observed, which checks passed or failed, and which
canonical references support that outcome. It is separate from
`ExecutionResult`, Reviewer decisions, approvals, continuation, retry, Git, and
deployment authority.

## Canonical Contracts

`EvalSpec` binds one exact `execution_id` and `job_id` to an evaluator identity,
evaluator version, ordered checks, and bounded reporting metadata. Every spec
begins with exactly one `EXECUTION_RESULT_CONTRACT` check. Check identifiers are
unique and check configuration is bounded structured JSON.

`EvalResult` records `pass`, `fail`, or `error`, ordered structured check
results, canonical evidence references, failed/error check IDs, warnings,
metadata, and creation time. CORE-03 leaves `score` null: categorical
deterministic checks are primary and no arbitrary quality score is inferred.

Evaluator output is untrusted structured data, including output from an
explicitly injected registry used by programmatic callers. Before aggregation,
the runner revalidates every returned `EvalCheckResult` and binds its immutable
check identity (`check_id`, `evaluator_type`, and `severity`) to the originating
`EvalCheckSpec`. A wrong identity, wrong object type, or malformed typed result
becomes a deterministic canonical `error` for the original check; evaluator
output cannot rename or change the policy of the check it answers.

Runner-owned specs and contexts are trust anchors and are never passed to an
evaluator. Typed specs are canonicalized into a new runner-owned model, and
each evaluator invocation receives a disposable reconstructed check and context,
including a separate execution payload and canonical result. Error construction,
returned-output validation, later checks, semantic identity, and persistence use
only the untouched runner-owned values. Mutating an evaluator-visible object
therefore cannot mutate caller input, rename a check, change its severity or
type, alter later checks, or inject content into canonical error evidence.

Evaluator invocation and runner-owned output validation are separate trust
phases. Every exception crossing from evaluator execution is untrusted and maps
to a fixed canonical error message; raw exception text, paths, object
representations, addresses, provider text, and credential-shaped content never
become result or identity material. The private output-validation error is
trusted only when runner validation creates it after an evaluator has returned.
Normalized errors retain the originating check identity and participate in the
same deterministic semantic result digest as every other canonical check.

`fail` means valid input did not meet an expectation. `error` means evaluation
could not safely determine the check, including malformed canonical execution
data, invalid evaluator configuration, unsupported evaluator identity/version,
or an unregistered evaluator. Errors never become passes and mandatory checks
are never silently skipped.

## Deterministic Evaluators

The explicit registry contains only:

- `EXECUTION_RESULT_CONTRACT`, which reuses the CORE-01 schema/model validator;
- `EXPECTED_STATUS`;
- `REQUIRED_EVIDENCE`, matching declared structured evidence rather than prose;
- `REQUIRED_ARTIFACTS`, matching canonical artifact references;
- `FORBIDDEN_CONDITIONS`, covering statuses, blockers, human blockers,
  retryability, and named inert next actions;
- `FIELD_MATCH`, limited to an explicit allowlist of bounded result fields.

`FIELD_MATCH` uses an internal missing-value sentinel. A missing field never
matches JSON `null`; an allowlisted field that is present with a null value can
match null, and all present values continue to use type-strict comparison.

No evaluator name can cause a dynamic import, provider call, shell command, or
arbitrary code execution. Semantic/provider-assisted evaluation is future
scope and has no live stub in CORE-03.

## Identity And Persistence

Every result retains one compact `identity` object containing SHA-256 digests of
the exact canonical EvalSpec, exact supplied ExecutionResult payload, and the
deterministic semantic EvalResult content. The latter includes all persisted
result fields except `eval_id`, `identity`, and `created_at`. The logical
`eval_id` is the first 32 hexadecimal characters of the SHA-256 digest of that
identity object, prefixed by `eval-`; `created_at` is therefore not identity
material. The same input/spec/version produces the same identity and semantic
check content.

Models, validators, persistence creation, and persistence loading all recompute
and verify the semantic-result digest and claimed eval ID. A repeated matching
write safely deduplicates to the existing record; forged IDs, changed identity
digests, result-content tampering, and same-ID semantic mismatches fail closed.

Typed results are atomically persisted as sorted JSON under
`state/executions/evals/`. Loads apply both `eval-result.schema.json` and Python
cross-field invariants. Records are immutable after creation and malformed
persisted results fail closed.

Aggregate `EvalResult.evidence` is a summary capped at the first 100 unique
references in deterministic check/reference order. Complete bounded evidence
remains attached to every check, so the summary cap never drops check-local
evidence. This makes maximum valid evaluator inputs compatible with the result
contract while retaining the existing aggregate bound.

## Authority And Security Boundaries

Eval is measurement evidence only. A pass does not approve work, complete a
review, authorize continuation or retry, clear a recovery hold, mutate a job or
plan, authorize Git, or authorize deployment. Provider identity may be retained
as bounded metadata but never determines check semantics. Provider prose is not
evidence unless the EvalSpec explicitly asks only for the presence of a
canonical structured provider-output evidence entry; it still grants no
authority.

EvalSpec and EvalResult input is treated as untrusted structured data. Schemas
and models bound identifiers, strings, nesting, list/object sizes, numbers,
metadata, and references; prohibit sensitive fields and credential-shaped
content; require content-addressed persistence identifiers; and reject path
traversal. CORE-03 imports the same canonical secret-key and credential-shape
detection used by CORE-01, including assignment-shaped secrets and the
`*_credential` suffix.

## CLI

The existing runtime CLI provides:

```text
python -m runtime.cli eval run --spec path/to/eval-spec.json
python -m runtime.cli eval list
python -m runtime.cli eval show <eval-id>
```

`eval run` loads the exact persisted execution named by the spec, performs no
provider call, and prints/persists the canonical EvalResult.
