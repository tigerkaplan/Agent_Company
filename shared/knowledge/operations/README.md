# Knowledge Operations

This directory defines provider-neutral operating contracts for the LLM Wiki.

- `ingest/`: integrate new source material into source cards and existing wiki knowledge.
- `query/`: retrieve the minimum relevant knowledge for a task.
- `lint/`: report quality, consistency, provenance, and navigation problems.

These are specifications only. Phase 3A includes no executable commands, provider-specific skills, embeddings, vector database, RAG, or semantic search.

All operations follow `../SCHEMA.md`, update `../log.md` as specified, and preserve the operational-state boundary described in `../README.md`.

