# Configuration reference

Primary file: **`config.yaml`** at project root (path passed via `--config` or `CODEGRAPH_CONFIG`).

Password: **`NEO4J_PASSWORD`** in `.env` only (DEC-010).

---

## Example

```yaml
project_root: .

exclude_patterns:
  - __pycache__
  - .venv
  - .git
  - "*.pyc"
  - .pytest_cache

neo4j:
  uri: neo4j://localhost:7687
  username: neo4j
  # password: NEVER here — use .env

ppr:
  damping_factor: 0.70
  max_iterations: 20
  tolerance: 1.0e-07
  top_k: 30
  retrieval_mode: uniform

seed_selection:
  entity_match_weight: 0.6
  bm25_weight: 0.3
  bm25_top_n: 10
  exclude_seed_paths:
    - tests/
    - test_

mcp:
  server_name: codegraph
  default_token_budget: 6000
  default_top_k: 30

project_history:
  - name: my-app
    path: /abs/path/to/app
    url: null
```

---

## Keys

### `project_root`

Directory to parse. Resolved relative to config file location if not absolute.

### `exclude_patterns`

Glob/path segments skipped during **indexing**.

### `neo4j`

| Key | Description |
|-----|-------------|
| `uri` | Bolt URI |
| `username` | DB user |

### `ppr`

| Key | Default | Description |
|-----|---------|-------------|
| `damping_factor` | 0.70 | PageRank damping (DEC-001) |
| `max_iterations` | 20 | GDS iteration cap |
| `tolerance` | 1e-7 | Convergence tolerance |
| `top_k` | 30 | Max ranked nodes |
| `retrieval_mode` | `uniform` | Seed restart strategy |

### `seed_selection`

| Key | Default | Description |
|-----|---------|-------------|
| `entity_match_weight` | 0.6 | Seed mass from name match |
| `bm25_weight` | 0.3 | Seed mass from BM25 |
| `bm25_top_n` | 10 | BM25 candidates |
| `exclude_seed_paths` | [] | Path prefixes excluded from seeds only |

### `mcp`

Defaults when tool passes `top_k=0` or `token_budget=0`.

### `project_history`

Named projects for `init` / switching; not required for single-repo use.

---

## Optional `.cgignore`

Gitignore-style pathspecs at repo root; merged into parser excludes when present.

---

## Loader

`src/codegraph/utils/config.py` — `load_raw_config`, `resolve_project_root`.

Do not document password-in-yaml as supported; `doctor` warns if missing `NEO4J_PASSWORD`.
