# GOV-01 Evidence-Gated Completion

Canonical implementation: `runtime/core/task_contract.py`, JobRuntime terminal
save, existing execution/eval/review/approval stores. Execution success is not DONE.

DONE requires nonempty explicit acceptance criteria, all mapped registered checks
passing, every required check/evidence observation, declared outputs authenticated
against supported file/provider/mutation evidence sources, no contract stop, and
all required review/human gates. File evidence uses bounded deterministic SHA256
observations through CORE-03 FILE_DIGEST. Provider claims and output references
alone cannot prove a deliverable. Unknown evidence sources fail closed.

The execution must have the exact task contract and canonical approval fingerprint.
Independent review must be persisted, schema-valid, after execution, from a distinct
reviewer, bound to the same request/contract, with nonempty checks/evidence and all
checks PASS. Required human completion uses the existing COMPLETE_REVIEWED_JOB
approval. Review PASS remains review PASS while that separate human gate waits.
No agent/provider can fabricate a review or self-approve completion.

Terminal persistence pins a completion receipt before the job becomes completed.
Reload verifies the receipt and full persisted execution/eval/review/artifact/approval
identities; missing or changed evidence fails closed. Source files can change later:
the original accepted file observation remains historical persisted evidence, and
is never re-created from later bytes. Missing acceptance/evidence is reported as
completion blocked, not fabricated success; production defaults remain incomplete.

GOV-01F1 version-2 receipts include required canonical approval artifact digests
and their store root. Verification uses FileApprovalStore, including exact task,
scope and execution/review bindings and agreement with the compact job projection.
Deleting, corrupting, replacing or replaying REJECTED approval evidence invalidates
DONE. Pre-F1 completion receipts require explicit recovery and are never migrated
or reinterpreted automatically.
