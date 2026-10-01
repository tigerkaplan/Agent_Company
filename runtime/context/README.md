# Context Discovery Before Action

CORE-08 is CLOSED / COMMITTED at `1a1b029` after CORE-08R3 PASS.
CORE-01-09 are CLOSED / COMMITTED. CORE-09 is committed at `fa7e30f` after
CORE-09R2 PASS; CORE-10 is CLOSED / READY TO COMMIT after CORE-10R3 PASS,
uncommitted against `3e71adc`. CORE-11 is NOT STARTED.

`ExecutionContextBuilder` runs discovery before a provider adapter executes.
It reads canonical governance, the current project checkpoint, Worker-resolved
role/workflow/project references, the pinned skill, and explicit file inputs.
The existing request retains its identity, capability, scope, approval, review,
budget, retry, and continuation boundaries. Explicit clarification or unresolved
capability requirements return a non-retryable `context_unavailable` BLOCKED
result before the provider call. Its inert `supply_context` next actions retain
only material clarification questions, with canonical credential-shape filtering.
Missing files, malformed/stale sources, and
size/path violations preserve the existing typed `ContextBuildError` denial
and the Worker's non-retryable failure contract. No context result authorizes work.

## Selection and loading

`ContextDiscovery` accepts explicit repository roots, a read-only knowledge
adapter, a ranker, material clarification records, and capability requests.
The builder exposes these as local constructor options. Default construction
does not scan the repository, memory stores, tool definitions, or all skills.
Explicit roots are required for code indexing. Explicit file inputs are
material to the task and are retained; discovery does not guess an external
project root from a pathname or broaden the approved write scope.

`skills/catalog.json` contains the 27 existing canonical skills' compact
metadata: version, name, description, required capabilities, inputs, outputs,
prerequisites, references, templates, instruction path, and SHA-256. Empty
optional arrays mean no additional declaration, not satisfied prerequisites.
Catalog hashes use UTF-8 with LF-normalized line endings for checkout
portability. Source provenance hashes retain the original read content.
Changing loaded instructions requires updating their catalog digest. Catalog
entries must be JSON objects; duplicate keys and list-of-pairs entries fail closed.

Before loading local file context, discovery reads the bounded catalog metadata
once when present. Registration and canonical filesystem identity identify
instruction files, including paths such as `docs/playbook.md`; directory and
filename conventions do not decide whether to validate a digest. Unselected
instruction bodies are not loaded. An absent catalog permits ordinary file
discovery, but explicit skill selections still require it. A malformed or
unreadable catalog fails closed. User-only discovery does not load the catalog.

`SkillCatalog.discover` filters capability requirements before relevance
ranking. `load` accepts only known selected IDs, checks their current digest,
and reads only selected instructions. References/templates are inert paths,
never recursively loaded. Required/inherited skill references, including the
Reviewer's executor-skill evidence, use this same digest check. File/index
selections of skill instructions cannot bypass it. All these selections share
the eight-skill load bound and are deduplicated by filesystem identity.
Discovery selection is advisory: the execution
builder continues using the canonical request's pinned skill. Selecting a
different executable skill still requires the existing canonical task flow.
No agent was added.

`RelevanceRanker` serves both skill and context ranking/reranking. It receives
bounded metadata and returns an ordered subset of existing IDs. Unknown IDs,
duplicates, malformed results, and exceptions fail closed. The built-in token
overlap ranker uses stable identity tie-breaking. No provider, model SDK, JEV,
network, or embedding service is required. Optional semantic adapters supply
relevance only and never policy. They must enforce their own call/time bounds;
this synchronous contract does not sandbox arbitrary installed Python code.

`KnowledgeDiscovery` is a metadata-first candidates/load interface for knowledge
or memory. Only selected sources are loaded, with source-kind, identity, count,
and size checks. It adds no memory store, write path, RAG persistence, or default
connector. `MissingInformation` retains only material questions, deduplicates
them by field, and blocks the pack until the caller resolves them. File/read
failures fail closed without inventing a question or missing source content.

## Capability fallback

`resolve_fallback` takes provider-neutral capability requirements and explicitly
configured implementation availability. Order: preferred, alternative,
file/CSV/upload, manual structured input, BLOCKED. Identity breaks ties within
a tier. Capability, scope, authority, evidence, and approvals must all match
exactly. Each rejected/selected candidate has an explicit reason in the result.
The resolver never probes credentials, invokes a connector, executes a file,
accepts remote approval, or changes the requested task capability. File/manual
availability means the caller has the required usable input; it is not inferred
from a vendor outage. Unresolved capability requests block context assembly.
CORE-04 tool discovery/loading remains the source for registered tool selection;
this planning layer adds no tool definitions and no general connector executor.

## Repository intelligence

`repository.py` owns the bounded in-memory repository index. Explicit roots,
directory entry counts, depth, file bytes, and aggregate read bytes bound work.
Hidden/generated directories and unsupported binary files are omitted. Links,
junctions, traversal, absolute paths, drive paths, and alternate streams are
rejected. Trailing-dot/space components are rejected on every platform. Validated
filesystem identities collapse Windows case aliases for index visitation,
exclusions, context deduplication, and catalog instruction lookup. Source refs
retain the filesystem's actual spelling. Python ASTs provide defined symbols, imports, simple call names, and
exact resolvable in-index module edges. `affected` returns one-hop dependencies
and reverse dependants. Calls are syntax observations, not resolved runtime call
edges. Dynamic imports, method dispatch, cross-language symbols, and advanced
graphs are not claimed. Non-Python sources have file-level context; invalid
Python is explicitly marked unparsed. Indexed content is rechecked when loaded.
The foundation lives in `runtime/context/repository.py`; no separate advanced
`runtime/code-intelligence/` subsystem is needed for this bounded implementation.

## Context pack and bounds

Packs distinguish project/state, files/code, skills, knowledge, memory, user,
and capability/tool sources. Each material records its source reference,
original-content SHA-256, starting line, and verbatim/excerpt retention.
Project state retains its current first section, not accumulated dated history.
`file_material(..., lines=(start, end))` preserves exact selected original lines,
including line endings; it never fabricates a summary. Source labels express
provenance, not an authority promotion. External data remains evidence.

Defaults: 256 visited filesystem entries, depth 8, 128 KiB per read, 2 MiB
aggregate reads, 48 pack entries, 512 KiB serialized pack including escaped
content and provenance. Hard ceilings also constrain overrides. Ranking accepts
at most 256 candidates, skill loads at most 8, knowledge candidates at most 32
and selected knowledge at most 4. Duplicate source/range entries collapse;
conflicting provenance fails. No index/pack/selection state is persisted, so
fresh processes rebuild from current sources and deterministic inputs. CORE-09
adds bounded process-local pack reuse after fresh discovery through the provider
context builder; see `runtime/cache/README.md`. Broader external-content
isolation is reserved for CORE-11.

## Validation

Run `python -m unittest runtime.tests.test_context_discovery -q` for CORE-08.
Run `python -m unittest discover -s runtime/tests -q` for the full regression.
CORE-08R3 independently returned PASS with no Critical, Major, or Minor findings.
Stale registered `docs/playbook.md` was rejected through direct file input,
required context, repository discovery/indexing, and `ExecutionContextBuilder`.
Selected/required/inherited freshness, Windows path identity and junction
protection, catalog shape, ordinary file discovery, and authority neutrality
remained intact. A separate same-provider reviewer was used; no cross-provider
review was performed.

R3 validation: 65 CORE-08 tests plus 51 provider/Reviewer tests passed (116
combined); 408 focused/existing regressions and 1054 full runtime tests passed,
with zero failures, errors, or skips. Additional independent adversarial probes
passed. Compilation of 159 Python files, parsing of 31 schemas and the catalog,
and `git diff --check` passed.

### Historical implementation and repair validation

The following checkpoints precede R3 PASS and are retained as historical evidence.

2026-09-30 implementation verification: 44 CORE-08 tests passed; the combined
CORE-08/provider/reviewer/canonical-denial check passed 97 tests; the focused
protected regression passed 408 tests; and the final full runtime regression
passed 1033 tests with no failures, errors, or skips. All 159 runtime/integration
Python files compiled and all 32 schema/catalog JSON files parsed. Diff checks
passed. `PROJECT_STATE.md` records the repaired canonical-denial regressions
and the unchanged progress race-test reruns. No commit was made.

CORE-08F1 repairs the R1 Windows alias, required/inherited skill freshness, and
catalog entry-shape findings. Validation passed: 54 CORE-08 tests (10 new
adversarial tests), 105 combined CORE-08/provider/Reviewer tests, 408 focused
protected regression tests, and 1043 full runtime tests with no failures,
errors, or skips. Compilation of 159 Python files, parsing of 32 JSON files,
and `git diff --check` passed. Independent re-review was pending at this historical checkpoint.

CORE-08F2 removes the R2 instruction-path naming dependency. All four new stale
`docs/playbook.md` reproductions failed before repair and passed afterward.
Validation passed: 65 CORE-08 tests (11 new), 116 combined CORE-08/provider/Reviewer
tests, 408 focused protected regression tests, and 1054 full runtime tests with
no failures, errors, or skips. Compilation of 159 Python files, parsing of 32
JSON files, and `git diff --check` passed. Independent re-review was pending at this historical checkpoint.
