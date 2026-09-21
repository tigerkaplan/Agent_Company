# Brightshore Cleaning Project State

## Confirmed State

- Project root: `E:\00_CleaningProject\CleaningBusiness`.
- Canonical name: Brightshore Cleaning.
- Agent Company should onboard the entire CleaningBusiness project as Brightshore Cleaning.
- Project areas are Global, Local App, Website, Marketing, and Business Operations.
- Primary Local App implementation authority is `02_LOCAL_APP/17_CODE_LOCAL_APP`.
- Local App owner live setup is pending unless separately confirmed.
- Root Git metadata and Local App Git metadata are broken or unusable for normal Git status/history.
- Git repair is not part of onboarding and requires a separate approved task.
- Runtime/generated artifacts must not be treated as canonical source or release artifacts.

## Provisional State

- Website authority is provisionally `01_WEBSITE/06_CODE` because it contains usable Git metadata and current files.
- The Website authority must be confirmed later because Website documentation also references `01_WEBSITE/cleaning-business-service-website-git`, which appeared empty/not a usable Git repository during inspection.

## Inferred State

- The Local App appears to be in a post-MVP automated verification state, preparing for controlled live owner use after owner setup.
- Website appears to have launch gates around domain, contact details, legal/privacy wording, production intake, and indexing.
- Marketing and Business Operations are active project areas but were not deeply audited in this pass.

## Current Status

Overall onboarding status: state package created from evidence and human clarification.

Operational status: not yet ready to assume live production operation without owner confirmation of setup and Git authority decisions.

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
