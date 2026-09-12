# Deployment and configuration

## CLI options

The CLI accepts `--host`, `--port`, `--workers`, `--data-dir`, `--no-qr`,
`--no-persist`, `--certfile`, and `--keyfile`. Set `VAALBOKS_DATA_DIR` to
configure the runtime directory without a command-line argument; explicit
configuration takes precedence.

The default server uses Gunicorn on Linux and macOS and Uvicorn on Windows.
`--no-persist` keeps the SQLite database and shared files in memory for the
current run, uses one worker, and loses all data when the process exits.

## Running from a checkout

For local development from the repository:

```sh
uv run python manage.py runserver 0.0.0.0:8123
```

Then open `http://<your-LAN-IP>:8123/` from a device on the network. On macOS,
find the LAN address with `ipconfig getifaddr en0`.

## HTTPS and certificates

The default server uses HTTPS on port 8443. Certificates and private keys are
generated with Python's `cryptography` package; no system OpenSSL command is
required. The private key is stored in the runtime data directory.

For a direct Gunicorn deployment on Linux or macOS:

```sh
uv run gunicorn vaalboks_server.asgi:application \
  --worker-class uvicorn_worker.UvicornWorker \
  --workers 2 \
  --bind 0.0.0.0:8443 \
  --certfile certs/vaalboks-cert.pem \
  --keyfile certs/vaalboks-key.pem
```

The bundled server enables HTTPS-aware cookies by default. Use `--http` only
on a trusted network; HTTP exposes room phrases, session cookies, uploads, and
downloads to network observers.

## Resource limits

The bundled server limits each upload request to 1 GB and 1,000 files. Room
entry attempts are limited to 10 per client address per minute. Override these
values with:

- `VAALBOKS_MAX_UPLOAD_BYTES`
- `VAALBOKS_ROOM_ATTEMPT_LIMIT`
- `VAALBOKS_ROOM_ATTEMPT_WINDOW`

Room throttling uses Django's cache. Use a shared cache backend when running
multiple workers or hosts if the limit must apply across all processes.
