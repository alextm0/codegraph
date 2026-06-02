"""Shared helpers for evaluation unit tests."""

# Minimal unified diff so ``extract_gold_files`` returns ``gold.py`` without mocking.
GOLD_PATCH = """\
--- a/gold.py
+++ b/gold.py
@@ -1 +1 @@
-x
+y
"""


def make_instance(
    repo: str,
    base_commit: str,
    instance_id: str | None = None,
    patch: str = GOLD_PATCH,
) -> dict:
    """Build a minimal SWE-bench instance dict."""
    return {
        "repo": repo,
        "base_commit": base_commit,
        "instance_id": instance_id or f"{repo}_{base_commit[:8]}",
        "problem_statement": "fix something",
        "patch": patch,
    }


def make_result(idx: int) -> dict:
    """Build a minimal per-instance JSONL record with index for ordering tests."""
    return {"instance_id": f"inst_{idx}", "idx": idx}
