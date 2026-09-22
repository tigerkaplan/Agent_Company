# Google Calendar Connector Contract

## Purpose

Provide a provider-neutral contract for reading calendar events and creating, updating, or cancelling events only through approval-aware actions.

This contract defers to `../../CONSTITUTION.md` and `../../AGENTS.md`.

## Supported Read Operations

- Read approved calendars, event metadata, and event details.
- Search events by date range, attendee, title, location, status, or calendar.
- Retrieve availability or schedule context when approved.

## Supported Write/Action Operations

- Create calendar events with appropriate approval.
- Update event time, attendees, details, reminders, or location with appropriate approval.
- Cancel or delete events only with explicit approval.
- Send calendar invitations or updates only when approved.

## Input Contract

- Operation type: read, search, availability, create, update, cancel, or approved action.
- Approved calendar identifier, date range, event id, or query.
- Event fields for proposed create or update operations.
- Attendee list, notification preference, and timezone when relevant.
- Approval evidence for create, update, cancel, delete, or invitation actions.

## Output Contract

- Operation status and timestamp.
- Event list, event detail, or availability summary for read operations.
- Proposed event draft when approval is absent.
- Created, updated, or cancelled event reference for approved actions.
- Errors, conflicts, missing permissions, or skipped notifications.

## Authentication Expectation

Future implementations must use approved delegated authentication and least-privilege calendar scopes. Secrets, tokens, and credentials must not be stored in this contract directory or committed to the repository.

## Approval Boundaries

- Creating, updating, cancelling, deleting, or sending invitations is externally consequential and approval-aware.
- Changes involving customers, vendors, interviews, deadlines, paid work, or sensitive meetings should be escalated for human review.
- Do not infer availability or attendance when calendar data is incomplete.

## Error/Fallback Behavior

- If calendar access is unavailable, report the limitation and do not claim schedule state.
- If approval is absent, return an event draft or proposed change instead of applying it.
- If a scheduling conflict appears, report the conflict and request review.

## Data Retention/Privacy Expectations

- Retain only the minimum event details needed for the approved task.
- Do not store secrets, full calendar dumps, unrelated attendees, or unnecessary personal data.
- Keep operational schedule state separate from long-term knowledge.

## Intended Agents/Skills

- Communications Agent: `skills/communications/meeting-notes`
- Sales Agent: `skills/sales/speed-to-lead`, `skills/sales/follow-up`
- Operations Agent: `skills/operations/report-builder`, `skills/operations/sop-builder`
- Project Manager Agent: workflow coordination and handoff planning
