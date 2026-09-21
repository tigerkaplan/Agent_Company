# Shared Knowledge

`shared/knowledge/` is the provider-neutral, local-first home for durable synthesized knowledge used by Agent Company.

## Boundaries

| Location | Responsibility |
| --- | --- |
| `../projects/` | Current operational project state, tasks, blockers, approvals, and handoffs. |
| `../../agents/*/MEMORY.md` | Agent-specific learned lessons and recurring execution patterns. |
| `../memory/` | Reserved for future cross-project company learning; it is not implemented in Phase 3A. |
| `./` | Long-term sources, provenance, and synthesized knowledge. |

Knowledge pages must not become mirrors of project TODOs, current status, session logs, or other operational state.

## Knowledge Flow

`raw/` -> `sources/` -> `wiki/`

- `raw/` preserves original source material without overwriting it.
- `sources/` holds processed source cards, summaries, and provenance.
- `wiki/` holds living synthesized Markdown knowledge that may evolve as evidence changes.
- `index.md` maps what the wiki currently knows and is always read first.
- `log.md` is the append-only history of INGEST, QUERY, and LINT operations.

## Retrieval

Read `index.md` first. Load only the relevant wiki pages, then consult source cards or raw material only when the task needs verification or the synthesis is insufficient.

## Current Scope

The knowledge core uses Markdown structure and provider-neutral operating contracts. It does not implement embeddings, vector databases, RAG, semantic search, deterministic tooling, or provider-specific knowledge skills.

Obsidian compatibility is optional and human-facing. The integration guide at `../../integrations/obsidian/README.md` does not change this directory's canonical status or make Obsidian required.

No existing project or external source is ingested by this foundation.

## Navigation

- Schema: `SCHEMA.md`
- Knowledge map: `index.md`
- Operation history: `log.md`
- Raw source policy: `raw/README.md`
- Source cards: `sources/README.md`
- Wiki pages: `wiki/README.md`
- Operations: `operations/README.md`
- Optional Obsidian interface: `../../integrations/obsidian/README.md`
