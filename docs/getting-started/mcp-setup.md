# MCP setup

CodeGraph runs as a **stdio MCP server**: `codegraph serve` with `CODEGRAPH_CONFIG` pointing at your `config.yaml`.

## Automated (recommended)

```bash
codegraph init
codegraph install
codegraph rebuild
```

`install` writes:

| Client | File |
|--------|------|
| Claude Code | Project `.mcp.json` |
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) |
| Gemini CLI | `.gemini/settings.json` |

**Restart the IDE** after install.

## Manual: Claude Desktop (macOS)

`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "codegraph": {
      "command": "codegraph",
      "args": ["serve", "--config", "/absolute/path/to/your/config.yaml"]
    }
  }
}
```

Use the same `command`/`args` if CodeGraph is only on PATH inside a venv (activate venv in wrapper script or use full path to venv `codegraph`).

## Manual: Cursor

1. Settings → MCP → Add server
2. Type: **command**
3. Command: `codegraph serve --config /path/to/config.yaml`

## Manual: Claude Code

Project `.mcp.json`:

```json
{
  "mcpServers": {
    "codegraph": {
      "command": "codegraph",
      "args": ["serve", "--config", "./config.yaml"]
    }
  }
}
```

## Server behavior

- **Lifespan:** Opens Neo4j driver + GDS on startup, closes on shutdown (`src/codegraph/mcp/server.py`).
- **Empty graph:** Tools trigger background indexing; retry after 15–30s or run `codegraph rebuild`.
- **Tools:** Only `get_relevant_context` and `query_dependencies` — see [../reference/mcp.md](../reference/mcp.md).

## Agent instructions

The server ships an LLM system prompt (`src/codegraph/mcp/prompts.py`) telling agents to call `get_relevant_context` first. Repo-level copy: [../guides/agent-workflows.md](../guides/agent-workflows.md).

## Verify

```bash
codegraph doctor
codegraph status    # shows MCP registration hints
```

From the agent: ask it to call `get_relevant_context` for a small task and confirm JSON with `results[]`.
