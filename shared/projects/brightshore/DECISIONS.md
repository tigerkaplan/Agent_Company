# Brightshore Cleaning Decisions

## Human-Confirmed Decisions

- Onboard the entire CleaningBusiness project as Brightshore Cleaning.
- Treat Local App, Website, Marketing, Business Operations, and Global as separate project areas.
- Use `Brightshore Cleaning` as the canonical project/business name.
- Treat `02_LOCAL_APP/17_CODE_LOCAL_APP` as the current primary Local App implementation authority.
- Treat the Local App as under active development and not finished; stale completion or readiness wording does not override this human-confirmed state.
- Do not assume owner live setup is the immediate next development priority.
- Do not repair broken root or Local App Git metadata during onboarding.
- Record broken Git metadata as a blocker/risk and handle Git recovery as a separate approved task.
- Provisionally treat `01_WEBSITE/06_CODE` as the current evidence-backed working Website repository.
- Do not assume the modified Website `.gitignore` is intentional.
- Treat Local App owner live setup as pending unless separately confirmed.
- Do not treat runtime/generated artifacts as canonical source or release artifacts.
- Do not delete or move runtime/generated artifacts during onboarding.

## Evidence-Backed Decisions

- Local App runtime is Electron.
- Tauri is not part of the active Local App package.
- Local App backup/restore rules are documented in `BACKUP_AND_EXPORT_RULES.md`.
- Historical Local App 25N verification evidence reports PASS but does not establish development completion or owner live setup.
- Current canonical state does not identify the actual next Local App development task; minimum relevant source inspection is required to determine it.

## Deferred Decisions

- Website authority confirmation.
- Git metadata recovery approach.
- Runtime artifact handling policy.
- Website production launch readiness.
- Online payment provider need/selection.
- Review evidence storage.
- Automation and analytics scope.
