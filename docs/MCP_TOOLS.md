# MCP tools quick reference

CodeGraph exposes **exactly two** MCP tools. There is no graph stats, dead-code, or raw Cypher tool over MCP — use the CLI for those.

## `get_relevant_context`

**When:** Start of almost every coding task. Do not guess file locations.

| Parameter | Type | Notes |
|-----------|------|-------|
| `task_description` | string | Plain-English task |
| `mentioned_entities` | list \| null | Exact names user cited, e.g. `["AuthService"]` |
| `current_file` | string \| null | Legacy; **ignored** |
| `top_k` | int | `0` = default 30 |
| `token_budget` | int | `0` = default 6000 |
| `include_explanations` | bool | Default **true**; per-result reasoning paths |

**Returns:** JSON with `summary` (includes `last_indexed` freshness), `seeds[]` (provenance signal), `results[]` (entity, file, lines, score, `source_code`, optional `explanation`).

**Empty graph:** Auto-starts background index; retry after ~15–30s or run `codegraph rebuild`.

## `query_dependencies`

**When:** Known symbol lookup, inheritance, or impact analysis.

| Parameter | Type | Notes |
|-----------|------|-------|
| `entity_name` | string | Name, qualified name, or pattern (`symbol_search`) |
| `direction` | string | `upstream` \| `downstream` \| `both` |
| `depth` | int | `1` or `2` (dependencies mode) |
| `mode` | string | `dependencies` \| `symbol_search` \| `class_hierarchy` |

**Returns:** JSON with `mode`, `result_count`, `results[]`.

## Agent workflow

```
# Known symbol:
query_dependencies(entity, mode="symbol_search", ...)

# Vague task:
get_relevant_context(task, entities?)
  → implement / answer
  → query_dependencies(entity, mode="dependencies", direction=...)  # if impact needed
```

## Registration

```bash
codegraph install
```

Writes `.mcp.json` (Claude Code), Claude Desktop `claude.json`, or Gemini `.gemini/settings.json`. Restart the IDE after install.

Server entry: `codegraph serve` with `CODEGRAPH_CONFIG` pointing at `config.yaml`.

See [reference/mcp.md](reference/mcp.md) for full schema and error payloads.
