"""Extract gold file paths from SWE-bench unified diff patches."""

import re


def extract_gold_files(patch: str) -> list[str]:
    """Extract changed file paths from a unified diff patch string.

    Parses `--- a/<path>` / `+++ b/<path>` headers from a unified diff,
    ignoring /dev/null entries (added/deleted files still count).

    Args:
        patch: Raw unified diff string (e.g. from SWE-bench `patch` field).

    Returns:
        Deduplicated list of file paths in the order they first appear.
        Paths are returned without the `a/` / `b/` prefix.
    """
    seen: set[str] = set()
    result: list[str] = []

    for line in patch.splitlines():
        # Match "--- a/path/to/file.py" or "+++ b/path/to/file.py"
        m = re.match(r"^(?:---|\+\+\+) (?:a|b)/(.+)$", line)
        if not m:
            continue
        path = m.group(1).strip()
        if path == "/dev/null":
            continue
        if path not in seen:
            seen.add(path)
            result.append(path)

    return result
