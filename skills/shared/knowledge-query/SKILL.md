# Skill: Knowledge Query

## Purpose

Retrieve the minimum relevant long-term knowledge for a task while preserving provenance, uncertainty, and separation from current project state.

## Inputs

- Question or task.
- `../../../shared/knowledge/index.md`.
- Relevant wiki pages selected from the index.
- Source cards or raw material only when verification requires them.

## Outputs

- Concise answer based on the minimum relevant knowledge.
- Provenance for material claims.
- Confirmed knowledge, inference, uncertainty, conflicts, and gaps kept distinguishable.
- Recommendation for a later INGEST operation when durable new synthesis would improve the wiki.

## Constraints

- Follow `../../../CONSTITUTION.md`, `../../../AGENTS.md`, `../../../shared/knowledge/README.md`, and `../../../shared/knowledge/SCHEMA.md`.
- Execute the canonical `../../../shared/knowledge/operations/query/OPERATION.md` under its `../../../shared/knowledge/operations/query/POLICY.md`.
- Read `../../../shared/knowledge/index.md` first.
- Do not treat wiki knowledge as current project state or current project state as wiki knowledge.
- Do not mutate raw material, source cards, wiki pages, or the index during QUERY by default.
- Do not silently write durable new synthesis; recommend a later INGEST operation.
- Do not use provider-specific copies, embeddings, RAG, vector databases, semantic search, or unimplemented tooling.

## Procedure

1. Read the canonical QUERY operation and policy.
2. Read `../../../shared/knowledge/index.md` first.
3. Identify the minimum relevant wiki pages from their index descriptions.
4. Read only those pages unless a material gap, conflict, or verification need requires more context.
5. Consult source cards and then raw material only when necessary.
6. Return a concise answer with provenance and uncertainty preserved.
7. Append only the concise QUERY operation record required by the canonical operation; do not change knowledge content.
8. Recommend later INGEST when the query produces valuable durable synthesis.

## Checks

- Retrieval started with the index.
- Only minimum relevant pages were loaded.
- Provenance, uncertainty, conflicts, and data gaps remain visible.
- Wiki knowledge and operational project state remain distinguishable.
- No knowledge content was mutated during the query.
- Any proposed durable synthesis is deferred to INGEST.

