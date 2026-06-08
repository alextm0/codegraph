# Call and import resolution

Static linking from parse-time `CallEntity` / `ImportEntity` to graph edges. **Pure Python** — no Neo4j in this layer (`resolution.py`).

**Binding rule:** ambiguous callee → **no `CALLS` edge**.

---

## Entity lookup table

Built once per rebuild from all `FileEntities`:

```
simple_name → [qualified_name, ...]
```

Registered names:

- Function `foo` → `path/to/file.py::foo`
- Class `Bar` → `path/to/file.py::Bar`
- Method → `path::Class.method` and also `Class.method` as alias

---

## Callee resolution order (`_resolve_callee`)

For each call site:

1. **Import map** — if callee imported from another file, resolve in that file’s namespace first
2. **Same file** — definition in current `file_path`
3. **Global unique** — exactly one entry in lookup for that simple name
4. **Otherwise** — return `None` (edge omitted)

**Filtered:** callees in `_PYTHON_BUILTINS` (`len`, `print`, `str`, …) never get edges.

---

## Caller resolution (`_resolve_caller`)

| caller_name | Resolved qualified_name |
|-------------|-------------------------|
| `<module>` | File path (File node) |
| `Class.method` | `file::Class.method` |
| `func` | `file::func` |

---

## Import resolution (`_resolve_import_to_file_path`)

Maps `module.path` to a project file path by matching against known file paths (package `__init__.py`, module `.py` layout). Failed imports → no `IMPORTS` edge.

Import map per file maps **symbol alias → file path** for callee disambiguation.

---

## Inheritance (`_resolve_base_class`)

Resolves base class names to Class nodes; creates `INHERITS_FROM` when unambiguous.

---

## Graph build order (`graph_builder.py`)

**Pass 1:** All nodes + `CONTAINS` edges (structure exists before cross-file links).

**Pass 2:** `CALLS`, `IMPORTS`, `INHERITS_FROM` — requires full lookup table.

Edge weights written as `1.0`; IDF applied later at retrieval.

---

## Implications for agents

- Popular names (`get`, `run`, `main`) often have **no** or **wrong** edge if ambiguous
- Mention **specific entity names** in `mentioned_entities` to strengthen seeds
- `query_dependencies` only follows edges that exist — not full IDE reference search

---

## Testing

Unit tests cover resolution without Neo4j: `tests/unit/core/graph/` (resolution, builder mocks).

Integration tests use `tests/fixtures/user_auth/` for end-to-end CALLS chains.
