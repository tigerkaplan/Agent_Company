# Obsidian Integration

Obsidian is an optional human-facing interface for the provider-neutral LLM Wiki. Agent Company does not require Obsidian to read, query, ingest, lint, or maintain knowledge.

## Open The Wiki As A Vault

1. In Obsidian, choose **Open folder as vault**.
2. Select the repository's `shared/knowledge/` directory itself, not the repository root and not a copied directory.
3. Open `index.md` first and use it as the primary knowledge map.

Opening the existing directory avoids moving files, duplicating knowledge, or creating a second source of truth.

## Canonical And UI-Only State

- `shared/knowledge/` is the canonical knowledge root.
- Markdown content, relative links, source provenance, `index.md`, and `log.md` remain canonical outside Obsidian.
- Obsidian panes, bookmarks, graph filters, recent files, and workspace layout are UI-only convenience state.
- A local `.obsidian/` directory, if Obsidian creates one, must remain local and uncommitted and must not become required Agent Company state. Do not add plugins, community-plugin dependencies, themes, or large workspace state to the canonical knowledge tree.

Agents must continue to operate directly on standard Markdown and must never require Obsidian APIs, settings, caches, backlinks, or graph data.

## Index-First Use

Start navigation from `index.md`. Its relative Markdown links and descriptions define what the wiki knows and which pages should be opened. Backlinks and graph view may help humans discover relationships, but they do not replace the index or establish canonical truth.

## Backlinks And Graph View

Obsidian can derive backlinks and graph relationships from normal relative Markdown links. Humans may use these views to:

- find pages that cite the same concept or source card;
- notice isolated pages that may be missing index entries or cross-references;
- explore related concepts before a manual QUERY or LINT;
- identify possible duplicates or weakly connected topics for review.

Graph proximity and backlink counts are navigation signals only. They are not evidence of correctness, importance, authority, or consensus.

## Safe Naming And Linking

- Prefer lowercase kebab-case filenames such as `agent-memory.md`.
- Keep filenames stable and avoid duplicate basenames across wiki categories.
- Use descriptive Markdown headings for human-readable titles.
- Use relative Markdown links for canonical references, provenance, index entries, and machine-readable navigation.
- Obsidian-style wikilinks may be added only as optional supplementary navigation when they do not replace or obscure a canonical relative Markdown link.
- Do not rely on wikilink aliases, embeds, block references, Obsidian URLs, or plugin syntax for required meaning.
- Keep links valid in ordinary Markdown readers and repository tooling.
