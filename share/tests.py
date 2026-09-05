import tempfile
from pathlib import Path

from asgiref.sync import async_to_sync
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings


class SharingTests(TestCase):
    def test_index_has_strict_csp_and_external_assets(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("default-src 'none'", response["Content-Security-Policy"])
        self.assertContains(response, "/static/share/app.css")
        self.assertNotContains(response, "<style")
        self.assertNotContains(response, ' style="')

    def test_upload_and_download_preserve_relative_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with override_settings(VAALBOKS_SHARED_ROOT=root):
                response = self.client.post(
                    "/api/upload/",
                    {
                        "files": SimpleUploadedFile("hello.txt", b"hello"),
                        "paths": "nested/hello.txt",
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual((root / "nested/hello.txt").read_bytes(), b"hello")

                response = self.client.get("/files/nested/hello.txt")
                self.assertEqual(response.status_code, 200)

                async def read_stream():
                    return b"".join([chunk async for chunk in response.streaming_content])

                self.assertEqual(async_to_sync(read_stream)(), b"hello")

    def test_download_rejects_path_traversal(self):
        response = self.client.get("/files/../settings.py")

        self.assertEqual(response.status_code, 404)
