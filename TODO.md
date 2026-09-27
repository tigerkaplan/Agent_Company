# Agent Company TODO

## Core Runtime Enhancements

- [x] CORE-01 Canonical Result Contract — COMPLETED / CLOSED / COMMITTED at
  `3f6acb6` after final independent closure review PASS with no Critical or
  Major findings.
- [x] CORE-02 Continuation Policy — COMPLETED / CLOSED / COMMITTED at `9d5ead1`
  after CORE-02R6 PASS with no Critical, Major, or Minor findings.
- [x] CORE-03 Eval Framework — COMPLETED / CLOSED / COMMITTED at `80ead22`
  after CORE-03R5 PASS with no Critical, Major, or Minor findings.
- [ ] CORE-04 Tool Discovery — NEXT / NOT STARTED.
- [ ] CORE-05 Time Budget — PLANNED.
- [ ] CORE-06 Retry / Stop Policy — PLANNED.
- [ ] CORE-07 Progress Events — PLANNED.
- [ ] CORE-08 Context Discovery — PLANNED.
- [ ] CORE-09 Context Cache Policy — PLANNED.
- [ ] CORE-10 Effort Routing — PLANNED.
- [ ] CORE-11 External Content Isolation — PLANNED.
- [ ] FUTURE HARDENING / NON-BLOCKING: add an aggregate serialized-result byte
  ceiling.

## Phase 7 Planning

- [x] Define the Phase 7 threat and authority model in `runtime/remote/AUTHORITY_MODEL.md`.
- [x] Define the remote-command contract in `runtime/remote/COMMAND_CONTRACT.md`.
- [x] Define the Telegram connector/runtime boundary in `integrations/telegram/CONTRACT.md`.
- [x] Define remote approval and rejection interaction in `runtime/remote/AUTHORITY_MODEL.md`.
- [x] Determine the webhook runtime ingestion boundary in `integrations/webhooks/CONTRACT.md`.
- [x] Define Phase 7 acceptance criteria in `runtime/remote/README.md`.

## Phase 7 Implementation Tasks

- [x] Add a canonical RemoteCommand model and deterministic command ID/idempotency validation.
- [x] Add explicit remote identity mapping from stable platform IDs to trusted human or machine identities without tracked secrets.
- [x] Add a RemoteCommandService that calls only existing runtime/orchestrator authority surfaces.
- [x] Persist remote approval audit evidence for authenticated remote actor, source channel, platform identity, command ID, and approval binding.
- [x] Add duplicate update/callback replay protection with persisted command audit records.
- [x] Add Telegram transport adapter tests without calling Telegram APIs.
- [x] Add authenticated local-first webhook ingress with signed trusted machine events, durable replay/idempotency state, canonical routing, bounded audit evidence, and rejected human-approval attempts.
- [x] Add remote notification formatting for approval requested/resolved, job completed/failed, and scheduler/runtime errors.
- [x] Add deny-by-default command permissions and action/project-scoped remote approval policy.
- [x] Restrict Telegram command handling to authenticated private chats.
- [x] Persist remote approval intent before mutation and expose incomplete mutation audit state.
- [x] Reject excessive future command timestamps with bounded clock skew.
- [x] Run the full Phase 6/7 regression suite after security remediation (424/424 PASS on 2026-09-24).
- [x] Pass the final repository-backed Phase 7 architecture and security review
  (142/142 targeted and 430/430 full runtime tests PASS on 2026-09-24).
- [x] Record Phase 7 as COMPLETED / CLOSED; retain a different-provider
  full-repository audit as recommended future validation rather than a gate.

## Phase 8A Design — COMPLETED / CLOSED

- [x] Inventory current always-on-safe runtime assumptions without claiming distributed guarantees.
- [x] Define the canonical host, process, persistent-state, secret, ingress, backup, and authority boundaries.
- [x] Assess Docker, a vendor-neutral VPS target, Telegram long polling, public webhook prerequisites, and optional Hermes use.
- [x] Define the Phase 8 threat model, acceptance criteria, and implementation stages in `infrastructure/`.
- [x] Close the recorded Phase 7 independent review gate before Phase 8 implementation.
- [x] Record Phase 8A as COMPLETED / CLOSED with no deployment and no Phase 8B implementation.
- [x] Implement Phase 8B host configuration, canonical persistence paths,
  initialization, and readiness checks without deploying.
- [x] Repair the Phase 8B independent-review security and correctness findings.
- [x] Pass the Phase 8B independent implementation/security re-review and
  record Phase 8B as COMPLETED / CLOSED.
- [x] Implement Phase 8C background process lifecycle and deterministic recovery
  validation without public exposure.
- [x] Repair the three Phase 8C review blockers: provider-enable bypass,
  signal-callback reentrancy, and startup/stop-request overwrite.
- [x] Complete the successful Phase 8C independent implementation/security
  re-review and record Phase 8C as COMPLETED / CLOSED.
- [x] Implement the Phase 8D Docker adaptation with one non-root image, fixed
  Compose services, persistent canonical state, and no public exposure.
- [x] Complete the Phase 8D independent implementation/security review with no
  critical, major, or required-fix findings and close Phase 8D.
- [ ] Phase 8E is BLOCKED / PAUSED because the VPS has not yet been created;
  deployment has not started.
- [ ] Before Phase 8E production use, build the pinned image on the target Linux
  architecture and perform an SBOM/vulnerability scan.
- [ ] Verify or update the base-image digest where appropriate.
- [ ] Verify fresh named-volume ownership, non-root `host init`, read-only-root
  behavior, and `/tmp` behavior.
- [ ] Verify duplicate-process locking across containers, `docker stop` signal
  delivery, lifecycle final state after stop, and live health transitions.
- [ ] Validate the derived Linux provider image/executable, provider-specific
  credential mount, provider authentication, and provider environment isolation.
- [ ] Run live Telegram, provider, or public-ingress smoke tests only with
  separate explicit approval.
- [ ] Require exact human approval before Phase 8E VPS deployment or any later public exposure.
- [ ] Phase 8F backup/recovery is NOT STARTED.
- [ ] Complete Phase 8G smoke testing and Phase 8H final independent security review.

Non-blocking Phase 8C future hardening: different-provider full-repository
audit, real subprocess singleton-race validation, native Windows signal/ACL
validation, and more race-resistant status-lock probing. Race-resistant
directory-handle containment remains a separate non-blocking Phase 8B item.
