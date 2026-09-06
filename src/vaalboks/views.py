import asyncio
import json
import mimetypes
from pathlib import Path
from typing import BinaryIO

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import Http404, JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .clipboard import append_entry, clear_entries, delete_entry, list_entries


def _open_binary(path: Path) -> BinaryIO:
    return path.open("rb")


def _shared_root() -> Path:
    configured_root = getattr(settings, "VAALBOKS_SHARED_ROOT", None)
    if configured_root is None:
        configured_root = getattr(settings, "SHARED_ROOT", None)
    if configured_root is None:
        raise ImproperlyConfigured(
            "Set VAALBOKS_SHARED_ROOT to the directory used for shared files."
        )
    root = Path(configured_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_resolve(relpath: str) -> Path:
    """Resolve a user-supplied relative path inside SHARED_ROOT, rejecting escapes."""
    root = _shared_root()
    candidate = (root / relpath).resolve()
    if candidate != root and root not in candidate.parents:
        raise Http404("Invalid path")
    return candidate


def _human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _build_entries(rel_dir: str = "") -> list[dict]:
    directory = _safe_resolve(rel_dir)
    if not directory.is_dir():
        raise Http404("Not a directory")
    entries = []
    for item in sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        if item.name.startswith(".") or item.name == "clipboard.jsonl":
            continue
        item_relpath = str(Path(rel_dir) / item.name) if rel_dir else item.name
        if item.is_dir():
            entries.append(
                {
                    "kind": "dir",
                    "name": item.name,
                    "relpath": item_relpath,
                    "has_children": any(not child.name.startswith(".") for child in item.iterdir()),
                }
            )
        elif item.is_file():
            entries.append(
                {
                    "kind": "file",
                    "name": item.name,
                    "relpath": item_relpath,
                    "size": _human_size(item.stat().st_size),
                }
            )
    return entries


@ensure_csrf_cookie
def index(request):
    return render(request, "vaalboks/index.html")


def list_files(request):
    """htmx partial: refreshed file listing."""
    return render(
        request,
        "vaalboks/_file_list.html",
        {"entries": _build_entries(request.GET.get("path", ""))},
    )


@require_POST
def upload(request):
    files = request.FILES.getlist("files")
    paths = request.POST.getlist("paths")
    if not files:
        return JsonResponse({"error": "no files"}, status=400)
    saved = 0
    for f, rel in zip(files, paths, strict=True):
        rel = rel.lstrip("/") or f.name
        dest = _safe_resolve(rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as out:
            out.writelines(f.chunks())
        saved += 1
    return JsonResponse({"saved": saved})


def clipboard(request):
    entries, revision = list_entries(_shared_root())
    return JsonResponse({"entries": entries, "revision": revision})


@require_POST
def clipboard_add(request):
    try:
        payload = json.loads(request.body)
        text = payload["text"]
        if not isinstance(text, str):
            raise TypeError
        entry = append_entry(_shared_root(), text)
    except json.JSONDecodeError, KeyError, TypeError:
        return JsonResponse({"error": "request must contain a text string"}, status=400)
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)
    return JsonResponse({"entry": entry}, status=201)


@require_POST
def clipboard_delete(request, entry_id: str):
    if not delete_entry(_shared_root(), entry_id):
        raise Http404("Clipboard entry not found")
    return JsonResponse({"deleted": entry_id})


@require_POST
def clipboard_clear(request):
    clear_entries(_shared_root())
    return JsonResponse({"cleared": True})


async def download(request, relpath: str):
    target = _safe_resolve(relpath)
    if not target.is_file():
        raise Http404("Not a file")

    async def file_chunks():
        file = await asyncio.to_thread(_open_binary, target)
        try:
            while chunk := await asyncio.to_thread(file.read, 1024 * 1024):
                yield chunk
        finally:
            await asyncio.to_thread(file.close)

    response = StreamingHttpResponse(
        file_chunks(),
        content_type=mimetypes.guess_type(target.name)[0] or "application/octet-stream",
    )
    response["Content-Length"] = target.stat().st_size
    response["Content-Disposition"] = f'attachment; filename="{target.name}"'
    return response
