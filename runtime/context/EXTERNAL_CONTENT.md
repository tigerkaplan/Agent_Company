# CORE-11 external content isolation

CLOSED / COMMITTED at `8bda7eb` after Independent Re-review R2 PASS.
CORE-01-11 are CLOSED / COMMITTED; Core Runtime Foundation = COMPLETE. This is a structural
provider-neutral boundary, not a claim that a model cannot be persuaded.
Existing sandbox, approval, scope, retry/continuation, budget, write, Git and
deployment gates remain runtime controls. No evidence record feeds those gates.

Local ingress calls `external_record(origin, ref, content)` for pasted, web,
email, upload, retrieved, scraped, connector or tool content. These APIs do not
fetch URLs, open uploads, execute tools or install connectors. Callers must keep
the human's task in the canonical request and supply pasted/document bodies in
`ExecutionContextBuilder(external_content=records)`, not concatenate them into
the task. The runtime cannot infer the origin of arbitrary text already placed
in an authorized task string.

Each record requires exact version, origin, ref, content, source_digest, trust
and authority fields. Version is integer 1; trust is untrusted; authority is
none. A digest binds the complete verbatim body. It proves content identity,
not publisher authenticity. Metadata comes from the local ingress, never from
claims inside the body. Unknown/missing fields, wrong primitive types, invalid
origin, authority promotion and mismatched digests fail closed.

CORE-08 materials carry origin/trust/authority alongside existing source, ref,
digest, line and retention fields. Explicit locally resolved canonical context
and catalog-validated selected skills are instructions; input files, project
state, retrieval and tool evidence remain untrusted. Input selection of a
catalog instruction still validates freshness but does not promote its trust.
Provider rendering separates canonical instructions from untrusted evidence;
review rendering retains trust metadata and represents process output as data.
This combines strict contracts, provenance, separate channels in the package,
and existing runtime gates; delimiters and injection keyword detection are not
the enforcement mechanism.

Ingress is bounded by CORE-08 limits: 48 entries, 128 KiB per body and 512 KiB
aggregate by default, plus serialized pack limits. Records are copied at builder
configuration. Cache identity includes provenance and exact content; cached and
fresh materials and provider rendering are revalidated. No trust persistence or
new authority store is added; fresh processes deterministically rebuild packs.

Validation: `python -m unittest runtime.tests.test_external_content
runtime.tests.test_context_discovery runtime.tests.test_context_cache
runtime.tests.test_providers -q`, followed by the full runtime regression suite.
No GOV-01, DEC-01/JEV, memory expansion or new agent definitions are included.

## R2 closure guarantees

R2 PASS confirmed that flattened entries retain original provenance/trust
constraints through context/provider/reviewer rendering: changing flattened trust
cannot promote content, and content/digest mismatch fails closed. Resolver and
metadata reads are bounded before parsing; explicit origins such as connector
survive retrieval. Prompt injection cannot grant runtime authority. CORE-08
integration and existing authority gates remain intact. External content stays
non-authoritative. See PROJECT_STATE.md for preserved R1/F1 and R2 evidence.
V1 scope freeze remains unchanged; GOV/ORCH/MEM/Phase 9 remain NOT STARTED.
Closure rerun: 14 CORE-11 tests passed; git diff --check passed.
