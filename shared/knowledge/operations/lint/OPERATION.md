# LINT Operation

## Purpose

Inspect knowledge quality and navigation without silently changing disputed or uncertain content.

## Inputs

- `../../index.md`.
- Wiki pages in the requested scope.
- Linked source cards and raw references needed to validate findings.
- `CHECKS.md`.

## Procedure

1. Define the smallest lint scope.
2. Read `../../index.md` and the indexed pages in scope.
3. Apply the checks in `CHECKS.md`.
4. Verify suspected problems against source cards or raw references when necessary.
5. Report findings with affected files, evidence, severity, and uncertainty.
6. Report knowledge gaps separately from contradictions or errors.
7. Do not rewrite disputed facts or silently repair content.
8. Append a concise LINT record to `../../log.md`.

## Completion Checks

- Findings are evidence-backed and scoped.
- Contradictions, stale claims, gaps, and broken navigation are distinguishable.
- No disputed knowledge was silently changed.
- Operational project state was not copied into the wiki.

