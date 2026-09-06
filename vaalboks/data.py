from pathlib import Path


def repository_root(start: Path | None = None) -> Path | None:
    """Return the nearest Git worktree root, if ``start`` is inside one."""
    path = (start or Path.cwd()).resolve()
    for candidate in (path, *path.parents):
        git_metadata = candidate / ".git"
        if git_metadata.is_dir() or git_metadata.is_file():
            return candidate
    return None


def default_data_dir(start: Path | None = None) -> Path:
    """Choose checkout-local state for development and per-user state otherwise."""
    root = repository_root(start)
    return root / "vaalboks-data" if root else Path.home() / ".vaalboks"
