# Thesis defense demo script

Step-by-step demo flow.

---

## Preparation

1. **Neo4j Desktop** — DBMS running, GDS plugin enabled
2. **Clear graph** — `codegraph rebuild` on demo project (there is no `doctor --reset`; rebuild clears via `clear_database`)
3. **MCP** — `codegraph install`; restart Claude Desktop
4. Optional: pre-index Flask to save time:

```bash
codegraph init https://github.com/pallets/flask
codegraph rebuild
```

---

## Act 1: Visualizer (human exploration)

```bash
codegraph visualize
```

1. Browser → http://localhost:8474
2. If empty: paste `https://github.com/pallets/flask` → **Index Repository**
3. Wait for WebSocket `rebuild_complete`
4. Explore force graph — zoom, pan, node inspect
5. Query panel: **"How does routing work?"**
6. Show ranked sidebar + highlighted paths
7. Click node → source snippet / file panel

**Talking point:** Same PPR core as agents; UI is explainability for humans.

---

## Act 2: MCP (AI collaboration)

1. Open Claude Desktop (MCP connected)
2. Prompt:

> I'm working on Flask routing. Use your CodeGraph tools to find relevant context and explain how I would add a new route.

3. Show tool call: `get_relevant_context`
4. Compare scores/files to visualizer results from Act 1

**Talking point:** Structural ranking, not embeddings; consistent scores across interfaces.

---

## Act 3: CLI (developer speed)

```bash
codegraph init    # or skip if configured
codegraph explain "How does routing work?"
codegraph analyze deps Blueprint --direction downstream
```

**Talking point:** Same pipeline, three surfaces — MCP, UI, terminal.

---

## Fallbacks

| Problem | Action |
|---------|--------|
| Empty graph | `codegraph rebuild` |
| MCP missing | `codegraph install` + restart IDE |
| GDS error | Neo4j Desktop → Plugins |
| Slow clone | Pre-clone under `projects/` |

---

## Assets for slides

Thesis screenshots: `thesis/assets/gui_*.png` (ranked results, seeds, graph inspect).
