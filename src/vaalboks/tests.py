import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.core.exceptions import ImproperlyConfigured
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from .models import ClipboardEntry


def storage_settings(root: Path) -> dict:
    return {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        "vaalboks": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": str(root)},
        },
    }


class SharingTests(TestCase):
    def test_index_has_strict_csp_and_external_assets(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("default-src 'none'", response["Content-Security-Policy"])
        self.assertContains(response, "/static/vaalboks/app.css")
        self.assertNotContains(response, "<style")
        self.assertNotContains(response, ' style="')

    def test_upload_listing_and_download_use_nested_storage_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with override_settings(STORAGES=storage_settings(root)):
                response = self.client.post(
                    "/api/upload/",
                    {
                        "files": SimpleUploadedFile("hello.txt", b"hello"),
                        "paths": "nested/hello.txt",
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual((root / "nested/hello.txt").read_bytes(), b"hello")

                response = self.client.get("/api/files/")
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "nested")
                response = self.client.get("/api/files/?path=nested")
                self.assertContains(response, "hello.txt")

                response = self.client.get("/files/nested/hello.txt")
                self.assertEqual(response.status_code, 200)

                async def read_stream():
                    return b"".join([chunk async for chunk in response.streaming_content])

                self.assertEqual(async_to_sync(read_stream)(), b"hello")

    def test_upload_collision_overwrites_existing_file(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            override_settings(STORAGES=storage_settings(Path(directory))),
        ):
            payload = {"files": SimpleUploadedFile("same.txt", b"first"), "paths": "same.txt"}
            self.assertEqual(self.client.post("/api/upload/", payload).status_code, 200)
            payload = {"files": SimpleUploadedFile("same.txt", b"second"), "paths": "same.txt"}
            self.assertEqual(self.client.post("/api/upload/", payload).status_code, 200)
            response = self.client.get("/files/same.txt")

            async def read_stream():
                return b"".join([chunk async for chunk in response.streaming_content])

            self.assertEqual(async_to_sync(read_stream)(), b"second")

    def test_listing_filters_hidden_and_internal_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".hidden").write_bytes(b"hidden")
            (root / "clipboard.jsonl").write_text("{}\n")
            (root / "visible.txt").write_bytes(b"visible")
            with override_settings(STORAGES=storage_settings(root)):
                response = self.client.get("/api/files/")
                self.assertContains(response, "visible.txt")
                self.assertNotContains(response, ".hidden")
                self.assertNotContains(response, "clipboard.jsonl")

    def test_download_rejects_path_traversal_and_missing_files(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            override_settings(STORAGES=storage_settings(Path(directory))),
        ):
            self.assertEqual(self.client.get("/files/../settings.py").status_code, 404)
            self.assertEqual(self.client.get("/files/missing.txt").status_code, 404)
            (Path(directory) / "directory").mkdir()
            self.assertEqual(self.client.get("/files/directory").status_code, 404)

    def test_shared_storage_alias_is_required(self):
        with (
            override_settings(
                STORAGES={
                    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                    "staticfiles": {
                        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
                    },
                }
            ),
            self.assertRaisesMessage(ImproperlyConfigured, 'STORAGES["vaalboks"]'),
        ):
            self.client.get("/api/files/")


class ClipboardTests(TestCase):
    def add(self, text: str) -> dict:
        response = self.client.post(
            "/api/clipboard/add/",
            data=json.dumps({"text": text}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        return response.json()["entry"]

    def test_entries_persist_in_database_newest_first_and_revision_changes(self):
        first = self.add("one")
        first_revision = self.client.get("/api/clipboard/").json()["revision"]
        second = self.add("two")
        response = self.client.get("/api/clipboard/")

        self.assertEqual(response.json()["entries"], [second, first])
        self.assertNotEqual(response.json()["revision"], first_revision)
        self.assertEqual(ClipboardEntry.objects.count(), 2)

    def test_blank_and_oversized_entries_are_rejected(self):
        response = self.client.post(
            "/api/clipboard/add/",
            data=json.dumps({"text": "   "}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        with patch("vaalboks.clipboard.MAX_ENTRY_BYTES", 2):
            response = self.client.post(
                "/api/clipboard/add/",
                data=json.dumps({"text": "long"}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 400)

    def test_entry_and_history_limits_are_enforced(self):
        with patch("vaalboks.clipboard.MAX_ENTRIES", 2):
            entries = [self.add(text) for text in ("one", "two", "three")]
        self.assertEqual(
            [entry["text"] for entry in self.client.get("/api/clipboard/").json()["entries"]],
            ["three", "two"],
        )
        self.assertFalse(ClipboardEntry.objects.filter(pk=entries[0]["id"]).exists())

        with patch("vaalboks.clipboard.MAX_HISTORY_BYTES", 1):
            self.add("another")
        self.assertEqual(self.client.get("/api/clipboard/").json()["entries"], [])

    def test_delete_and_clear_update_persistence_and_revision(self):
        entry = self.add("one")
        before_delete = self.client.get("/api/clipboard/").json()["revision"]
        self.assertEqual(self.client.post(f"/api/clipboard/{entry['id']}/delete/").status_code, 200)
        response = self.client.get("/api/clipboard/")
        self.assertEqual(response.json()["entries"], [])
        self.assertNotEqual(response.json()["revision"], before_delete)

        self.add("two")
        self.assertEqual(self.client.post("/api/clipboard/clear/").status_code, 200)
        self.assertEqual(ClipboardEntry.objects.count(), 0)
