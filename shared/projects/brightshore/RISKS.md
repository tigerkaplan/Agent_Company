# Brightshore Cleaning Risks

## High Risks

- Broken root and Local App Git metadata prevents reliable repository status/history for those areas.
- Treating stale documentation as current truth could route future work to obsolete paths.
- Treating automated Local App verification as owner live setup would overstate readiness.

## Medium Risks

- Website authority is provisional and conflicts with current documentation.
- Website `.gitignore` is modified and may represent intentional work or accidental drift.
- Runtime/generated artifacts are present inside project folders and could be accidentally packaged or mistaken for canonical source.
- Local App has live-use-sensitive settings for supplier identity, contact details, bank details, due dates, invoice issuance, delivery, and backup.

## Low Risks

- Marketing and Business Operations were not deeply audited in this first state package.
- Prior memory can help orient future work but must not override current repository evidence or human confirmation.

## Mitigations

- Keep project-state claims labelled as confirmed, provisional, or inferred.
- Require approval before Git repair, cleanup, deployment, external communication, or production data work.
- Use current routing files before broad documentation scans.
- Keep Website authority provisional until resolved.
