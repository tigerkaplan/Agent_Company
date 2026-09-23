# GitHub Connector

This directory defines the canonical connector contract for GitHub-like repository hosting access.

See `CONTRACT.md` for the provider-neutral contract. This directory remains documentation only. Phase 6J implements a narrow local push and GitHub CLI pull-request creation gate under `runtime/git/`; it does not add credentials, an API client, webhook listener, merge authority, or repository-writing implementation to this connector directory.
