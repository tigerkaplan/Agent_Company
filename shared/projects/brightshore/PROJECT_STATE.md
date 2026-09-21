# Brightshore Cleaning Project State

## Confirmed State

- Project root: `E:\00_CleaningProject\CleaningBusiness`.
- Canonical name: Brightshore Cleaning.
- Agent Company should onboard the entire CleaningBusiness project as Brightshore Cleaning.
- Onboarding was read-only, with project-state creation confined to Agent Company; the Brightshore source repository was not modified.
- Project areas are Global, Local App, Website, Marketing, and Business Operations.
- Primary Local App implementation authority is `02_LOCAL_APP/17_CODE_LOCAL_APP`.
- The Local App remains under active development and is not finished.
- Previous automated verification results are historical evidence only; they do not establish that Local App development is complete or production-ready.
- Local App owner live setup is pending unless separately confirmed.
- Owner live setup is a pending live-use gate, not a confirmed immediate development priority.
- Root Git metadata and Local App Git metadata are broken or unusable for normal Git status/history.
- Git repair is not part of onboarding and requires a separate approved task.
- Runtime/generated artifacts must not be treated as canonical source or release artifacts.

## Provisional State

- Website authority is provisionally `01_WEBSITE/06_CODE` because it contains usable Git metadata and current files.
- The Website authority must be confirmed later because Website documentation also references `01_WEBSITE/cleaning-business-service-website-git`, which appeared empty/not a usable Git repository during inspection.

## Inferred State

- Website appears to have launch gates around domain, contact details, legal/privacy wording, production intake, and indexing.
- Marketing and Business Operations are active project areas but were not deeply audited in this pass.

## Current Status

Overall onboarding status: state package created from evidence and human clarification.

Local App status: active development; not complete and not confirmed production-ready.

Next Local App development task: unknown from current canonical state. Targeted inspection of the minimum relevant files in the confirmed Local App authority is required before selecting it.

## Non-Canonical Artifacts

The following must not be treated as canonical source or release artifacts:

- `.next`
- `out`
- `.25n-runtime`
- `.25m-runtime`
- `.env.local`
- logs
- local runtime data
- local export data

Do not delete or move them during onboarding.
