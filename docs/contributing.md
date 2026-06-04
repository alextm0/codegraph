# Contributing

## For AI agents

1. Read [README.md](README.md) doc map and [DECISIONS.md](../DECISIONS.md)
2. Follow [guides/development.md](guides/development.md)
3. Update docs in the same change as code ([UPDATING_DOCS.md](UPDATING_DOCS.md))

## For humans

- **Style:** type hints, docstrings on public APIs, frozen dataclasses in parser
- **Tests:** `python -m pytest tests/unit/ -q` before PR; full suite when Neo4j available
- **Decisions:** propose new entries in `DECISIONS.md` for architectural changes

## What we are not accepting without discussion

- Third MCP tool (DEC-007)
- Password in `config.yaml` (DEC-010)
- PPR default changes without evaluation numbers (DEC-001)

## Reference project

CodeGraphContext docs under `docs/CodeGraphContext-Docs-From-Github/` — compare only; implement against this repo’s docs and code.

## Thesis contributors

Keep `docs/thesis/evaluation.md` aligned with `thesis/chapters/chapter5_evaluation_results.tex`.
