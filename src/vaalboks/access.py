import hashlib
import hmac
import inspect
from functools import wraps
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils.cache import patch_vary_headers

ROOM_SESSION_KEY = "vaalboks_room"


def room_keys_enabled() -> bool:
    return bool(getattr(settings, "VAALBOKS_ROOM_KEYS", False))


def room_digest(phrase: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode(),
        phrase.strip().encode(),
        hashlib.sha256,
    ).hexdigest()


def room_root(shared_root: Path, phrase: str) -> Path:
    return shared_root / "rooms" / room_digest(phrase)


def room_attempt_allowed(request) -> bool:
    address = request.META.get("REMOTE_ADDR", "unknown")
    key = f"vaalboks:room-attempt:{hashlib.sha256(address.encode()).hexdigest()}"
    window = getattr(settings, "VAALBOKS_ROOM_ATTEMPT_WINDOW", 60)
    limit = getattr(settings, "VAALBOKS_ROOM_ATTEMPT_LIMIT", 10)
    if cache.add(key, 1, timeout=window):
        return True
    attempts = cache.get(key, 0)
    if attempts >= limit:
        return False
    cache.set(key, attempts + 1, timeout=window)
    return True


def room_attempt_limited_response() -> HttpResponse:
    response = HttpResponse("Too many room attempts. Try again later.", status=429)
    response["Retry-After"] = str(getattr(settings, "VAALBOKS_ROOM_ATTEMPT_WINDOW", 60))
    return response


def room_key_required(view):
    if inspect.iscoroutinefunction(view):

        @wraps(view)
        async def async_wrapper(request, *args, **kwargs):
            if room_keys_enabled() and not request.session.get(ROOM_SESSION_KEY):
                return HttpResponseRedirect(reverse("vaalboks:room"))
            response = await view(request, *args, **kwargs)
            if room_keys_enabled():
                response["Cache-Control"] = "private, no-store"
                patch_vary_headers(response, ["Cookie"])
            return response

        return async_wrapper

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if room_keys_enabled() and not request.session.get(ROOM_SESSION_KEY):
            return HttpResponseRedirect(reverse("vaalboks:room"))
        response = view(request, *args, **kwargs)
        if room_keys_enabled():
            response["Cache-Control"] = "private, no-store"
            patch_vary_headers(response, ["Cookie"])
        return response

    return wrapper
