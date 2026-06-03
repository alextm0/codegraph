# Interactive visualizer

`codegraph visualize` serves a React + D3 force graph and REST/WebSocket API on **port 8474** (default).

---

## User mode

```bash
codegraph visualize
codegraph visualize --port 9000 --no-browser
codegraph query "task" --viz    # query then open browser
codegraph analyze deps Foo --viz
```

**Features (high level):**

- Force-directed graph of entities and edges
- Run queries from UI; PPR heat coloring
- Explain panel (seeds + paths) — mirrors `codegraph explain`
- Project tree, file panel, stats popover

**Backend:** `src/codegraph/visualizer/`  
**Frontend:** `frontend/` (Vite, React, TypeScript)

Built assets are served by the Python app; users do not need `npm` for normal use.

---

## Developer mode

```bash
cd frontend && npm install && npm run dev
codegraph visualize --dev
```

`--dev`: API only from Python; Vite dev server serves UI with HMR.

---

## Watch + live graph

```bash
codegraph visualize --watch
```

Combines file watcher with live graph refresh (same family as `codegraph watch`).

---

## MCP link

`get_relevant_context` returns `summary.visualizer_url` (default `http://localhost:8474`) so agents can point users to the UI for exploration.

---

## Key frontend modules

| Area | Path |
|------|------|
| Graph canvas | `frontend/src/components/graph/GraphCanvas.tsx` |
| Layout helpers | `frontend/src/components/graph/graphHelpers.ts` |
| Query hook | `frontend/src/hooks/useQuery.ts` |
| API client | `frontend/src/api/client.ts` |

Do not reimplement PPR in TypeScript — all ranking stays in Python core.

---

## HTTP API

Full endpoint list: [../reference/visualizer-api.md](../reference/visualizer-api.md).

WebSocket `/ws/status` broadcasts rebuild progress during UI indexing.
