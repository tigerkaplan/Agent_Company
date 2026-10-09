# Canonical graph execution runtime

ORCH-01 implementation; independent review and owner closure remain pending.
The pre-implementation reality classification, invariants and acceptance cases
are in [the graph acceptance contract](../../orchestrator/graph/ACCEPTANCE.md).

`GraphPlanner.build` validates explicit contracted units and dependency order.
`GraphPlanner.split` constructs fan-out units with an optional fan-in/merge node.
Planner/splitter proposals pass the same validator and parent authority checks.
Profiles (planner, splitter, researcher, explorer, worker, critic, deterministic)
travel in canonical ExecutionRequest/package metadata. They do not add canonical
agents, certifications, tools, approval authority or provider policy.

`GraphRuntime` coordinates planner/splitter, worker, deterministic, gate, human
gate, merge and fan-out/fan-in nodes. Every executable unit is a normal JobRuntime
job. Runtime-managed `graph_binding` carries its immutable parent plan digest,
node/profile identity, accepted dependency receipts and optional failed source.
The parent `graph_plan` is a coordination envelope and cannot be executed by a
Worker. TaskContractStore anchors both using its existing paired creation records
and progress observations. Existing job schemas, budget/approval/review stores,
state roots and atomic persistence remain the owners.

## Admission and completion

`advance` admits ready units under the existing cross-process claim transaction,
with deterministic identities and a maximum of 16 active units (including approval
and review pauses). All required dependencies must have canonical task completion
proofs. Each branch starts with explicitly selected parent inputs and only its own
dependency outputs. Sibling outputs never enter its inputs automatically.

Each template has an explicit Task & Authority Contract and acceptance criteria.
Its budget reference is null as a template placeholder, then bound to the parent's
canonical budget. The node may narrow the parent's tools, capabilities, inputs,
delegation level and write scope, or strengthen approval/review requirements.
Filesystem scope narrowing uses the existing canonical matcher. Parent approval
does not approve a child; human gates obtain ApprovalRuntime approval on exact
node work. Gate nodes require ReviewerRuntime and retain its human handoff path.
The parent receipt is verified through the existing ApprovalStore before node
admission and again at certified dispatch/tool boundaries. Persisted dispatch
reconstruction uses the exact approval-store owner recorded in its provenance.
Deterministic operations narrow tools to `local_executor` and run collect,
deduplicate, sort, hash or verify over canonical references through Worker.

`run_ready` executes one admitted batch using separate canonical Workers and a
bounded thread pool. Every claim, retry admission, execution intent, certification,
context, compute decision, effect, result, eval and review remains on its existing
path. The budget owner permits simultaneous reservations only for verified active
graph siblings within their immutable parallel limit. Ordinary budget callers
retain their serial recovery rule. Shared active elapsed time is considered before
another branch reservation; restart conservatively accounts each active window.
Live dispatch reads paired budget evidence under that same owner's transaction,
waiting for a sibling's usage-head/state publication to commit. Canonical claim
lock initialization occurs only after acquiring its byte lock, including delayed
Windows creators; neither repair introduces another lock or persistence owner.

A run is complete when all activated required units have accepted canonical
completion (or a declared, accepted correction/replan substitute). That status
does not assert semantic acceptance of the root's overall business objective:
the root remains a coordination envelope, without invented task_completion proof.

## Correction, replan and restart

Local retries and failed-unit repair use `JobRuntime.retry_or_stop` and RetryRuntime.
A correction/replan edge activates only after a persisted, exact-source canonical
`REPLAN_REQUIRED` decision. The target is a separately contracted, predeclared
task unit; graph output cannot modify the frozen plan or expand its ceiling.
Accepted target output substitutes the failed source at downstream fan-in.
STOP, authority/policy/budget failure, cancellation and rejected gates are terminal
for graph admission. Recovery endpoints are unambiguous, handoffs are bounded,
and revisiting admitted work stops a cycle rather than resetting retry allowance.
Consumers of conditional recovery branches activate only when all their declared
branches activate; fan-in then waits for all of those accepted results.

Graph/run/node state is reconstructed from persisted canonical jobs and their
retry chains, approvals, reviews and dependency receipts. There is no graph-local
state store, scheduler, retry policy or authority ledger. `recover` explicitly
reuses Worker result recovery, budget reconciliation, continuation recovery and
expired-claim recovery. Interrupted admission with incomplete immutable evidence
requires an explicit recovery decision; it never rebuilds missing authority.

## Local API and CLI

Create a graph with `GraphRuntime.create(parent_payload, GraphPlanner.build(...))`.
Use `show`, `advance`, `run_ready(root_id, worker_factory)` and `recover(root_id, worker)`.
The worker factory receives isolated copies of the declared node and canonical
job, selects an existing certified executor/provider, and returns a distinct Worker
using the same job and execution-store owners. Reuse canonical provider, review,
context and compute factories for provider-backed work.

The CLI creates parent payloads through the existing `job create --from` command
(including a canonically ordered `graph_plan`), then offers:

```text
python -m runtime.cli graph show ROOT_JOB_ID
python -m runtime.cli graph advance ROOT_JOB_ID
python -m runtime.cli graph run-once ROOT_JOB_ID --executor provider
python -m runtime.cli graph recover ROOT_JOB_ID --executor provider
```

`run-once` performs one bounded batch; Scheduler/ordinary Workers can process
admitted provider nodes through their existing claims. Deterministic nodes use
the graph deterministic executor. Local-success/local-failure modes are existing
fixture executors, not business task implementations. No daemon or external
connector is introduced. Operational progress remains separate from memory;
learning promotion and MEM-01 are outside this checkpoint.
