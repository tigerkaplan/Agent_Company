# Brightshore Cleaning Blockers

## Active Blockers

### Local App Live Setup Pending

Status: active.

Evidence: Local App 25N handoff and verification say controlled live owner use is ready only after actual owner setup.

Required action: owner confirmation of clean live profile, actual supplier/contact/address/bank settings, terms/due date review, first document review, and separate-device backup routine.

### Broken Root Git Metadata

Status: active.

Evidence: `git status` at project root failed with "not a git repository" despite a `.git` directory being present.

Required action: separate approved Git recovery task.

### Broken Local App Git Metadata

Status: active.

Evidence: `git status` in `02_LOCAL_APP/17_CODE_LOCAL_APP` failed with "not a git repository" despite a `.git` directory being present.

Required action: separate approved Git recovery task.

### Website Authority Conflict

Status: active.

Evidence: Website docs reference `01_WEBSITE/cleaning-business-service-website-git`, but inspection found no usable package/Git repository there. `01_WEBSITE/06_CODE` contains usable Git evidence and current files.

Required action: later Website authority confirmation.

## Not Blockers For This Onboarding Package

- Runtime artifacts exist but must not be deleted or moved during onboarding.
- Website `.gitignore` is modified but requires read-only diff review before interpretation.
