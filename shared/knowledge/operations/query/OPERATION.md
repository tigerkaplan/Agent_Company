# QUERY Operation

## Purpose

Retrieve the minimum relevant long-term knowledge needed for a task without loading the full knowledge tree.

## Inputs

- A question or task.
- `../../index.md`.
- Relevant wiki pages selected from the index.
- Source cards or raw material only when verification is needed.

## Procedure

1. Read `../../index.md` first.
2. Select only wiki pages whose index descriptions match the task.
3. Read the minimum relevant sections of those pages.
4. Consult linked source cards when provenance, freshness, or conflicting claims matter.
5. Consult raw material only when wiki pages and source cards are insufficient.
6. Return a concise answer that distinguishes confirmed knowledge, inference, uncertainty, conflicts, and gaps.
7. Append a concise QUERY record to `../../log.md` without copying the raw query or sensitive content.
8. Recommend a separate INGEST operation when durable new analysis would improve the wiki.

## Completion Checks

- Retrieval started with the index.
- Unrelated pages and operational project state were not loaded.
- Claims retain source provenance and uncertainty.
- QUERY did not silently modify wiki knowledge.

