"""Portable filesystem path resolution utilities for AEGIS across Linux and Windows."""

from pathlib import Path


def get_project_root() -> Path:
    """Locate the AEGIS repository root directory across development and cloud environments.

    Searches upward from this module's location and current working directory
    for root markers ('pyproject.toml', '.git', or 'data/processed').
    """
    # 1. Search upward from module location
    curr = Path(__file__).resolve().parent
    for _ in range(5):
        if (
            (curr / "pyproject.toml").exists()
            or (curr / ".git").exists()
            or (curr / "data" / "processed").exists()
        ):
            return curr
        if curr.parent == curr:
            break
        curr = curr.parent

    # 2. Search upward from working directory
    cwd = Path.cwd().resolve()
    curr = cwd
    for _ in range(5):
        if (
            (curr / "pyproject.toml").exists()
            or (curr / ".git").exists()
            or (curr / "data" / "processed").exists()
        ):
            return curr
        if curr.parent == curr:
            break
        curr = curr.parent

    # 3. Default fallback based on standard src layout (src/aegis/utils -> root is 3 levels up)
    return Path(__file__).resolve().parents[2]


def resolve_repo_path(path: str | Path) -> Path:
    """Resolve a relative or absolute path against the project root.

    Parameters
    ----------
    path : str | Path
        Target relative or absolute path.

    Returns
    -------
    Path
        Resolved, normalized absolute or canonical Path.
    """
    p = Path(path)
    # If already an existing absolute path, return it
    if p.is_absolute() and p.exists():
        return p.resolve()

    # If it exists relative to current working directory, return it
    if p.exists():
        return p.resolve()

    # Otherwise resolve against discovered project root
    root = get_project_root()
    candidate = (root / p).resolve()
    if candidate.exists():
        return candidate

    # Return normalized path under root even if it doesn't exist yet (for creation)
    return candidate
