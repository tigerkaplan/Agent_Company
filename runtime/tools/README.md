# Tool Discovery And Deferred Loading

CORE-04 is CLOSED / COMMITTED at `35f03f8` after CORE-04R5 PASS with no Critical,
Major, or Minor findings. CORE-05 is CLOSED / COMMITTED at `63813b5` after
CORE-05R3 PASS; CORE-06 is NEXT / NOT STARTED.

CORE-04 is a provider-independent runtime capability. It does not create a Tool
Discovery Agent. `ToolRegistry` answers which explicitly registered tools could
satisfy canonical capability requirements; `ToolDefinitionLoader` loads full
data for an already selected subset. Neither object executes a tool.

## Contracts

`ToolDescriptor` is compact immutable registration metadata: stable tool ID and
version, name and description, exact capabilities, declared authority and risk
classes, tool class, provider/agent/workflow compatibility, availability,
status, tags, deterministic preference rank, and trusted-root-relative
definition/schema references. Full schemas and execution context are not part
of the descriptor. Serializable descriptor, request, result, definition, and
schema strings reuse the shared canonical credential-shape detector and fail
closed instead of emitting detected secrets.

`ToolDiscoveryRequest` contains at most 20 required capabilities and optional
bounded agent, workflow, execution-mode, risk, authority-class, tool-class, and
provider restrictions. It caps the returned candidate set at 50. Discovery is
exact structured matching, not semantic or provider-prose search.

`ToolDiscoveryResult` records the immutable registry digest, ordered candidates,
deterministic match/ineligibility reasons, bounded rejections, selected and
loaded identities, and registered/considered/matched/selected/loaded counts. A
canonical `no_match` result is returned when no available eligible candidate
exists. It does not invent a tool or fall back to shell execution.

## Registry And Ordering

Registration is explicit through `ToolRegistry`; it does not scan directories,
import modules, query a network, or accept provider-created tools. Construction
validates the compact descriptor schema, canonical-serializes deeply detached
descriptor records, sorts by canonical identity, and stores them as immutable
tuple content. Every authoritative boundary revalidates that content and derives
the SHA-256 digest from the exact records used by discovery, selection, and
loading. The content and digest therefore cannot be replaced as independent
slots; Python privacy, frozen dataclasses, and slotted attributes are not treated
as integrity boundaries. Public snapshots and descriptor lookups reconstruct
disposable views, so retained caller references or mutation of exposed
descriptors cannot alter trusted state. Duplicate tool IDs are rejected even
when versions differ.
CORE-04 deliberately supports one canonical version per stable tool ID;
version coexistence policy is later scope.

Every immutable descriptor is considered. A candidate must contain every
required capability as an exact string. Matching candidates are ordered by:

1. available and eligible before unavailable/ineligible;
2. fewest additional capabilities;
3. configured numeric preference rank;
4. local, connector, MCP, then provider-native tool class;
5. stable tool ID, then version.

The request limit is applied only after this ordering. Selection is a separate
registry operation. The registry recomputes discovery from its snapshot before
accepting selected IDs, so a caller or provider cannot promote a hidden,
unavailable, ineligible, or mutated candidate. Selection validates syntax,
duplicates, and discovered/selectable membership item by item, rejecting at the
first invalid item. It consumes at most the request maximum plus one iterable
item before rejecting overflow, including for large or infinite caller-provided
iterables.

## Deferred Loading

`ToolDefinitionLoader` accepts only a verified discovery result with explicit
selected IDs. Descriptor JSON Schema and runtime validation share the same
bounded normalized-relative-reference rules: no prohibited C0 control
character, empty, absolute, URL, backslash/mixed-separator, dot-segment,
traversal, or overlength reference is accepted. The runtime's existing explicit
tab, newline, and carriage-return semantics remain unchanged. Schema lookaheads
scan the entire reference including LF, and dot-segment termination uses an
explicit no-character-remains assertion rather than newline-sensitive `$`
behavior. For each selected ID the loader resolves the validated reference
beneath one trusted definition root, follows resolved-path containment
(including symlinks), reads bounded JSON, validates the fixed canonical
definition schema and a bounded local JSON Schema subset, and checks tool ID,
version, capability, class, risk, and authority identity against the descriptor.
Missing, malformed, traversing, external-reference, or identity-drifted
definitions fail closed.

Non-selected definition files are not read and non-selected schemas are not
parsed. Loaded definitions expose immutable data plus an opaque `adapter_id`;
they contain no callable, import path, shell command, or execute method. Adapter
resolution, invocation, and authority checks remain separate existing runtime
responsibilities.

## State And Authority

The lifecycle is distinct and monotonic:

`REGISTERED -> AVAILABLE -> ELIGIBLE -> SELECTED -> LOADED`

Registration does not prove availability. Availability does not prove policy
eligibility. A candidate is not selected; a selected descriptor is not loaded;
and a loaded definition is not authorized or executed. Declared
`authority_class` is a requirement to preserve, never an authority grant.

Discovery/loading cannot create or resolve Approval, complete Reviewer work,
continue or retry a job, clear recovery hold, authorize controlled write, invoke
Git, deploy, or let a provider choose policy. Existing job, approval, review,
continuation, controlled-write, Git, and deployment boundaries remain
authoritative.

Discovery evidence is intentionally ephemeral in CORE-04 because it does not
change job or authority state. The immutable `ToolDiscoveryResult` and
`ToolLoadResult` are the runtime/test evidence. A later execution integration
may attach their canonical dictionaries to its existing execution artifact;
CORE-04 does not create a competing persistence store or CORE-09 cache policy.
