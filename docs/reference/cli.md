# CLI reference

Entry point: `codegraph` (Typer). Global option on all commands:

| Option | Default | Description |
|--------|---------|-------------|
| `--config` | `config.yaml` | Path to config file (resolved from CWD if missing) |

---

## Lifecycle

### `init [target]`

Interactive wizard. Optional `target`: local path or GitHub URL.

Creates `config.yaml`, `.env` (`NEO4J_PASSWORD`), optional clone under `projects/`.

### `install`

Registers MCP server in Claude Code (`.mcp.json`), Claude Desktop, or Gemini CLI.

### `rebuild`

Clear graph + full re-parse + write. Primary indexing command.

### `status`

Project root, graph counts, last build time, MCP registration hints.

### `stats`

Node counts by label, relationship counts.

### `doctor`

Structured health checks: config, password, Neo4j, GDS, graph non-empty.

### `watch`

Filesystem watcher; incremental file updates.

### `serve [--config PATH]`

Start MCP stdio server. Sets `CODEGRAPH_CONFIG`.

---

## Retrieval

### `query TASK [options]`

Run PPR retrieval pipeline.

| Option | Description |
|--------|-------------|
| `--entity` / `-e` | Repeatable seed entity names |
| `--top-k` | Max results (0 = config default) |
| `--budget` | Token budget (0 = default) |
| `--compact` | Paths + scores only |
| `--json` | Machine-readable JSON |
| `--trace` | Structured retrieval trace JSON |
| `--viz` | Open visualizer after query |

### `explain TASK`

Show seed nodes and reasoning paths (default top 10 files).

| Option | Description |
|--------|-------------|
| `--top-k` / `-k` | Number of explained files |
| `--trace` | JSON trace |

---

## Analysis (`analyze` group)

### `analyze deps NAME`

| Option | Default | Values |
|--------|---------|--------|
| `--direction` / `-d` | `both` | `upstream`, `downstream`, `both` |
| `--depth` | `1` | `1` or `2` |
| `--viz` | off | Open visualizer |

- **upstream:** who calls / imports this entity
- **downstream:** what this entity calls / imports

### `analyze dead-code`

Lists unreachable functions (CLI only, not MCP).

---

## Visualizer

### `visualize`

| Option | Description |
|--------|-------------|
| `--port` / `-p` | Listen port (default 8474) |
| `--no-browser` | Do not open browser |
| `--dev` | API-only for Vite frontend dev |
| `--watch` | Enable file watching + live updates |

---

## Examples

```bash
codegraph rebuild
codegraph query "fix JWT expiry" -e TokenService -e validate_jwt
codegraph explain "fix JWT expiry" --top-k 5
codegraph analyze deps validate_jwt --direction upstream --depth 2
codegraph analyze dead-code
codegraph visualize --port 8474
codegraph serve --config ./config.yaml
```

Implementation: `src/codegraph/cli/main.py`, commands in `src/codegraph/cli/commands/`.
