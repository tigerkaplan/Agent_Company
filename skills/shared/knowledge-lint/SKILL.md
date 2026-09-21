# Skill: Knowledge Lint

## Purpose

Inspect the LLM Wiki for quality, consistency, provenance, navigation, duplication, and knowledge gaps without silently rewriting knowledge.

## Inputs

- Requested lint scope.
- `../../../shared/knowledge/index.md`.
- Wiki pages, source cards, and raw references needed for the checks.
- Canonical LINT checks and policy.

## Outputs

- Findings grouped by severity.
- Affected files and supporting evidence.
- Recommended fixes.
- Explicit uncertainty and data gaps.
- Concise LINT record appended to the knowledge operation log.

## Constraints

- Follow `../../../CONSTITUTION.md`, `../../../AGENTS.md`, `../../../shared/knowledge/README.md`, and `../../../shared/knowledge/SCHEMA.md`.
- Execute `../../../shared/knowledge/operations/lint/OPERATION.md` under its `../../../shared/knowledge/operations/lint/POLICY.md` and apply `../../../shared/knowledge/operations/lint/CHECKS.md`.
- Do not silently rewrite disputed or contradictory facts.
- Do not mutate raw material, source cards, wiki pages, or the index during LINT.
- Mutate knowledge only in a separately approved remediation step.
- Do not use provider-specific copies, embeddings, RAG, vector databases, semantic search, or unimplemented tooling.

## Procedure

1. Read the canonical LINT operation, policy, and checks.
2. Define the minimum lint scope and read the knowledge index.
3. Check contradictions, stale claims, orphan pages, broken links, missing concepts, missing cross-references, duplicate topics, missing provenance, and data gaps.
4. Verify suspected findings against source cards or raw references when needed.
5. Group findings by severity and identify affected files and evidence.
6. Recommend scoped fixes without applying them.
7. Append only a concise LINT operation record to `log.md`.

## Checks

- Every required lint category was considered or marked not applicable.
- Findings identify severity, evidence, and affected files.
- Contradictions and disputed facts were reported without silent resolution.
- Recommended fixes are separate from findings.
- No knowledge content was mutated.
- Any remediation is deferred to a separately approved step.

