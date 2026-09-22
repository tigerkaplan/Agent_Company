# Google Drive Connector Contract

## Purpose

Provide a provider-neutral contract for reading, searching, creating, and updating approved files or documents while keeping document writes approval-aware.

This contract defers to `../../CONSTITUTION.md` and `../../AGENTS.md`.

## Supported Read Operations

- Search approved files by name, folder, owner, type, date, or metadata.
- Read approved file metadata.
- Read approved document or file content in a supported text form.
- Retrieve revision or folder context when needed and approved.

## Supported Write/Action Operations

- Create documents from approved content.
- Update documents or file metadata with appropriate approval.
- Move, rename, share, delete, or change permissions only if a future implementation has explicit approval for that action.

## Input Contract

- Operation type: search, read, create, update, or approved action.
- Approved drive, folder, file id, path, or query.
- Content, patch, metadata, or output format requested.
- Scope limits such as folder boundary, file type, or date range.
- Approval evidence for create, update, permission, sharing, move, or delete actions.

## Output Contract

- Operation status and timestamp.
- File list, metadata, or extracted content for read operations.
- Created or updated document reference for approved write operations.
- Applied changes, skipped changes, and review notes.
- Errors, missing permissions, redactions, or unsupported formats.

## Authentication Expectation

Future implementations must use approved delegated authentication and least-privilege scopes. Secrets, tokens, and credentials must not be stored in this contract directory or committed to the repository.

## Approval Boundaries

- Creating or updating documents requires appropriate approval.
- Sharing, permission changes, deletion, moving, or external publication require explicit approval.
- Sensitive, legal, financial, personal, or contractual documents should be escalated for review.

## Error/Fallback Behavior

- If a file cannot be accessed, report the missing permission or unavailable source.
- If write approval is absent, return proposed content or a patch for review instead of applying it.
- If a format cannot be parsed, report the unsupported format and offer a safe manual fallback.

## Data Retention/Privacy Expectations

- Retain only the minimum file content required for the approved task.
- Do not store secrets, raw drive dumps, unrelated folders, or unnecessary personal data.
- Keep operational file state separate from long-term knowledge.

## Intended Agents/Skills

- Communications Agent: `skills/communications/meeting-notes`
- Sales Agent: `skills/sales/proposal-builder`
- Marketing Agent: `skills/marketing/marketing-monday`, `skills/marketing/competitor-analysis`
- Operations Agent: `skills/operations/report-builder`, `skills/operations/sop-builder`
- Knowledge Manager Agent: shared knowledge skills when approved source documents are supplied
