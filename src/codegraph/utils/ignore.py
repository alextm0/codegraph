import fnmatch
import os
from pathlib import Path

def load_ignore_patterns(ignore_file: str | Path) -> list[str]:
    """
    Load ignore patterns from a file (e.g., .cgignore).
    
    Each line in the file is treated as a pattern, unless it's empty
    or starts with '#'.
    
    Parameters:
        ignore_file (str | Path): Path to the ignore file.
        
    Returns:
        list[str]: A list of patterns found in the file.
    """
    patterns = []
    path = Path(ignore_file)
    if not path.exists():
        return patterns

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)
    except OSError:
        # If we can't read it, just return what we have (likely empty)
        pass
        
    return patterns

def is_ignored(path_str: str, patterns: list[str]) -> bool:
    """
    Determine whether a filepath matches any of the provided ignore patterns.
    
    Patterns containing wildcard characters (*, ?, [, ]) are treated as shell-style glob patterns; 
    patterns ending with '/' are treated as directory matches;
    other patterns are matched by simple substring containment.
    
    Parameters:
        path_str (str): Filesystem path to test.
        patterns (list[str]): Ignore patterns to check against.
    
    Returns:
        bool: `True` if `path_str` matches any pattern, `False` otherwise.
    """
    # Normalize path separators and case for consistent matching
    path_str = path_str.replace("\\", "/").lower()
    
    for pattern in patterns:
        pattern = pattern.replace("\\", "/").lower()
        
        # Directory pattern: matches if the path contains the directory or is within it
        if pattern.endswith("/"):
            dir_pattern = pattern.rstrip("/")
            if f"/{dir_pattern}/" in f"/{path_str}/":
                return True
            continue

        # Wildcard pattern: use fnmatch
        if any(char in pattern for char in "*?[]"):
            # Check if the pattern matches the filename or the full path
            if fnmatch.fnmatch(path_str, pattern) or fnmatch.fnmatch(os.path.basename(path_str), pattern):
                return True
            # Also handle patterns that should match anywhere in the path
            if f"*/{pattern}" in path_str or fnmatch.fnmatch(path_str, f"*/{pattern}"):
                return True
        # Simple substring match
        elif pattern in path_str:
            return True
            
    return False
