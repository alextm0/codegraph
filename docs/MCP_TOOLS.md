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
| `include_explanations` | bool | Seed paths per result |

**Returns:** JSON with `summary`, `results[]` (entity, file, lines, score, `source_code`), optional `seeds[]`.

**Empty graph:** Auto-starts background index; retry after ~15–30s or run `codegraph rebuild`.

## `query_dependencies`

**When:** After confirming entity names via `get_relevant_context`. Impact analysis before refactors.

| Parameter | Type | Notes |
|-----------|------|-------|
| `entity_name` | string | Name or qualified name; partial match OK |
| `direction` | string | `upstream` \| `downstream` \| `both` |
| `depth` | int | `1` or `2` |

**Returns:** JSON with `results[]` (`qualified_name`, `name`, `label`, `file_path`, `relationship_type`).

## Agent workflow

```
get_relevant_context(task, entities?)
  → implement / answer
  → query_dependencies(entity, direction)   # if refactor or impact needed
```

## Registration

```bash
codegraph install
```

Writes `.mcp.json` (Claude Code), Claude Desktop `claude.json`, or Gemini `.gemini/settings.json`. Restart the IDE after install.

Server entry: `codegraph serve` with `CODEGRAPH_CONFIG` pointing at `config.yaml`.

See [reference/mcp.md](reference/mcp.md) for full schema and error payloads.
