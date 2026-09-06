import argparse
import ipaddress
import os
import socket
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from vaalboks_server.data import default_data_dir


def _lan_addresses() -> list[str]:
    addresses = {"127.0.0.1"}
    try:
        for result in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = result[4][0]
            if isinstance(address, str):
                addresses.add(address)
    except socket.gaierror:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            addresses.add(probe.getsockname()[0])
    except OSError:
        pass
    return sorted(addresses)


def _access_urls(*, host: str, port: int, http: bool) -> list[str]:
    scheme = "http" if http else "https"
    if host not in {"0.0.0.0", "::"}:
        addresses = [host]
    else:
        addresses = [address for address in _lan_addresses() if address != "127.0.0.1"]
        if not addresses:
            addresses = ["127.0.0.1"]
    return [f"{scheme}://{address}:{port}/" for address in addresses]


def _terminal_qr(value: str) -> str:
    import qrcode

    qr = qrcode.QRCode(border=2)
    qr.add_data(value)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    return "\n".join(
        "".join("\N{FULL BLOCK}" * 2 if cell else "  " for cell in row) for row in matrix
    )


def _display_access(*, host: str, port: int, http: bool, show_qr: bool) -> None:
    urls = _access_urls(host=host, port=port, http=http)
    print("\nVaalboks is ready. Open one of these URLs:", file=sys.stderr)
    for url in urls:
        print(f"  {url}", file=sys.stderr)
    if show_qr:
        print("\nScan this QR code on your phone:", file=sys.stderr)
        print(_terminal_qr(urls[0]), file=sys.stderr)
        if not http:
            print(
                "\nHTTPS uses a local self-signed certificate; accept the browser "
                "warning on each device.",
                file=sys.stderr,
            )


def _ensure_certificate(certfile: Path, keyfile: Path) -> bool:
    if certfile.exists() and keyfile.exists():
        return False
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    certfile.parent.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "vaalboks.local")])
    san_names = [x509.DNSName("vaalboks.local"), x509.DNSName("localhost")]
    for address in _lan_addresses():
        san_names.append(x509.IPAddress(ipaddress.ip_address(address)))
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC))
        .not_valid_after(datetime.now(UTC) + timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName(san_names), critical=False)
        .sign(key, hashes.SHA256())
    )
    keyfile.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    certfile.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    keyfile.chmod(0o600)
    return True


def _run_server(
    *,
    args: argparse.Namespace,
    port: int,
    certfile: Path,
    keyfile: Path,
    gunicorn_args: list[str],
) -> None:
    if os.name == "nt" or args.no_persist:
        import uvicorn

        uvicorn.run(
            "vaalboks_server.asgi:application",
            host=args.host,
            port=port,
            workers=1 if args.no_persist else args.workers,
            access_log=True,
            ssl_certfile=None if args.http else str(certfile),
            ssl_keyfile=None if args.http else str(keyfile),
        )
        return

    from gunicorn.app.wsgiapp import run

    sys.argv = ["vaalboks", *gunicorn_args]
    run(prog="vaalboks")


def main() -> None:
    parser = argparse.ArgumentParser(description="Share files on your local network.")
    parser.add_argument("--http", action="store_true", help="Use HTTP instead of HTTPS.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument(
        "--no-qr",
        action="store_true",
        help="Do not print a terminal QR code at startup.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        help="Directory for the database and shared files.",
    )
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Keep the database and shared files in memory for this run.",
    )
    parser.add_argument("--certfile", type=Path)
    parser.add_argument("--keyfile", type=Path)
    args = parser.parse_args()

    if args.no_persist:
        os.environ["VAALBOKS_NO_PERSIST"] = "true"
        args.workers = 1

    if args.data_dir:
        os.environ["VAALBOKS_DATA_DIR"] = str(args.data_dir.expanduser().resolve())
    data_dir = Path(os.environ.get("VAALBOKS_DATA_DIR") or default_data_dir()).expanduser()
    os.environ["VAALBOKS_DATA_DIR"] = str(data_dir.resolve())
    data_dir.mkdir(parents=True, exist_ok=True)
    certfile = (args.certfile or data_dir / "certs" / "vaalboks-cert.pem").expanduser()
    keyfile = (args.keyfile or data_dir / "certs" / "vaalboks-key.pem").expanduser()
    port = args.port or (8123 if args.http else 8443)

    gunicorn_args = [
        "vaalboks_server.asgi:application",
        "--worker-class",
        "uvicorn_worker.UvicornWorker",
        "--workers",
        str(args.workers),
        "--bind",
        f"{args.host}:{port}",
        "--access-logfile",
        "-",
        "--error-logfile",
        "-",
    ]
    if not args.http:
        os.environ["VAALBOKS_DEBUG"] = "false"
        generated_certificate = _ensure_certificate(certfile, keyfile)
        os.environ["VAALBOKS_CERTFILE"] = str(certfile)
        os.environ["VAALBOKS_KEYFILE"] = str(keyfile)
        if generated_certificate:
            print(
                "Generated a self-signed TLS certificate for local-network use.",
                file=sys.stderr,
            )
            print(
                "For a trusted certificate, restart with --certfile and "
                "--keyfile pointing to your own PEM files.",
                file=sys.stderr,
            )
        gunicorn_args.extend(["--certfile", str(certfile), "--keyfile", str(keyfile)])

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vaalboks_server.settings")
    import django
    from django.core.management import call_command

    django.setup()
    call_command("migrate", interactive=False, verbosity=0)
    call_command("collectstatic", interactive=False, verbosity=0, clear=True)

    _display_access(host=args.host, port=port, http=args.http, show_qr=not args.no_qr)
    _run_server(
        args=args,
        port=port,
        certfile=certfile,
        keyfile=keyfile,
        gunicorn_args=gunicorn_args,
    )
