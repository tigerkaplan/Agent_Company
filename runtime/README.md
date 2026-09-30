# Runtime

The runtime is the local-first execution coordination layer. It accepts already-classified work from the orchestrator, creates canonical jobs, manages job lifecycle state, queues work, and later lets workers execute jobs through provider abstractions.

CORE-04 Tool Discovery is CLOSED / COMMITTED at `35f03f8` after CORE-04R5 PASS
with no Critical, Major, or Minor findings. CORE-05 Time / Execution Budget is
CLOSED / COMMITTED at `63813b5` after CORE-05R3 PASS. CORE-06 Retry / Stop
Policy under `retry/` is CLOSED / COMMITTED at `4a6e5c4` after CORE-06R6 PASS.
CORE-07 Progress Events under `progress/` is CLOSED / COMMITTED at
`6bcffa4` after CORE-07R3 PASS. CORE-08 is NEXT / NOT STARTED.
Its bounded append-only journals live under `jobs/.progress/`
and never grant completion, approval, retry, continuation, budget, or write authority.

Phase 6F adds deterministic verification and a Reviewer Runtime after Phase 6E provider execution. Phase 6G adds persisted scoped human approval requests. Phase 6H adds explicit execution modes and staged controlled mutation. Phase 6I adds an exact local Git change-set and commit gate after reviewed completion. Phase 6J adds separately approved exact-branch push and pull-request creation gates. Phase 6M adds the bounded autonomous Scheduler, claims, leases, retry backoff, restart recovery, and audit status. Phase 8B adds one configurable state base root while preserving the repository-local `runtime/state/` default. Phase 8C adds a supervisor-neutral lifecycle wrapper, fixed process types, atomic host-process records, local singleton locks, graceful signals, and a host heartbeat. CORE-03 adds deterministic provider-neutral evaluation under `evals/`. Jobs remain under `jobs/`, execution/provider/review/mutation/Git/eval artifacts under `executions/`, approvals under `approvals/`, schedules under `schedules/`, scheduler operational state under `scheduler-runtime/`, and lifecycle metadata under `host/processes/` beneath that root. Legal job transitions still come directly from `jobs/lifecycle.yaml`.

The runtime does not classify business intent. Classification, canonical agent routing, workflow selection, risk assessment, review triggers, provider capability resolution, and approval rules remain governed by `../orchestrator/`, `../CONSTITUTION.md`, and `../AGENTS.md`. CORE-04 adds capability-first tool discovery and deferred definition loading under `tools/`; it does not replace agent, skill, workflow, or provider routing.

## Canonical Boundaries

- Agent = WHO
- Skill = HOW
- Workflow = ORDER
- Capability = WHAT EXECUTION CAPABILITY IS REQUIRED
- Connector = DATA/ACTION ACCESS
- Provider = EXECUTION ENGINE
- Provider Adapter = HOW RUNTIME TALKS TO THAT ENGINE
- Worker = EXECUTION COORDINATOR
- Runtime = EXECUTION COORDINATION
- Job = ONE EXECUTABLE UNIT OF WORK
- Execution Result = WHAT HAPPENED
- Eval = HOW THE RESULT / BEHAVIOR MET DECLARED EXPECTATIONS
- Tool Discovery = WHICH EXPLICITLY REGISTERED TOOLS MATCH A REQUIRED CAPABILITY
- Deferred Loading = WHEN A SELECTED TOOL'S FULL DEFINITION IS LOADED

## Execution Separation

- Dispatcher = decides what the work is.
- Queue = holds runnable jobs.
- Worker = coordinates one execution.
- Executor = performs one provider-neutral `ExecutionRequest`.
- Provider Adapter = translates one canonical execution package into a local engine invocation.
- Provider = actual configured execution engine.
- Reviewer = independent quality and safety stage.
- EvalRunner = deterministic measurement over one exact EvalSpec and ExecutionResult.
- Approval Runtime = explicit scoped local human authorization boundary.
- Controlled Write Runtime = staged mutation, scope enforcement, and independent evidence.
- Controlled Git Runtime = exact change set, commit approval, staging, commit, and evidence.
- Remote Git Runtime = remote inspection, separate push/PR approvals, exact push, and remote evidence.
- Scheduler = decides when due, already-authorized work may enter the Worker.
- ToolRegistry = discovers compact capability metadata without loading schemas.
- ToolDefinitionLoader = loads only explicitly selected definitions as inert data.
- RetryRuntime = decides and reserves one exact failed-unit retry, or stops at a
  canonical local boundary without replanning.

## Role

The runtime:

- receives a dispatch result from the orchestrator;
- creates one or more canonical jobs from that dispatch result;
- records job lifecycle state, attempts, timestamps, and result references;
- queues runnable jobs;
- preserves waiting states for human approval and independent review;
- allows workers to claim and coordinate queued jobs through an Executor;
- lets a bounded scheduler emit due task intent and claim eligible queued jobs;
- keeps provider execution behind the provider abstraction in `../providers/`;
- preserves connector boundaries from `../integrations/`.
- measures exact persisted execution results without changing job or authority state.
- discovers candidate tools and loads selected definitions without invoking them or granting authority.
- persists bounded retry/stop history and exact-work retry reservations without
  treating provider output or remaining budget as authority.

## Local Runtime Boundary

This remains a local file-backed runtime. Phase 6M adds atomic per-record writes, a local claim transaction lock, an OS-backed singleton scheduler lock, persisted leases, heartbeats, and expiry recovery. Execution remains deliberately sequential with `max_concurrent_jobs=1`; this is not a distributed transaction or multi-host queue.

`local-success` and `local-failure` remain deterministic read-only test executors and are still the default. `--executor provider` is an explicit opt-in that resolves provider eligibility, execution-mode support, preference, observed local executable availability, and fallback from the canonical routing files. Read-only Codex and Claude behavior is unchanged. Codex alone declares `CONTROLLED_WRITE`; Claude support remains unavailable/unverified. Provider process output is bounded, sanitized for likely secrets, and stored as a Git-ignored artifact instead of being copied into job state.

Availability means that the configured executable was observed on the local path. It does not claim authentication, account access, model quality, or successful remote service access. Provider child processes receive a default-deny environment containing only required system variables and that provider's explicitly allowlisted authentication variables. A configured credential root supplies a separate provider-specific `HOME`/`USERPROFILE` and native provider home; unrelated Telegram, webhook, connector, Git, and other-provider variables are not propagated. There is no provider SDK/API integration yet, and automated tests use fake adapters/runners so they consume no real provider usage.

For review-required jobs, execution success now enters deterministic verification and the Reviewer Runtime. Only a normalized evidence-backed `PASS` completes the job. `FAIL`, `RETRY`, and `NEEDS_HUMAN` use the existing failure, retry-attempt, and waiting-approval boundaries. See `review/README.md`.

CORE-03 evaluation is separate from that Reviewer flow. It validates one exact
canonical ExecutionResult against a bounded EvalSpec and persists structured
`pass`, `fail`, or `error` measurement evidence under `executions/evals/`.
Eval never completes review, grants approval, continues or retries a job, clears
a recovery hold, invokes Git, or calls a provider. See `evals/README.md`.

CORE-04 tool discovery is also separate from execution and provider routing. It
matches immutable compact descriptors by exact capability and bounded policy,
then loads full JSON definitions and input schemas only for selected tool IDs.
Candidate, selected, loaded, and authorized are distinct states. No discovery
or load operation invokes a tool or creates Approval, Reviewer, continuation,
retry, recovery-hold, controlled-write, Git, or deployment authority. See
`tools/README.md`.

`NEEDS_HUMAN` creates a `PENDING` approval bound to the exact job, execution, review, and `COMPLETE_REVIEWED_JOB` action. Approval completes that reviewed job without re-execution; rejection fails it. Pre-execution governance creates an `EXECUTE_JOB` approval whose acceptance queues only that job. See `approvals/README.md`.

`CONTROLLED_WRITE` is never inferred. It requires a persisted scope, exact approval fingerprint, and review. Codex runs with a fixed `workspace-write` argument array, a fixed native Windows `elevated` sandbox implementation override, and `shell=False` inside a runtime-owned temporary workspace containing only authorized paths. The adapter records requested and effective sandbox modes and fails closed on a downgrade or missing effective metadata. The runtime computes mutation evidence, rejects path/protection/limit violations, and applies only validated changes to the real target. This is staged local control, not OS/container sandbox isolation. See `actions/README.md`.

Canonical `dry_run=true` changes controlled write into preview-only execution below the CLI layer: staged proposals and review evidence are retained, `_apply()` is not called, and deterministic target-integrity evidence must show that the target stayed unchanged. Use `job create --from dispatch-job.json --dry-run`; the flag is serialized into both job state and controlled-write scope.

After a non-dry-run controlled write is completed through deterministic review or explicit human review completion, `git prepare` may build an immutable change set from actual Git state and mutation evidence. It creates a separate `COMMIT_CHANGE_SET` approval. Only an approved, unchanged change set can reach exact-path staging and commit. A verified commit can then enter `git push-prepare`; an exact separately approved push can produce remote evidence, which may enter the separately approved PR gate. Providers cannot invoke any Git boundary. Force push, merge, release, and deployment remain unavailable. See `git/README.md`.

The Scheduler supports bounded `run` and deterministic `run-once` polling in the foreground. Phase 8C can run it, Telegram, or an opt-in loopback webhook adapter through the same host lifecycle contract. It still does not install a daemon, Windows Service, Task Scheduler task, systemd unit, external scheduler, condition watcher, cron parser, Docker image, or VPS deployment. Public listeners remain out of scope.

The runtime must not redefine agent, skill, workflow, connector, provider, approval, reviewer, or project-state policy. It must not treat inbound messages, webhooks, schedules, or connector reads as approval for downstream external actions.

## CLI

Run from the repository root:

```text
python -m runtime.cli host init [--config <path>] [--base-root <absolute-path>]
python -m runtime.cli host check [--config <path>] [--base-root <absolute-path>]
python -m runtime.cli host processes
python -m runtime.cli host status
python -m runtime.cli host run <scheduler|telegram|webhook-local>
python -m runtime.cli host request-stop <scheduler|telegram|webhook-local>
python -m runtime.cli job create --from dispatch-job.json
python -m runtime.cli job create --from dispatch-job.json --dry-run
python -m runtime.cli job enqueue <job_id>
python -m runtime.cli job list [--status queued]
python -m runtime.cli job show <job_id>
python -m runtime.cli job claim
python -m runtime.cli job transition <job_id> <status>
python -m runtime.cli job complete <job_id>
python -m runtime.cli job fail <job_id> [--code CODE] [--message MESSAGE]
python -m runtime.cli job retry <job_id>
python -m runtime.cli job schedule <job_id> (--at <timestamp> | --delay-seconds <seconds>)
python -m runtime.cli job reschedule <job_id> (--at <timestamp> | --delay-seconds <seconds>)
python -m runtime.cli job cancel <job_id>
python -m runtime.cli worker run-once [--executor local-success|local-failure|provider]
python -m runtime.cli provider list
python -m runtime.cli provider status
python -m runtime.cli review list
python -m runtime.cli review show <review_id>
python -m runtime.cli eval run --spec <eval-spec.json>
python -m runtime.cli eval list
python -m runtime.cli eval show <eval_id>
python -m runtime.cli approval list [--status PENDING|APPROVED|REJECTED]
python -m runtime.cli approval show <approval_id>
python -m runtime.cli approval approve <approval_id> --by <local_operator> [--reason TEXT]
python -m runtime.cli approval reject <approval_id> --by <local_operator> [--reason TEXT]
python -m runtime.cli git prepare --job-id <job_id> --execution-id <execution_id> --repository-root <path> --message <text> [--dry-run]
python -m runtime.cli git list
python -m runtime.cli git show <change_set_id>
python -m runtime.cli git commit <change_set_id>
python -m runtime.cli git push-prepare --change-set-id <change_set_id> --remote origin --branch <branch> [--dry-run]
python -m runtime.cli git push <push_plan_id>
python -m runtime.cli git pr-prepare --push-evidence-id <push_evidence_id> --base <branch> --title <text> --body-file <path> [--dry-run]
python -m runtime.cli git pr-create <pull_request_plan_id>
python -m runtime.cli scheduler create --from schedule.json
python -m runtime.cli scheduler list
python -m runtime.cli scheduler show <schedule_id>
python -m runtime.cli scheduler enable <schedule_id>
python -m runtime.cli scheduler disable <schedule_id>
python -m runtime.cli scheduler tick
python -m runtime.cli scheduler run-once [--dry-run] [--executor local-success|local-failure|provider]
python -m runtime.cli scheduler run [--max-cycles N] [--poll-seconds N] [--dry-run]
python -m runtime.cli scheduler status
python -m runtime.cli scheduler stop
python -m runtime.cli scheduler list-due
```

Use global `--base-root <absolute-path>` or `AGENT_COMPANY_STATE_ROOT` for the
canonical layout. Resolution order is CLI base root, environment base root,
host-config `state_root`, then local `runtime/state/`. Existing component root
CLI options remain available; with a configured canonical base they must equal
the exact derived component path. Legacy component
`AGENT_COMPANY_*_STATE_ROOT` variables are used only
when the local default is selected.

`host init` creates only the canonical directories, is idempotent, and never
migrates or deletes existing state. `host check` is read-only, prints only
secret presence/missing status, and makes no provider, Telegram, webhook, or
other network call. Host mode requires an explicit dedicated state root outside
and non-overlapping with the Git repository; broad roots and repository
ancestors are rejected before directory creation or permission changes.
Provider credentials, state, and secret locations are checked symmetrically.
Malformed dependent configuration is a bounded FAIL rather than an exception.
Windows ACL validation is reported as WARN/operator validation required, never
as POSIX-equivalent PASS. See `../config/host.example.json` and
`../infrastructure/`.

See `host/README.md` for lifecycle state, singleton, signal, heartbeat, and
future-supervisor requirements.

## Local-First Portability

The contracts and operations here work as local files first. Phase 8B provides
host configuration and state foundations. Phase 8C adds only the foreground
lifecycle contract needed by a later supervisor; it does not install one.
Later transports must not change the canonical job model or governance
boundaries.
