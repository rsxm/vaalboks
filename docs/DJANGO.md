# Django integration

The file-sharing interface can be mounted in an existing Django project.
Install `vaalboks`, add it to `INSTALLED_APPS`, configure the required
`vaalboks` storage alias, run migrations, and include `vaalboks.urls`:

```python
# settings.py
INSTALLED_APPS = [
    # ...
    "vaalboks",
]

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    "vaalboks": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": BASE_DIR / "shared"},
    },
}
```

```python
# urls.py
from django.urls import include, path

urlpatterns = [
    path("share/", include("vaalboks.urls")),
]
```

The app does not require the bundled `vaalboks_server` settings, middleware,
or server. The host project remains responsible for Django middleware, static
files, CSRF, and deployment configuration.

The app always uses `STORAGES["vaalboks"]`; it does not fall back to Django's
default storage or call `storage.path()`. For quick, ephemeral sharing, use
Django's in-memory storage backend:

```python
STORAGES = {
    "vaalboks": {
        "BACKEND": "django.core.files.storage.InMemoryStorage",
    },
}
```

In-memory files disappear when the server process stops and are not shared
between multiple worker processes. File listings require a storage backend
that implements `listdir()` and `size()`.
