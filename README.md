# vaalboks

<p align="center">
  <img src="share/static/share/logo.svg" alt="vaalboks logo" width="520">
</p>

Vaalboks is a small file-sharing server for a local network. Drop files or
folders in the browser, then download them from another device on the same
network.

The name is Afrikaans for “dull box” — a straightforward tool for moving files
between computers without a separate hosted service.

## Stack

- Python 3.14, Django 6.1, uv
- Frontend: plain HTML/CSS/JS + htmx 4.0
- Uploads use XHR for live progress and speed tracking; downloads use streaming
  `fetch`

## Run

After installing the package, start the server with:

```sh
uvx vaalboks
```

This starts HTTPS on `0.0.0.0:8443` with two workers. Runtime data is stored
in `./vaalboks-data`, and a self-signed certificate is generated there on
first launch. Migrations and static-file collection run automatically. Use
`--http` for plain HTTP on port 8123. The CLI uses Gunicorn on Linux and macOS
and Uvicorn on Windows.

When running from this checkout:

```sh
uv run python manage.py runserver 0.0.0.0:8123
```

Then open `http://<your-LAN-IP>:8123/` from any device on the network.
(Find your IP with `ipconfig getifaddr en0`.)

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
`--certfile`, and `--keyfile`.

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
- `GET /files/<path>` — download a shared file (path-traversal protected)
