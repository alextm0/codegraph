# Quickstart

## 1. Build graph

```bash
codegraph rebuild
codegraph stats
```

## 2. Query

```bash
codegraph query "add rate limiting to login"
codegraph query "fix token validation" --entity AuthService --entity validate_token
codegraph query "refactor sessions" --compact
```

## 3. Explain

```bash
codegraph explain "add rate limiting to login"
```

## 4. Dependencies

```bash
codegraph analyze deps AuthService --direction upstream
codegraph analyze deps AuthService --direction downstream --depth 2
```

## 5. Visualizer

```bash
codegraph visualize
```

Opens http://localhost:8474

## 6. Agent usage

After `codegraph install`, agents should call **`get_relevant_context`** before editing code.

See [mcp-setup.md](mcp-setup.md) and [../guides/agent-workflows.md](../guides/agent-workflows.md).

Next: [../guides/indexing.md](../guides/indexing.md), [../reference/cli.md](../reference/cli.md)
