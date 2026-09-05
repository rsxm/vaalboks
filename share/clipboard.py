import json
import logging
import os
import tempfile
import threading
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

MAX_ENTRY_BYTES = 1_000_000
MAX_ENTRIES = 100
MAX_HISTORY_BYTES = 10_000_000
_thread_lock = threading.RLock()
logger = logging.getLogger(__name__)

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows uses the process lock.
    fcntl = None


def _clipboard_path(root: Path) -> Path:
    return root / "clipboard.jsonl"


@contextmanager
def _locked(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    with _thread_lock:
        lock_path = root / ".clipboard.lock"
        with lock_path.open("a+") as lock_file:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _read_unlocked(path: Path) -> list[dict]:
    if not path.exists():
        return []
    entries = []
    with path.open(encoding="utf-8") as clipboard_file:
        for line_number, line in enumerate(clipboard_file, start=1):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Ignoring malformed clipboard JSONL entry at line %d", line_number)
                continue
            if (
                isinstance(entry, dict)
                and isinstance(entry.get("id"), str)
                and isinstance(entry.get("text"), str)
                and isinstance(entry.get("created_at"), str)
            ):
                entries.append(entry)
            if len(entries) >= MAX_ENTRIES:
                break
    return entries


def _rewrite_unlocked(path: Path, entries: list[dict]) -> None:
    if not entries:
        path.unlink(missing_ok=True)
        return
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=".clipboard-", delete=False
    ) as temporary:
        for entry in entries:
            temporary.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")))
            temporary.write("\n")
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, path)


def list_entries(root: Path) -> tuple[list[dict], str]:
    path = _clipboard_path(root)
    with _locked(root):
        entries = _read_unlocked(path)
        revision = f"{path.stat().st_mtime_ns}:{path.stat().st_size}" if path.exists() else "empty"
    return list(reversed(entries)), revision


def append_entry(root: Path, text: str) -> dict:
    if not text.strip():
        raise ValueError("text must not be blank")
    if len(text.encode("utf-8")) > MAX_ENTRY_BYTES:
        raise ValueError(f"text must be at most {MAX_ENTRY_BYTES} bytes")
    path = _clipboard_path(root)
    entry = {
        "id": uuid.uuid4().hex,
        "text": text,
        "created_at": datetime.now(UTC).isoformat(),
    }
    with _locked(root):
        entries = _read_unlocked(path)
        entries.append(entry)
        entries = entries[-MAX_ENTRIES:]
        while (
            entries
            and len(
                "\n".join(
                    json.dumps(item, ensure_ascii=False, separators=(",", ":")) for item in entries
                ).encode("utf-8")
            )
            > MAX_HISTORY_BYTES
        ):
            entries.pop(0)
        _rewrite_unlocked(path, entries)
    return entry


def delete_entry(root: Path, entry_id: str) -> bool:
    path = _clipboard_path(root)
    with _locked(root):
        entries = _read_unlocked(path)
        remaining = [entry for entry in entries if entry["id"] != entry_id]
        if len(remaining) == len(entries):
            return False
        _rewrite_unlocked(path, remaining)
    return True


def clear_entries(root: Path) -> None:
    with _locked(root):
        _rewrite_unlocked(_clipboard_path(root), [])
