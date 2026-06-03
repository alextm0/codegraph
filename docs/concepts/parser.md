# Parser and entity extraction

CodeGraph ingests **Python only** via **tree-sitter**. All parsed values are **frozen dataclasses** (DEC-002).

**Code:** `src/codegraph/core/parser/`

---

## Pipeline per file

1. Read source bytes
2. `tree-sitter` parse → CST
3. Walk AST with extractors → populate `FileEntities`
4. Return one `FileEntities` per file; directory walk aggregates list

**Entry points:**

- `create_parser()` — returns configured `Parser`
- `parse_file(source, file_path, parser)` → `FileEntities`
- `parse_directory(directory, parser, exclude_patterns)` → `list[FileEntities]`

---

## Intermediate models (`models.py`)

Parsed **before** Neo4j; not stored in DB as separate labels.

| Type | Fields (high level) |
|------|---------------------|
| `FunctionEntity` | name, file_path, lines, signature, docstring |
| `ClassEntity` | name, file_path, lines, bases |
| `MethodEntity` | name, class_name, file_path, lines, signature, docstring |
| `ImportEntity` | module_path, imported_names, is_relative, line |
| `CallEntity` | caller_name, callee_name, line |
| `FileEntities` | file_path + lists of the above (mutable container) |

Stdlib imports are filtered (`node_utils.is_stdlib_module`) so they do not become graph noise.

---

## Extraction modules

| Module | Role |
|--------|------|
| `python_parser.py` | File discovery, parse orchestration |
| `python_lang.py` | Language / grammar binding |
| `extractors.py` | tree-sitter queries for defs, calls, imports |
| `node_utils.py` | Text extraction, docstrings, signatures, enclosing scope |
| `base.py` | Shared parser abstractions |

---

## Caller naming conventions

Extractors assign `caller_name` for calls:

- Top-level function → function name
- Method → `ClassName.method_name`
- Module-level script → `<module>` (maps to File node in resolution)

These feed `_resolve_caller` in [call-resolution.md](call-resolution.md).

---

## Excludes during discovery

`_iter_python_files` applies `exclude_patterns` from config + `.cgignore` via pathspec.

Evaluation harness uses its own excludes: `["tests", ".git"]` when parsing SWE-bench repos.

---

## Failure handling

- Syntax errors: file may be skipped or partially empty (see unit tests)
- Empty files: typically no entities
- Watch mode: parse errors logged; old entities deleted, re-insert skipped on failure

---

## Extending to new languages

Would require:

1. New tree-sitter grammar + extractors
2. New resolution module (imports/calls differ per language)
3. DEC-003 update or new decision for node labels
4. Graph builder edge creators

Do not copy CGC multi-language docs as implemented behavior. See [../roadmap.md](../roadmap.md).
