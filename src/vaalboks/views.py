import asyncio
import json
import mimetypes
from collections.abc import Iterable
from pathlib import PurePosixPath
from typing import BinaryIO

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import Storage, storages
from django.core.files.storage.handler import InvalidStorageError
from django.http import Http404, HttpResponseRedirect, JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .access import ROOM_SESSION_KEY, room_digest, room_key_required, room_keys_enabled
from .clipboard import append_entry, clear_entries, delete_entry, list_entries


def _storage() -> Storage:
    try:
        return storages["vaalboks"]
    except (InvalidStorageError, ImproperlyConfigured) as error:
        raise ImproperlyConfigured(
            'Configure a dedicated STORAGES["vaalboks"] alias for shared files.'
        ) from error


def _safe_relpath(relpath: str, *, allow_empty: bool = False) -> str:
    normalized = relpath.replace("\\", "/")
    if normalized.startswith("/"):
        raise Http404("Invalid path")
    parts = [part for part in normalized.split("/") if part not in {"", "."}]
    if not parts and not allow_empty:
        raise Http404("Invalid path")
    if any(part == ".." for part in parts):
        raise Http404("Invalid path")
    return str(PurePosixPath(*parts)) if parts else ""


def _room_id(request) -> str:
    if not room_keys_enabled():
        return ""
    room_id = request.session.get(ROOM_SESSION_KEY)
    if not room_id:
        raise ImproperlyConfigured("An authenticated room session is required.")
    return room_id


def _scoped_path(request, relpath: str) -> str:
    room_id = _room_id(request)
    return (
        f"rooms/{room_id}/{relpath}"
        if room_id and relpath
        else (f"rooms/{room_id}" if room_id else relpath)
    )


def _child_path(directory: str, name: str) -> str:
    return f"{directory}/{name}" if directory else name


def _is_visible(name: str) -> bool:
    return not name.startswith(".") and name != "clipboard.jsonl"


def _listdir(storage: Storage, rel_dir: str) -> tuple[list[str], list[str]]:
    try:
        directories, files = storage.listdir(rel_dir)
    except FileNotFoundError:
        if not rel_dir:
            return [], []
        raise Http404("Not a directory") from None
    except NotADirectoryError:
        raise Http404("Not a directory") from None
    return (
        [name for name in directories if _is_visible(name)],
        [name for name in files if _is_visible(name)],
    )


def _human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _build_entries(rel_dir: str = "", request=None) -> list[dict]:
    rel_dir = _safe_relpath(rel_dir, allow_empty=True)
    storage = _storage()
    scoped_dir = _scoped_path(request, rel_dir)
    directories, files = _listdir(storage, scoped_dir)
    names: Iterable[tuple[bool, str]] = (
        *((False, name) for name in directories),
        *((True, name) for name in files),
    )
    entries = []
    for is_file, name in sorted(names, key=lambda item: (item[0], item[1].lower())):
        item_relpath = _child_path(rel_dir, name)
        storage_path = _scoped_path(request, item_relpath)
        if is_file:
            entries.append(
                {
                    "kind": "file",
                    "name": name,
                    "relpath": item_relpath,
                    "size": _human_size(storage.size(storage_path)),
                }
            )
        else:
            child_dirs, child_files = _listdir(storage, storage_path)
            entries.append(
                {
                    "kind": "dir",
                    "name": name,
                    "relpath": item_relpath,
                    "has_children": bool(child_dirs or child_files),
                }
            )
    return entries


@ensure_csrf_cookie
@room_key_required
def index(request):
    return render(request, "vaalboks/index.html", {"room_keys_enabled": room_keys_enabled()})


def room(request):
    if not room_keys_enabled():
        return HttpResponseRedirect(reverse("vaalboks:index"))
    if request.method == "POST":
        phrase = request.POST.get("phrase", "").strip()
        if not phrase:
            return render(
                request, "vaalboks/login.html", {"error": "Enter a room phrase."}, status=400
            )
        request.session.cycle_key()
        request.session[ROOM_SESSION_KEY] = room_digest(phrase)
        request.session.set_expiry(getattr(settings, "VAALBOKS_SESSION_AGE", 12 * 60 * 60))
        request.session.save()
        return HttpResponseRedirect(reverse("vaalboks:index"))
    return render(request, "vaalboks/login.html")


@require_POST
@room_key_required
def leave_room(request):
    request.session.flush()
    return HttpResponseRedirect(reverse("vaalboks:room"))


@room_key_required
def list_files(request):
    return render(
        request,
        "vaalboks/_file_list.html",
        {"entries": _build_entries(request.GET.get("path", ""), request)},
    )


@require_POST
@room_key_required
def upload(request):
    storage = _storage()
    files = request.FILES.getlist("files")
    paths = request.POST.getlist("paths")
    if not files:
        return JsonResponse({"error": "no files"}, status=400)
    saved = 0
    for uploaded_file, relpath in zip(files, paths, strict=True):
        relpath = _safe_relpath(relpath.lstrip("/") or uploaded_file.name)
        storage_path = _scoped_path(request, relpath)
        if storage.exists(storage_path):
            storage.delete(storage_path)
        storage.save(storage_path, uploaded_file)
        saved += 1
    return JsonResponse({"saved": saved})


@room_key_required
def clipboard(request):
    entries, revision = list_entries(_room_id(request))
    return JsonResponse({"entries": entries, "revision": revision})


@require_POST
@room_key_required
def clipboard_add(request):
    try:
        payload = json.loads(request.body)
        text = payload["text"]
        if not isinstance(text, str):
            raise TypeError
        entry = append_entry(text, _room_id(request))
    except json.JSONDecodeError, KeyError, TypeError:
        return JsonResponse({"error": "request must contain a text string"}, status=400)
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)
    return JsonResponse({"entry": entry}, status=201)


@require_POST
@room_key_required
def clipboard_delete(request, entry_id: str):
    if not delete_entry(entry_id, _room_id(request)):
        raise Http404("Clipboard entry not found")
    return JsonResponse({"deleted": entry_id})


@require_POST
@room_key_required
def clipboard_clear(request):
    clear_entries(_room_id(request))
    return JsonResponse({"cleared": True})


@room_key_required
async def download(request, relpath: str):
    relpath = _safe_relpath(relpath)
    storage = _storage()
    storage_path = _scoped_path(request, relpath)
    if not storage.exists(storage_path):
        raise Http404("Not a file")

    def open_binary() -> BinaryIO:
        return storage.open(storage_path, "rb")

    try:
        file = await asyncio.to_thread(open_binary)
    except FileNotFoundError, IsADirectoryError, NotADirectoryError:
        raise Http404("Not a file") from None

    async def file_chunks():
        try:
            while chunk := await asyncio.to_thread(file.read, 1024 * 1024):
                yield chunk
        finally:
            await asyncio.to_thread(file.close)

    filename = PurePosixPath(relpath).name
    response = StreamingHttpResponse(
        file_chunks(),
        content_type=mimetypes.guess_type(filename)[0] or "application/octet-stream",
    )
    response["Content-Length"] = storage.size(storage_path)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
