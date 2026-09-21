# Brightshore Cleaning Active File Map

## Root

- `AGENTS.md`: current routing authority for project areas.
- `README.md`: historical/root overview; contains stale path references and must not override routing evidence.

## Global

- `00_GLOBAL/`: shared project rules and business context.
- `00_GLOBAL/02_HANDOFF.md`: global handoff, not read by default.
- `00_GLOBAL/02_TODO.md`: global TODO, not read by default.

## Local App

- `02_LOCAL_APP/AGENTS.md`: Local App routing authority.
- `02_LOCAL_APP/README.md`: Local App folder overview.
- `02_LOCAL_APP/17_CODE_LOCAL_APP/`: primary Local App implementation authority.
- `02_LOCAL_APP/17_CODE_LOCAL_APP/package.json`: Local App package and scripts.
- `02_LOCAL_APP/17_CODE_LOCAL_APP/02_HANDOFF.md`: Local App implementation evidence to inspect; stale completion or readiness claims must not override the human-confirmed active-development status.
- `02_LOCAL_APP/17_CODE_LOCAL_APP/02_TODO.md`: Local App task evidence to inspect when determining the actual next development task.
- `02_LOCAL_APP/17_CODE_LOCAL_APP/ACTIVE_CODE_RULES.md`: implementation constraints.
- `02_LOCAL_APP/17_CODE_LOCAL_APP/BACKUP_AND_EXPORT_RULES.md`: live setup, backup, restore, and export rules.
- `02_LOCAL_APP/17_CODE_LOCAL_APP/electron/`: Electron main/preload/database/recovery implementation.
- `02_LOCAL_APP/17_CODE_LOCAL_APP/app/`: Next app routes.
- `02_LOCAL_APP/17_CODE_LOCAL_APP/components/`: UI components.
- `02_LOCAL_APP/17_CODE_LOCAL_APP/lib/`: shared runtime logic and schema.
- `02_LOCAL_APP/17_CODE_LOCAL_APP/tests/`: test suite.

## Website

- `01_WEBSITE/AGENTS.md`: Website routing authority.
- `01_WEBSITE/00_CONTROL/`: Website controls and handoff.
- `01_WEBSITE/06_CODE/`: provisional Website implementation authority because it has usable Git evidence and current files.
- `01_WEBSITE/06_CODE/package.json`: provisional Website package and scripts.
- `01_WEBSITE/06_CODE/.gitignore`: modified; requires later read-only diff review.
- `01_WEBSITE/cleaning-business-service-website-git/`: referenced by docs but not confirmed as usable in this checkout.

## Marketing

- `03_MARKETING/AGENTS.md`: Marketing routing authority.
- `03_MARKETING/`: active project area, not deeply audited in this pass.

## Business Operations

- `04_BUSINESS_OPERATIONS/AGENTS.md`: Business Operations routing authority.
- `04_BUSINESS_OPERATIONS/`: active project area, not deeply audited in this pass.

## Non-Canonical Generated/Runtime Areas

- `.next`
- `out`
- `.25n-runtime`
- `.25m-runtime`
- `.env.local`
- logs
- runtime/export data
