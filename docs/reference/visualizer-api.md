# Visualizer HTTP API

FastAPI server started by `codegraph visualize`. Default base: **http://localhost:8474**

**Code:** `src/codegraph/visualizer/routes.py`, `query_service.py`, `app.py`

Requires: `pip install -e ".[visualizer]"`

---

## REST endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/init` | Clone URL or set path + background `rebuild` |
| `POST` | `/api/rebuild` | Rebuild current `project_root` |
| `POST` | `/api/query` | PPR retrieval + graph payload for UI |
| `GET` | `/api/health` | Status, git info, `project_history` |
| `GET` | `/api/stats` | Node/edge counts, top connected files, last build |
| `GET` | `/api/search?q=` | Entity search by name/qname pattern |
| `GET` | `/api/doctor` | Same checks as CLI `doctor` (JSON) |
| `GET` | `/api/dead-code?limit=` | Unreachable functions/methods |
| `GET` | `/api/dependencies` | `entity`, `direction`, `depth` |
| `GET` | `/api/dependencies/graph` | Subgraph for dependency view |
| `GET` | `/api/graph/base` | Full repo graph (filtered) |
| `GET` | `/api/node/{qname}` | Node metadata + source snippet |
| `GET` | `/api/files/source?file_path=` | Full file text + entities |
| `GET` | `/api/subgraph?focus=` | Prefix-filtered subgraph |
| `POST` | `/api/open` | Open file in IDE (`cursor`, `code`, etc.) |

Static UI: served from `frontend/dist/` unless `--dev` (Vite on separate port).

---

## WebSocket

| Path | Events |
|------|--------|
| `/ws/status` | `rebuild_started`, `rebuild_progress`, `rebuild_complete`, `rebuild_error` |

Clients subscribe for indexing progress during UI init/rebuild.

---

## Query request body (`POST /api/query`)

```json
{
  "task": "How does routing work?",
  "top_k": 30,
  "mentioned_entities": ["Blueprint"],
  "token_budget": 6000
}
```

Response includes PPR-ranked nodes/edges for D3 rendering (see `QueryResponse` in `visualizer/models.py`).

---

## Init request body (`POST /api/init`)

```json
{ "target": "https://github.com/pallets/flask" }
```

or local path. Updates `config.yaml` `project_root` and `project_history`.

---

## Graph filtering

`graph_filter.filter_graph_for_visualizer` hides paths matching `exclude_patterns` from config — keeps UI readable on large repos.

---

## IDE open precedence

`/api/open` tries: `cursor` → `code` → `charm` → `pycharm` → `open` / `xdg-open`.

---

## Frontend client

TypeScript API wrapper: `frontend/src/api/client.ts`  
Types: `frontend/src/types/api.ts`, `graph.ts`

When adding endpoints, update routes + client + this doc.
