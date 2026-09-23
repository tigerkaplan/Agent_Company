# Runtime

The runtime is the local-first execution coordination layer. It accepts already-classified work from the orchestrator, creates canonical jobs, manages job lifecycle state, queues work, and later lets workers execute jobs through provider abstractions.

Phase 6F adds deterministic verification and a Reviewer Runtime after Phase 6E provider execution. Phase 6G adds persisted scoped human approval requests. Phase 6H adds explicit execution modes and staged controlled mutation. Phase 6I adds an exact local Git change-set and commit gate after reviewed completion. Phase 6J adds separately approved exact-branch push and pull-request creation gates. Phase 6M adds the bounded autonomous Scheduler, claims, leases, retry backoff, restart recovery, and audit status. Jobs remain under `state/jobs/`, execution/provider/review/mutation/Git artifacts under `state/executions/`, approvals under `state/approvals/`, schedules under `state/schedules/`, and scheduler operational state under `state/scheduler-runtime/`. Legal job transitions still come directly from `jobs/lifecycle.yaml`.

The runtime does not classify business intent. Classification, canonical agent routing, workflow selection, risk assessment, review triggers, provider capability resolution, and approval rules remain governed by `../orchestrator/`, `../CONSTITUTION.md`, and `../AGENTS.md`.

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

## Execution Separation

- Dispatcher = decides what the work is.
- Queue = holds runnable jobs.
- Worker = coordinates one execution.
- Executor = performs one provider-neutral `ExecutionRequest`.
- Provider Adapter = translates one canonical execution package into a local engine invocation.
- Provider = actual configured execution engine.
- Reviewer = independent quality and safety stage.
- Approval Runtime = explicit scoped local human authorization boundary.
- Controlled Write Runtime = staged mutation, scope enforcement, and independent evidence.
- Controlled Git Runtime = exact change set, commit approval, staging, commit, and evidence.
- Remote Git Runtime = remote inspection, separate push/PR approvals, exact push, and remote evidence.
- Scheduler = decides when due, already-authorized work may enter the Worker.

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

## Local Runtime Boundary

This remains a local file-backed runtime. Phase 6M adds atomic per-record writes, a local claim transaction lock, an OS-backed singleton scheduler lock, persisted leases, heartbeats, and expiry recovery. Execution remains deliberately sequential with `max_concurrent_jobs=1`; this is not a distributed transaction or multi-host queue.

`local-success` and `local-failure` remain deterministic read-only test executors and are still the default. `--executor provider` is an explicit opt-in that resolves provider eligibility, execution-mode support, preference, observed local executable availability, and fallback from the canonical routing files. Read-only Codex and Claude behavior is unchanged. Codex alone declares `CONTROLLED_WRITE`; Claude support remains unavailable/unverified. Provider process output is bounded, sanitized for likely secrets, and stored as a Git-ignored artifact instead of being copied into job state.

Availability means that the configured executable was observed on the local path. It does not claim authentication, account access, model quality, or successful remote service access. There is no provider SDK/API integration yet, and automated tests use fake adapters/runners so they consume no real provider usage.

For review-required jobs, execution success now enters deterministic verification and the Reviewer Runtime. Only a normalized evidence-backed `PASS` completes the job. `FAIL`, `RETRY`, and `NEEDS_HUMAN` use the existing failure, retry-attempt, and waiting-approval boundaries. See `review/README.md`.

`NEEDS_HUMAN` creates a `PENDING` approval bound to the exact job, execution, review, and `COMPLETE_REVIEWED_JOB` action. Approval completes that reviewed job without re-execution; rejection fails it. Pre-execution governance creates an `EXECUTE_JOB` approval whose acceptance queues only that job. See `approvals/README.md`.

`CONTROLLED_WRITE` is never inferred. It requires a persisted scope, exact approval fingerprint, and review. Codex runs with a fixed `workspace-write` argument array, a fixed native Windows `elevated` sandbox implementation override, and `shell=False` inside a runtime-owned temporary workspace containing only authorized paths. The adapter records requested and effective sandbox modes and fails closed on a downgrade or missing effective metadata. The runtime computes mutation evidence, rejects path/protection/limit violations, and applies only validated changes to the real target. This is staged local control, not OS/container sandbox isolation. See `actions/README.md`.

Canonical `dry_run=true` changes controlled write into preview-only execution below the CLI layer: staged proposals and review evidence are retained, `_apply()` is not called, and deterministic target-integrity evidence must show that the target stayed unchanged. Use `job create --from dispatch-job.json --dry-run`; the flag is serialized into both job state and controlled-write scope.

After a non-dry-run controlled write is completed through deterministic review or explicit human review completion, `git prepare` may build an immutable change set from actual Git state and mutation evidence. It creates a separate `COMMIT_CHANGE_SET` approval. Only an approved, unchanged change set can reach exact-path staging and commit. A verified commit can then enter `git push-prepare`; an exact separately approved push can produce remote evidence, which may enter the separately approved PR gate. Providers cannot invoke any Git boundary. Force push, merge, release, and deployment remain unavailable. See `git/README.md`.

The Scheduler supports bounded `run` and deterministic `run-once` polling in the foreground. Phase 6M does not install a daemon, Windows Service, Task Scheduler task, systemd unit, external scheduler, condition watcher, or cron parser. Remote or multi-user authentication, connectors, REST or web interfaces, databases, VPS/Docker deployment, and external listeners remain out of scope.

The runtime must not redefine agent, skill, workflow, connector, provider, approval, reviewer, or project-state policy. It must not treat inbound messages, webhooks, schedules, or connector reads as approval for downstream external actions.

## CLI

Run from the repository root:

```text
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

Use `--state-root <path>`, `--execution-root <path>`, `--approval-root <path>`, `--schedule-root <path>`, `--scheduler-runtime-root <path>`, and `--git-state-root <path>` before the resource command for isolated storage. The scheduler root environment variable is `AGENT_COMPANY_SCHEDULER_RUNTIME_ROOT`; the existing roots retain their corresponding `AGENT_COMPANY_*_STATE_ROOT` variables.

## Local-First Portability

The contracts and operations here work as local files first. Later phases may move the same model into a background runtime or another approved transport, but those transports must not change the canonical job model or governance boundaries.
