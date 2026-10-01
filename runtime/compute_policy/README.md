# Compute / Effort Policy (CORE-10)

CLOSED / COMMITTED at `dd72cb2` after CORE-10R3 PASS. Implemented against
`3e71adc`; CORE-01-11 are CLOSED / COMMITTED; CORE-11 is CLOSED / COMMITTED at `8bda7eb`.

`ComputePolicy.decide(ExecutionRequest, ComputeInputs | None)` deterministically
returns an immutable `ComputeDecision`. Invalid or unsupported contracts raise
`ComputeError`; valid inputs with no eligible provider return `BLOCKED`.
No decision is execution authorization. There is no decision import/reuse API.

## Trusted inputs and exact work

The Worker constructs `ComputeInputs` from the persisted canonical job's bounded
`compute_requirements`, canonical risk/review fields, and the CORE-05 reservation
snapshot when one exists. Missing optional values remain unknown. These are not
provider output, prompt prose, or confidence scores. The executor accepts an
optional exact-request input contract, not a classifier callback.
Canonical request risk and required review cannot be lowered through inputs.

`binding(request)` hashes the complete validated request, including project,
task, job, execution attempt, capability, references, execution/write scope,
approval fingerprint, continuation and repair identities, and provider preference.
Inputs for another request fail closed. The executor binds the decision to the
resolved repository directory's filesystem identity (`st_dev`, `st_ino`) and
the rendered selected context package before provider selection. Distinct
filesystem directories, including distinct Unicode names, remain distinct;
resolved aliases share identity only when they refer to the same directory.
Missing roots, non-directories, and unavailable filesystem identity fail closed.
A material context change changes that decision identity. Digests identify
evidence, not authenticity or approval.

Absent optional inputs stay explicitly unknown. Unknown factors establish a
STANDARD floor and require at least internal provider clearance; unknown is not
proof of public data or absence of credentials. Default configured providers
have internal clearance, no credential eligibility, and support the four abstract
profiles. Known confidential/restricted material and known credential proximity
require explicit local provider eligibility. There is no automatic content/DLP
classifier or fabricated historical telemetry. Operators must supply known
classification and proximity before exposing that work to a provider.

## Selection rules

The maximum required floor wins. Budget pressure never lowers it.

| Input | FAST floor | STANDARD floor | DEEP floor | CRITICAL floor |
| --- | --- | --- | --- | --- |
| Complexity | simple | moderate / unknown | complex | - |
| Canonical risk | low | - | medium | high / approval_required |
| Sensitivity / file classification | public | internal / unknown | confidential | restricted |
| Credential proximity | none | unknown | near | direct |
| Visibility | internal | unknown | external | public |
| Financial impact | none | unknown | low | high |
| Verification | basic | standard | strong | independent |
| Historical reliability | reliable | unknown | degraded | poor |
| Canonical required review | false | - | true | - |

FAST is minimal effort; STANDARD is normal effort; DEEP is extended analysis;
CRITICAL is the highest effort with strongest requested verification. The CLI
adapters enforce low/medium/high native reasoning settings for FAST/STANDARD/
DEEP: Codex receives `-c model_reasoning_effort=<level>` and Claude receives
`CLAUDE_CODE_EFFORT_LEVEL=<level>` in its invocation environment.
Unsupported CLI adapter identities are rejected. CRITICAL uses high reasoning
and the full configured time cap; lower profiles use caps of 30/90/180 seconds.
The configured timeout remains the
upper bound. This controls invocation settings, not proof of verification.

Filtering runs in this order: classification, credentials, profile support,
cost estimate, time estimate. Provider estimates are trusted policy configuration
and may reflect measured historical performance when available. Defaults are
explicit planning constants: cost units `(1, 2, 4, 8)` and seconds
`(1, 10, 60, 300)`. Cost units are abstract, not currency or a billing claim.
Optional budgets must use these same units. Zero is a real bound; `None` means
no additional compute-routing bound. These estimates do not reserve, spend,
reset, refund, or override CORE-05 budgets, which retain their existing gates.

The existing router intersects the eligible set with canonical capability and
execution-mode restrictions, then retains existing weights, availability,
preference and fallback behavior. No fallback escapes the compute filter.
Successful fallback from a compute-excluded requested provider records
`requested_provider_ineligible_for_compute_policy`; execution-mode exclusion
records `requested_provider_ineligible_for_execution_mode`. An unavailable
eligible preferred provider records `preferred_provider_unavailable` when a
fallback succeeds; no available eligible provider records `no_provider_available`.
Reviewer routing intersects the same compute eligibility set for its package.
Its authority and independence gates remain separate.

## Evidence, bounds, and authority

Decisions include version, exact request-and-context hash, policy/input evidence hash,
profile, reasons with observed values and floors, eligible providers, exclusion
reasons, and an always-empty authority tuple. The execution package carries the
decision; execution results record its profile, hashes and reasons as observation
evidence. Providers cannot return a decision to alter routing. Confidence is
not a routing input and cannot alter effort or authority.

Contracts reject extra fields, subclasses, wrong types, booleans as numbers,
unsupported versions/enums, duplicate providers, and tampered frozen contracts
at decision time. Limits: 32 providers, 4 profiles, 100-character provider IDs,
16 decision reasons of at most 128 characters, integer budgets/estimates up to
1 billion, request binding depth 16, 4096 nodes, and 128 KiB UTF-8 text. Output
is bounded by these fixed contracts. No task text or credentials enter reasons.

Approval, Reviewer completion, retry, continuation, write, Git, deployment and
financial authority remain outside this policy. DEC-01/JEV is not implemented.
Malformed policy and exhausted eligibility block before context construction or
provider execution and do not create retry authority.

The importable implementation path is `runtime/compute_policy/`, replacing the
planned structural label `runtime/compute-policy/`; there is no duplicate tree.

Validation: `python -m unittest runtime.tests.test_compute_policy -q`.

CORE-10R3 final decision: PASS — READY FOR CORE-10 CLOSURE, with no findings.
R3 recorded 46 CORE-10 tests, filesystem probes, 161 focused regressions, and
1153 full runtime tests passing. CORE-10C closure reran the command above:
56 tests passed (46 CORE-10 plus 10 imported adapter tests); `git diff --check`
passed. Full regression evidence belongs to R3 and was not rerun for closure.
