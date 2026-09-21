# INGEST Operation

## Purpose

Integrate new source material into the long-term knowledge system while preserving the original source and its provenance.

## Inputs

- Source material or a stable source reference.
- Known provenance and usage constraints.
- Relevant existing entries from `../../index.md`.
- Existing source cards and wiki pages selected through the index.

## Procedure

1. Read `../../index.md` first and identify the minimum relevant existing pages.
2. Determine whether the source is new, a new version, or already represented.
3. Store new raw material in `../../raw/` without overwriting an existing item.
4. Create or update the corresponding source card in `../../sources/` with provenance, summary, claims, and uncertainty.
5. Integrate durable knowledge into existing wiki pages where possible; create a new page only when no suitable page exists.
6. Preserve confirmed, inferred, disputed, provisional, and unknown status where relevant.
7. Update `../../index.md` for any added, renamed, moved, or removed wiki page.
8. Append a concise INGEST record to `../../log.md`.

## Completion Checks

- Raw material was not overwritten.
- Every synthesized claim can be traced to a source card or is labelled as inference.
- Operational project state was not copied into the wiki.
- Conflicts and uncertainty remain visible.
- Index and links reflect the resulting wiki pages.

