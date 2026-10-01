# Context / Prompt Cache Policy

CORE-09 is CLOSED / READY TO COMMIT after CORE-09R2 PASS. It remains uncommitted;
CORE-10 is NOT STARTED.

## Integration and cacheable material

`ExecutionContextBuilder` owns a `ContextCache` by default. Each successful
build performs CORE-08 discovery and validation, then asks the cache to reuse
the immutable READY `ContextPack`. Only selected context evidence is cached:
governance/project-state excerpts, explicit files, selected skills, bounded
repository selections, knowledge/memory, task text, and capability evidence.
BLOCKED packs, execution packages, provider output, approvals, reviewer
decisions, budgets, retry/continuation records, and execution permissions are
not cache entries. Existing provider and Reviewer consumers use this builder.

This is conservative context-object reuse, not a source-read, discovery, ranking,
or provider token-cache optimization. Fresh discovery and serialization still
run on hits. It intentionally makes no latency or token-saving claim. A future
fast path would need equally strong fresh dependency validation.

## Identity and validity

The local builder supplies a bounded canonical binding: resolved repository
root, all canonical request fields except provider selection, selected skill
metadata (including catalog version and instruction digest), discovery limits,
and explicit repository roots. The exact request binds project, logical job,
execution, task text, role, workflow, capability, references, and scope. Provider
selection is excluded because this context pack has no provider-specific text.
Scope namespaces are hashed into the key. Default namespaces are private to a
builder; sharing a cache requires an explicit local user/scope namespace.
The namespace is supplied by trusted local integration, never inferred from
provider output. Different users must receive distinct namespaces.

A SHA-256 slot binds that identity and the complete cache policy/version.
The entry key additionally binds the full freshly validated pack serialization:
ordered source kinds/references, source digests, exact content, selected ranges,
retention, task text, and capability/fallback evidence. A hit requires
canonical model validation and exact serialized-byte equivalence of both
packs, matching key/size, and a valid monotonic creation time. Unknown or
missing fields, noncanonical containers/scalars, and malformed nested material
are rejected before reuse; Python/dataclass equality is not a validity check.
Source digests alone are insufficient. There is no provider-controlled validity
flag, import/put endpoint, filesystem cache loader, or validity callback.

Selected repository content is the relevant repository state. HEAD, unrelated
files, unselected skill metadata, and unrelated working-tree edits do not
invalidate equivalent context. Discovery/ranking and capability resolution run
again, so changed selections, removed sources, skill/catalog mismatches, and
changed availability cannot be hidden by a hit. Knowledge adapters remain
responsible for their existing bounded retrieval contract. Their returned
content and provenance are compared anew. Installed Python adapters are trusted
code, not sandboxed provider output.

## Invalidation and outcomes

- `HIT / validated`: reuse the cached immutable context object after fresh checks.
- `MISS / absent`: no entry exists for this exact isolation/work/options binding.
- `STALE / material_changed`: source/content/provenance changed or entry mismatch;
  discard that entry and use/store only the fresh pack.
- `STALE / expired`: age reached TTL or the monotonic clock moved backward;
  discard the old entry and use/store only the fresh pack.
- `STALE / malformed`: reject malformed cache state and rebuild from fresh material.
- `BYPASS / entry_bound`: fresh context is valid but exceeds cache storage limits;
  return it without retaining it.

Changed binding/policy/skill metadata produces a new key and explicit MISS;
the old entry is unreachable for that new binding and remains only until bounded
LRU eviction. Changed material within a binding replaces its slot. Expiry is
checked on access, with no background scan. Hits do not refresh creation time.
Unavailable, ambiguous, malformed, or stale canonical sources still raise the
existing `ContextBuildError` before cache access; unresolved material questions
still block. The builder clears `last_cache_result` before every build, so an
earlier hit cannot describe a later failed build. That property is diagnostic
evidence only; callers must use each build's returned package.

## Bounds and authority

Defaults: 16 entries, 4 MiB accounted serialized storage, 512 KiB per entry,
300-second TTL. Hard ceilings: 128 entries, 16 MiB aggregate, 2 MiB per entry,
86400-second TTL. Accounting includes serialized identity and fixed overhead,
even though only its hash is retained. Python object overhead is additionally
bounded by entry/material counts and existing pack limits; the byte limit is
not a process-RSS claim. Binding construction has depth, node, text, and
serialized-byte limits. LRU eviction is deterministic and lock-protected.
Cache state is ephemeral: a new process/builder starts cold and revalidates
sources. No persisted restart reuse, cache directory scans, unbounded history,
new memory store, or State Delta operating layer is introduced.

Execution metadata is always reconstructed from the current canonical request.
A cached pack contains `authority: none`. Hits cannot approve work, mark review
complete, grant retry/continuation authority, change budget or write scope,
enable tools, or grant Git/deployment permission. Existing execution gates are
unchanged. Cache policy and scope are local constructor inputs, not new remote
or provider interfaces. Source changes after a completed build remain the
existing snapshot boundary; caching adds no permission to act on changed work.

## Validation

Run `python -m unittest runtime.tests.test_context_cache -q` for CORE-09.
Run `python -m unittest discover -s runtime/tests -q` for full regression.
CORE-09R2 independently passed; closure is documentation-only and uncommitted.

2026-09-30 executor validation: 31 CORE-09 tests; 147 combined CORE-09/context/
provider/Reviewer tests; 534 existing CORE regressions; 287 focused integration
regressions; and 1085 final full runtime tests passed (733.596 seconds for full),
with no failures, errors, or skips. All 162 runtime/integration Python files and
32 schema/catalog JSON files parsed; new-file whitespace and `git diff --check`
passed. No commit was made. CORE-10 remains NOT STARTED.

### CORE-09R1 / CORE-09F1

R1 found one required Minor cached-material validation defect (boolean/float
line metadata accepted through loose equality). F1 adds shared canonical
contract and exact serialization checks plus direct and provider-builder
regressions. Corruption returns STALE / malformed and replaces the entry with
fresh evidence; valid unchanged packs still HIT. The two nonblocking R1
robustness observations are unchanged.

2026-10-01 F1 executor validation: 43 CORE-09 tests; 159 combined
CORE-09/context/provider/Reviewer tests; 469 existing CORE regressions; and
1097 full runtime tests passed, with no failures, errors, or skips. The
boolean/float reproductions failed before repair and now pass, including
provider-package delivery. All 162 runtime/integration Python files and 32
schema/catalog JSON files parsed; repair-file whitespace and `git diff --check`
passed. These were F1 executor checks before R2; no commit or CORE-10 work.

### CORE-09R2 final review

2026-10-01 CORE-09R2 returned PASS with no Critical, Major, or Minor findings.
Independent probes rejected corrupt cached scalar and nested values, missing
or unknown fields, noncanonical pack shapes, and serialization mismatches;
valid unchanged packs still HIT. Provider-builder probes confirmed corrupted
context becomes STALE and cannot enter provider packages or change current
authority. Identity, isolation, invalidation, TTL/LRU/bounds, and fresh
discovery on hits remained intact. R2 validation passed 43 CORE-09 tests,
159 affected context/provider/Reviewer tests, 469 existing CORE regressions,
and 1097 full runtime tests; `git diff --check` passed. CORE-09 is CLOSED /
READY TO COMMIT; CORE-10 is NOT STARTED.
