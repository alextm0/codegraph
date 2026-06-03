# MCP tool reference

Server: FastMCP, stdio transport, name `codegraph`.  
Register: `codegraph install` → `codegraph serve`.

**Exactly two tools** (DEC-007). No stats, dead-code, or Cypher over MCP.

---

## `get_relevant_context`

**Purpose:** PPR-ranked source entities for a task. **Call first** for almost all coding work.

### Parameters

| Name | Type | Required | Notes |
|------|------|----------|-------|
| `task_description` | string | yes | Plain-English task |
| `mentioned_entities` | list[string] \| null | no | Exact symbol names; null if none |
| `current_file` | string \| null | no | **Deprecated — ignored** |
| `top_k` | int | yes | `0` → server default (30) |
| `token_budget` | int | yes | `0` → default (6000) |
| `include_explanations` | bool | yes | Adds seeds + path explanations |

### Success response (JSON string)

```json
{
  "summary": {
    "result_count": 12,
    "total_tokens": 4500,
    "token_budget": 6000,
    "visualizer_url": "http://localhost:8474"
  },
  "seeds": [
    { "qualified_name": "src/auth.py::AuthService", "source": "entity_match", "weight": 0.15 }
  ],
  "results": [
    {
      "entity_name": "AuthService",
      "entity_type": "Class",
      "qualified_name": "src/auth.py::AuthService",
      "file_path": "src/auth.py",
      "lines": [10, 85],
      "relevance_score": 0.0421,
      "token_count": 320,
      "source_code": "..."
    }
  ]
}
```

With `include_explanations=true`, each result may include an `explanation` object (seed path, contribution).

### Error / empty payloads

| Condition | Response |
|-----------|----------|
| Empty graph | `error` + auto-index message; retry after rebuild |
| Pipeline exception | `error`, `detail`, `hint: run codegraph doctor` |
| No results | `result_count: 0`, `hint: run codegraph rebuild` |

Implementation: `get_relevant_context_impl` in `src/codegraph/mcp/tools.py`.

---

## `query_dependencies`

**Purpose:** Structural neighbors (call/import graph). Use **after** confirming entity names.

### Parameters

| Name | Type | Notes |
|------|------|-------|
| `entity_name` | string | Short or qualified name; partial match |
| `direction` | string | `upstream` \| `downstream` \| `both` |
| `depth` | int | `1` or `2` |

### Success response

```json
{
  "result_count": 5,
  "results": [
    {
      "qualified_name": "src/api.py::handle_login",
      "name": "handle_login",
      "label": "Function",
      "file_path": "src/api.py",
      "relationship_type": "CALLS"
    }
  ]
}
```

### Errors

| Condition | Response |
|-----------|----------|
| Invalid direction | `error` + hint for valid values |
| Unknown entity | hint to use `get_relevant_context` first |
| Empty graph | same as context tool (background index) |

Implementation: `query_dependencies_impl` in `src/codegraph/mcp/tools.py`.

---

## Server lifecycle

- `ServerState`: driver, GDS, config, `project_root`, defaults (`mcp/server_config.py`)
- Lifespan opens/closes DB (`mcp/server.py`)
- System prompt for LLMs: `mcp/prompts.py`

Quick copy: [../MCP_TOOLS.md](../MCP_TOOLS.md).
