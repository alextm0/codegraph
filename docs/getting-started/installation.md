# Installation

## 1. Install package

```bash
git clone <repo-url> codegraph
cd codegraph
python -m venv .venv && source .venv/bin/activate
pip install -e .
codegraph --help
```

## 2. Start Neo4j

Bolt on port 7687, GDS plugin enabled.

## 3. Initialize project

```bash
codegraph init
```

Creates `config.yaml` and `.env` with `NEO4J_PASSWORD`. Password is **never** written to `config.yaml`.

Optional clone into `projects/`:

```bash
codegraph init https://github.com/pallets/flask
```

## 4. Register MCP

```bash
codegraph install
```

Restart the AI client.

## 5. Index

```bash
codegraph rebuild
codegraph doctor && codegraph status && codegraph stats
```

## Environment variables

| Variable | Purpose |
|----------|---------|
| `NEO4J_PASSWORD` | DB password |
| `CODEGRAPH_CONFIG` | Path to `config.yaml` (set by `serve` / install) |

Next: [quickstart.md](quickstart.md)
