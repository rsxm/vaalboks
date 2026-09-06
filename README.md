# vaalboks

<p align="center">
  <img src="share/static/share/logo.svg" alt="vaalboks logo" width="520">
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
Install `vaalboks`, add `share` to `INSTALLED_APPS`, configure the directory
used for uploads, and include the app URLs:

```python
# settings.py
INSTALLED_APPS = [
    # ...
    "share",
]

VAALBOKS_SHARED_ROOT = BASE_DIR / "shared"
```

```python
# urls.py
from django.urls import include, path

urlpatterns = [
    path("share/", include("share.urls")),
]
```

The app does not require the bundled `vaalboks` settings, middleware, or
server. The host project remains responsible for Django middleware, static
files, CSRF, and deployment configuration.

## Direct Gunicorn HTTPS + zstd

This section applies to Linux and macOS. Windows users should use the `vaalboks`
command, which selects Uvicorn automatically.

Gunicorn can terminate HTTPS, and Django compresses eligible text responses
with zstd:

```sh
uv run gunicorn vaalboks.asgi:application \
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

Clipboard entries are stored as plain-text JSON lines in
`~/.vaalboks/shared/clipboard.jsonl` (or the checkout-local
`vaalboks-data/shared/clipboard.jsonl`, or the configured shared root). The
browser uses explicit Paste and Copy buttons because browser clipboard access
requires user permission. The file inherits the same local-network privacy
model as other shared files.
