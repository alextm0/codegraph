# Roadmap

Planned work derived from `TODO.md` and architectural gaps vs CodeGraphContext. **Not committed dates** — check git issues/PRs for active work.

---

## Near term

- [x] **Cookbook** — [guides/cookbook.md](guides/cookbook.md)
- [ ] **Docs sync** — keep `docs/` aligned with each release tag

---

## Features

- [ ] **Multi-language parsing** — Java, TypeScript/JavaScript (CGC has patterns; needs extension or new decision for node labels)
- [ ] **Spring Boot** — framework-specific nodes/edges (CGC has SpringBean/SpringEndpoint; would be new schema decision)
- [ ] **Incremental indexing** — stronger than current `watch` (hash-based skip at scale)

---

## Non-goals (unless decision changes)

- Large MCP tool suite
- Portable `.cgc` bundles (unless explicitly designed)
- Embedding-based ranking as default
- Cypher execution from MCP

---

## Deployment

- [ ] Evaluate realistic deployment story (Docker, remote Neo4j) — CGC deployment docs in reference folder may inspire; not spec

---

## Documentation

- [x] Agent-oriented `docs/` tree (this folder)
- [x] Link docs from Cursor rules (`.cursor/rules/codegraph-docs.mdc`) + `AGENTS.md`

When completing an item, update this file and `TODO.md` at repo root.
