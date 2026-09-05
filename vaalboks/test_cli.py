from unittest import TestCase
from unittest.mock import patch

from vaalboks.cli import _access_urls, _terminal_qr


class CliTests(TestCase):
    @patch("vaalboks.cli._lan_addresses", return_value=["10.0.0.12", "127.0.0.1"])
    def test_access_urls_use_lan_addresses_for_wildcard_bind(self, _lan_addresses):
        self.assertEqual(
            _access_urls(host="0.0.0.0", port=8123, http=True),
            ["http://10.0.0.12:8123/"],
        )

    def test_access_urls_use_explicit_host(self):
        self.assertEqual(
            _access_urls(host="192.168.1.5", port=8443, http=False),
            ["https://192.168.1.5:8443/"],
        )

    def test_terminal_qr_contains_quiet_zone_and_data(self):
        qr = _terminal_qr("http://10.0.0.12:8123/")

        rows = qr.splitlines()
        self.assertGreater(len(rows), 20)
        self.assertEqual(len({len(row) for row in rows}), 1)
        self.assertIn("\N{FULL BLOCK}", qr)
