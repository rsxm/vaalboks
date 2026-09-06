import os
from pathlib import Path

bind = "0.0.0.0:8443"
workers = 2
worker_class = "uvicorn_worker.UvicornWorker"
accesslog = "-"
errorlog = "-"
certfile: str | None = os.environ.get("VAALBOKS_CERTFILE")
keyfile: str | None = os.environ.get("VAALBOKS_KEYFILE")


def configure_tls(cert_path: Path, key_path: Path) -> None:
    global certfile, keyfile
    if not cert_path.is_file():
        raise FileNotFoundError(f"TLS certificate does not exist: {cert_path}")
    if not key_path.is_file():
        raise FileNotFoundError(f"TLS private key does not exist: {key_path}")
    certfile = str(cert_path)
    keyfile = str(key_path)


if certfile is None or keyfile is None:
    raise RuntimeError(
        "TLS is required by vaalboks_server.gunicorn; set VAALBOKS_CERTFILE and "
        "VAALBOKS_KEYFILE before starting Gunicorn."
    )
if not Path(certfile).is_file():
    raise FileNotFoundError(f"TLS certificate does not exist: {certfile}")
if not Path(keyfile).is_file():
    raise FileNotFoundError(f"TLS private key does not exist: {keyfile}")
