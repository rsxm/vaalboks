# vaalboks

<p align="center">
  <img src="src/vaalboks/static/vaalboks/logo.svg" alt="vaalboks logo" width="520">
</p>

Vaalboks is a small file-sharing server for a local network. Drop files or
folders in the browser, then download them from another device on the same
network. It also supports sharing short text snippets between connected
computers.

The name is Afrikaans for “dull box” — a straightforward tool for moving files
between computers without a separate hosted service.

## Stack

- Python 3.14, Django 6.1, uv
- Frontend: plain HTML/CSS/JS + htmx 4.0
- Uploads use XHR for live progress and speed tracking; downloads use streaming
  `fetch`

## Run

To use vaalboks, install `uv` and run:

```sh
uvx vaalboks
```

`uvx` downloads and runs the package without requiring a checkout or a
separate package installation. The command starts HTTPS on `0.0.0.0:8443`
with two workers. Runtime data is stored in `~/.vaalboks` when run outside a
Git checkout, and in `./vaalboks-data` when run from this repository. A
self-signed certificate is generated there on first launch. Migrations and
static-file collection run automatically. At startup, the CLI prints the
server's local-network URL(s) and a terminal QR code for the first URL. Use
`--no-qr` to hide the QR code. Use `--http` for plain HTTP on port 8123. The
CLI uses Gunicorn on Linux and macOS and Uvicorn on Windows.

For the easiest phone workflow, connect the phone and computer to the same
Wi-Fi, scan the startup QR code, and open the displayed URL. With the default
HTTPS mode, accept the self-signed certificate warning on the phone; use
`--http` on a trusted home network if you want to avoid that warning.

When running from this checkout:

```sh
uv run python manage.py runserver 0.0.0.0:8123
```

Then open `http://<your-LAN-IP>:8123/` from any device on the network.
(Find your IP with `ipconfig getifaddr en0`.)

## Use as a Django app

The file-sharing interface can also be mounted in an existing Django project.
Install `vaalboks`, add `vaalboks` to `INSTALLED_APPS`, configure the required
`vaalboks` storage alias, run migrations, and include `vaalboks.urls`:

```python
# settings.py
INSTALLED_APPS = [
    # ...
    "vaalboks",
]

STORAGES = {
    # Keep the project's existing default/staticfiles aliases as appropriate.
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
default storage or call `storage.path()`. For object storage, install and
configure [django-storages](https://django-storages.readthedocs.io/) and use
its backend in the alias, for example:

```python
STORAGES = {
    "vaalboks": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": "my-share",
            "location": "uploads",
        },
    },
}
```

File listings use the storage backend's logical `listdir()` operation. A
backend must implement `listdir()` and `size()` for the browser listing to
work; object-storage backends may have provider-specific directory semantics.
Directory names are logical prefixes, not local filesystem paths.

## Direct Gunicorn HTTPS + zstd

This section applies to Linux and macOS. Windows users should use the `vaalboks`
command, which selects Uvicorn automatically.

Gunicorn can terminate HTTPS, and Django compresses eligible text responses
with zstd:

```sh
uv run gunicorn vaalboks_server.asgi:application \
  --worker-class uvicorn_worker.UvicornWorker \
  --workers 2 \
  --bind 0.0.0.0:8443 \
  --certfile certs/vaalboks-cert.pem \
  --keyfile certs/vaalboks-key.pem
```

Open `https://<your-LAN-IP>:8443/` and trust the self-signed certificate on
each device that will connect. This setup provides HTTPS and zstd compression.

The CLI also accepts `--host`, `--port`, `--workers`, `--data-dir`,
`--certfile`, and `--keyfile`. Set `VAALBOKS_DATA_DIR` to configure the
runtime directory without a command-line argument; explicit configuration
takes precedence over the defaults.

## Publishing

Build artifacts locally with:

```sh
uv build
```

The repository includes GitHub Actions for quality checks and publishing on a
published GitHub release. Configure PyPI trusted publishing for the GitHub
repository before creating the first release; no long-lived PyPI token is
required.

## How it works

- `GET /` — single page with drop zone and live file listing
- `GET /api/files/` — htmx partial that re-renders the listing after uploads
- `POST /api/upload/` — multipart upload; folders are traversed client-side
  (`webkitGetAsEntry`) and each file is sent with its relative path
- `GET /api/clipboard/` — list shared clipboard entries
- `POST /api/clipboard/add/` — append a text entry from the clipboard panel
- `POST /api/clipboard/<id>/delete/` — delete one clipboard entry
- `POST /api/clipboard/clear/` — delete all clipboard entries
- `GET /files/<path>` — download a shared file (path-traversal protected)

Clipboard entries are stored transactionally in the Django database and are
included in the app's migrations. The browser uses explicit Paste and Copy
buttons because browser clipboard access requires user permission. Clipboard
history has the same 100-entry and 10 MB limits as before, and it inherits the
same local-network privacy model as other shared files. JSONL clipboard files
are not read by the database-backed implementation.
