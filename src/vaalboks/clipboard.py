import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import cast

from django.db import transaction

from .models import ClipboardEntry

MAX_ENTRY_BYTES = 1_000_000
MAX_ENTRIES = 100
MAX_HISTORY_BYTES = 10_000_000


def _entry_dict(entry: ClipboardEntry) -> dict[str, str]:
    created_at = cast(datetime, entry.created_at)
    return {
        "id": cast(str, entry.id),
        "text": cast(str, entry.text),
        "created_at": created_at.astimezone(UTC).isoformat(),
    }


def _serialized_size(entries: list[dict[str, str]]) -> int:
    return len(
        "\n".join(
            json.dumps(entry, ensure_ascii=False, separators=(",", ":")) for entry in entries
        ).encode("utf-8")
    )


def _prune_entries() -> None:
    entries = list(ClipboardEntry.objects.order_by("created_at", "id"))
    while len(entries) > MAX_ENTRIES or _serialized_size(
        [_entry_dict(entry) for entry in entries]
    ) > (MAX_HISTORY_BYTES):
        ClipboardEntry.objects.filter(pk=entries.pop(0).pk).delete()


def _revision(entries: list[dict[str, str]]) -> str:
    if not entries:
        return "empty"
    payload = json.dumps(entries, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def list_entries() -> tuple[list[dict[str, str]], str]:
    entries = [_entry_dict(entry) for entry in ClipboardEntry.objects.order_by("created_at", "id")]
    return list(reversed(entries)), _revision(entries)


def append_entry(text: str) -> dict[str, str]:
    if not text.strip():
        raise ValueError("text must not be blank")
    if len(text.encode("utf-8")) > MAX_ENTRY_BYTES:
        raise ValueError(f"text must be at most {MAX_ENTRY_BYTES} bytes")

    entry = ClipboardEntry(
        id=uuid.uuid4().hex,
        text=text,
        created_at=datetime.now(UTC),
    )
    with transaction.atomic():
        entry.save(force_insert=True)
        _prune_entries()
    return _entry_dict(entry)


def delete_entry(entry_id: str) -> bool:
    with transaction.atomic():
        deleted, _ = ClipboardEntry.objects.filter(pk=entry_id).delete()
    return bool(deleted)


def clear_entries() -> None:
    with transaction.atomic():
        ClipboardEntry.objects.all().delete()
