# ORCH-01 invariants and acceptance contract

Defined before implementation, against clean HEAD `8e1381a278b5f3c92c5eedf7fbfb9c9aa6c7bfb8`.
This is executor acceptance, not independent review or owner closure.

## Reality classification

| Requirement | Before implementation | Evidence / real gap |
| --- | --- | --- |
| Execution, certification, review, approval, retry/stop | SATISFIED | `runtime/core/jobs.py`, `workers/worker.py`, `core/capability_governance.py`, `review/`, `approvals/`, `retry/` |
| Budget, continuation, progress, context, compute policy, atomic persistence | SATISFIED | Existing CORE-01-11 owners; no replacement is needed |
| Planner/splitter and graph node/edge contracts | MISSING | ROADMAP ORCH-01; existing dispatcher and workflows route linear jobs |
| Persisted graph/run/node topology and dependency admission | MISSING | Existing job/continuation schemas lack graph identity and dependency bindings |
| Bounded parallel fan-out, isolated branch inputs, partial fan-in | PARTIAL | Canonical claims and Worker exist; graph readiness and concurrency bounds do not |
| Failure propagation, correction/replan edges, approval/review pauses | PARTIAL | Canonical retry and handoff exist; graph-level integration does not |
| Deterministic graph recovery and duplicate admission | MISSING | Existing recovery is per execution/linear continuation, not graph admission |

## Invariants

1. A graph definition is immutable exact work anchored by the existing TaskContractStore.
   A graph root is a coordination envelope, never a provider-executable job.
2. Each node is one canonical job, or its canonical retry lineage. Graph/run/node
   state is reconstructed from these persisted jobs; no separate state store exists.
3. Every admission revalidates the root, exact topology, successful dependency
   completion proofs and parent-to-child GOV-02 ceiling. Approval never transfers
   from parent to child. Managed bindings cannot be supplied to ordinary job creation.
4. Planner, splitter, researcher, explorer, worker and critic are profiles. Every
   execution still uses an existing canonical agent, certified executor and Worker.
5. Admission uses the canonical cross-process claim transaction and deterministic
   node identity. Count queued/running/reviewing/paused nodes against the graph bound.
6. Fan-in waits for all required branches, and receives only their immutable output
   references. Failure/cancellation never becomes successful input. Recovery may
   substitute only a predeclared correction/replan target after canonical REPLAN_REQUIRED.
7. Retries and unit repair belong exclusively to RetryRuntime. STOP, authority denial,
   budget exhaustion, corruption and cancellation cannot be bypassed by an edge.
8. Conditional recovery nodes are dormant until their exact failed source has a
   persisted canonical replan decision. Recovery cycles stop on revisiting a node;
   the finite plan and explicit handoff bound cannot invent unlimited new work.
9. Human gates request ApprovalRuntime approval on their exact node before execution.
   Review gates use ReviewerRuntime. Graph progress cannot approve either handoff.
10. Restart reuses existing claims, results, approvals, retries and node identities.
    Ambiguous interrupted admission fails closed; no automatic evidence reconstruction.
11. All branches share the parent's canonical execution budget. No new budget, refund,
    provider policy, tool allocation, context owner or authority path is introduced.
12. Graph completion requires accepted canonical node completion, including required
    reviews/human gates; successful executor return alone is insufficient. Run completion
    does not assert acceptance of the root's overall business objective.

## Required acceptance tests

- Planner/splitter construction; malformed topology; normal dependency cycles;
  profile/canonical-agent separation; deterministically ordered node admission.
- Parallel fan-out at the bound; eight concurrent duplicate admissions; restart
  after one admitted branch and after execution persistence; partial fan-in.
- Exact input isolation; failed and cancelled branches; merge waits for completion
  proof; unresolved acceptance never becomes graph completion.
- Gate rejection; human pause/approval/rejection; required independent review and
  reviewer-to-human handoff through canonical stores.
- Parent/child narrowing, capability/tool/project/write widening attacks, modified
  topology/binding, direct bypass through ordinary Worker or JobRuntime.
- Canonical retry and correction/replan handoff; cyclic replan visits and handoff
  exhaustion; budget exhaustion across branches and after restart.
- Affected integrations, focused regression, one complete green full regression,
  syntax/schema/reference validation, and `git diff --check`.

MEM-01, learning promotion, new canonical agents, publication and commits are outside
this authorization. Learning observations remain operational progress only.

## Shared-lock acceptance refinement from focused regression

Before repairing the exposed Windows race: initialize a new lock file only after
acquiring its canonical byte lock. A delayed creator must not write or flush while
another handle owns that byte. Verify a deliberately delayed creator, existing
concurrent progress delivery and cross-process delivery through the same owner.
Existing retry REPLAN_REQUIRED tests must assert no graph admission or authority
creation, rather than requiring the now-authorized graph directory to be absent.
Live dispatch must read paired budget usage evidence under the budget owner's
transaction while a parallel sibling finalizes. Verify a deliberately paused
writer between usage-head and state publication; the reader waits for that
transaction, then validates the intact pair without reconstructing either half.
Parent approval status and compact annotations cannot stand in for the canonical
receipt. Before this repair, a direct probe deleted the parent receipt after
child intent creation and still reached the local tool. Verify missing parent
receipts before admission, tampering before dispatch, deletion after intent,
and an explicitly configured canonical approval-store path after reconstruction.

## Final executor reality classification

Existing SATISFIED execution/governance/runtime owners remain the canonical owners.
The initial PARTIAL/MISSING graph requirements above are now SATISFIED by the
implemented graph contracts, canonical persisted jobs, bounded admission/Workers,
verified gates and recovery integration. The complete final validation is recorded
in [VALIDATION.md](VALIDATION.md). Independent review and owner closure are pending.
