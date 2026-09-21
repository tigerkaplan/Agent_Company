# Knowledge Schema

This schema is Markdown-first and provider-neutral. Use relative Markdown links so the knowledge tree remains portable and compatible with future local Markdown tools.

## Naming And Linking

- Prefer stable lowercase kebab-case filenames and descriptive Markdown headings.
- Avoid duplicate basenames across wiki categories so human-facing tools cannot resolve a page ambiguously.
- Use relative Markdown links for canonical index entries, provenance, source relationships, and machine-readable references.
- Standard Markdown links must carry all required meaning and remain usable without Obsidian.
- Obsidian-style wikilinks are optional supplementary navigation only. Do not use them as the sole canonical reference or require them for an agent workflow.
- Backlinks and graph relationships may support human discovery, but they do not establish authority, provenance, or truth.

## Raw Material

Raw material lives under `raw/` in the category that best matches its original form. Preserve the original content and stable filename. If a corrected or newer source arrives, add it as a new item rather than overwriting the earlier item.

## Source Cards

Source cards live under `sources/` and should contain only fields relevant to the source:

- stable source identifier;
- title and source type;
- relative link to raw material, when stored locally;
- original location or repository reference;
- author, publisher, and publication or capture date when known;
- access, licence, or usage constraints when known;
- concise summary;
- important claims and supporting locations;
- uncertainty, conflicts, or known limitations;
- related wiki pages.

Unknown metadata must be marked unknown or omitted, never invented.

## Wiki Pages

Wiki pages live under the relevant `wiki/` category and should include, when applicable:

- title and scope;
- concise synthesis;
- claims labelled as confirmed, inferred, disputed, provisional, or unknown where status matters;
- links to supporting source cards;
- conflicts, limitations, and stale-knowledge warnings;
- links to related wiki pages;
- last evidence review date when known.

Wiki pages synthesize durable knowledge. They must not store current project tasks, transient blockers, session state, or approval status from `shared/projects/`.

## Index Entries

Each indexed page should have a relative link and a one-line description sufficient to decide whether the page is relevant before opening it.

## Operation Log Entries

Append one concise entry per INGEST, QUERY, or LINT operation with:

- date or timestamp;
- operation type;
- scope;
- inputs consulted;
- pages created or changed, if any;
- outcome, gaps, or reported conflicts.

Do not copy raw prompts, chats, source contents, secrets, or operational project state into the log.
