"""Clone and checkout SWE-bench repository instances."""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def clone_or_cache(repo_url: str, cache_dir: str) -> str:
    """Clone a git repository into cache_dir if not already present.

    The repo is cloned once and reused across benchmark instances. The caller
    is responsible for calling checkout_commit() before each instance run.

    Args:
        repo_url: HTTPS or SSH URL of the git repository.
        cache_dir: Root directory where repos are cached.

    Returns:
        Absolute path to the cloned repository directory.
    """
    repo_name = _repo_name_from_url(repo_url)
    repo_path = Path(cache_dir) / repo_name

    if repo_path.exists():
        logger.info("Cache hit: %s", repo_path)
        return str(repo_path)

    logger.info("Cloning %s → %s", repo_url, repo_path)
    repo_path.parent.mkdir(parents=True, exist_ok=True)
    _run(["git", "clone", "--quiet", repo_url, str(repo_path)])
    return str(repo_path)


def checkout_commit(repo_path: str, commit_sha: str) -> None:
    """Hard-reset a cloned repository to a specific commit.

    This is a destructive operation — any local changes are discarded.
    Use only on cache directories managed exclusively by the benchmark runner.

    Args:
        repo_path: Path to the cloned repository.
        commit_sha: Git commit SHA or tag to checkout.
    """
    logger.info("Checking out %s in %s", commit_sha[:12], repo_path)
    if not _commit_exists_locally(repo_path, commit_sha):
        logger.info("Fetching origin (commit not in local cache)")
        _run(["git", "-C", repo_path, "fetch", "--quiet", "origin"])
    _run(["git", "-C", repo_path, "reset", "--hard", commit_sha])
    _run(["git", "-C", repo_path, "clean", "-fdx", "--quiet"])


def _commit_exists_locally(repo_path: str, commit_sha: str) -> bool:
    """Return True if commit_sha is already present in the local git object store."""
    result = subprocess.run(
        ["git", "-C", repo_path, "cat-file", "-e", commit_sha],
        capture_output=True,
    )
    return result.returncode == 0


def _repo_name_from_url(repo_url: str) -> str:
    """Derive a filesystem-safe directory name from a repo URL.

    'https://github.com/django/django' → 'django__django'
    """
    # Strip trailing .git and split on /
    url = repo_url.rstrip("/").removesuffix(".git")
    parts = url.split("/")
    if len(parts) >= 2:
        return "__".join(parts[-2:])
    return parts[-1]


def _run(cmd: list[str]) -> None:
    """Run a subprocess command, raising on non-zero exit."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
