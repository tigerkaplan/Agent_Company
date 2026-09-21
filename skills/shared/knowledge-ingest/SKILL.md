# Skill: Knowledge Ingest

## Purpose

Integrate source material into the provider-neutral LLM Wiki while preserving raw evidence, provenance, uncertainty, and the boundary from operational project state.

## Inputs

- Source material or a stable reference to it.
- Known provenance, access constraints, and source limitations.
- Requested ingest scope.
- Existing knowledge index, source cards, and relevant wiki pages.

## Outputs

- Preserved raw source location or stable source reference.
- New or updated source card when needed.
- Updated existing wiki pages, or a justified new page when no suitable page exists.
- Updated knowledge index when page structure changes.
- Concise INGEST record appended to the knowledge operation log.

## Constraints

- Follow `../../../CONSTITUTION.md`, `../../../AGENTS.md`, `../../../shared/knowledge/README.md`, and `../../../shared/knowledge/SCHEMA.md`.
- Execute the canonical `../../../shared/knowledge/operations/ingest/OPERATION.md` under its `../../../shared/knowledge/operations/ingest/POLICY.md`.
- Never modify or overwrite raw source material.
- Never copy an entire raw source into a wiki page.
- Preserve provenance, uncertainty, conflicts, and known limitations.
- Do not duplicate current project tasks, handoffs, blockers, risks, approvals, or workflow status from `../../../shared/projects/`.
- Do not use provider-specific copies, embeddings, RAG, vector databases, semantic search, or unimplemented tooling.

## Procedure

1. Read the canonical INGEST operation and policy.
2. Read the relevant raw source and known provenance.
3. Read the knowledge index and select the minimum relevant existing source cards and wiki pages.
4. Create or update a source card when needed.
5. Update an existing wiki page before considering a new page.
6. Create a new concept or topic page only when the material is durable, distinct, and not adequately represented elsewhere.
7. Update `index.md` only when knowledge structure changes.
8. Append a concise INGEST record to `log.md`.

## Checks

- Raw source material is unchanged.
- Important claims remain traceable to provenance or are labelled as inference.
- No whole raw source was copied into a wiki page.
- No avoidable duplicate topic or page was created.
- Index changes match structural wiki changes.
- Operational project state was not duplicated.
- The operation log entry is concise and contains no raw chat or source dump.

