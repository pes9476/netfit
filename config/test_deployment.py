import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import OperationalError
from django.test import TestCase, override_settings


class DeploymentTests(TestCase):
    def test_healthcheck_reports_database_failure_without_details(self):
        self.assertEqual(self.client.get("/healthz/").status_code, 200)
        with patch("config.deployment_views.connection.cursor", side_effect=OperationalError("secret")):
            response = self.client.get("/healthz/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_healthcheck_accepts_http_but_pages_redirect_to_https(self):
        self.assertEqual(self.client.get("/healthz/").status_code, 200)
        self.assertEqual(self.client.get("/login/").status_code, 301)

    def test_media_requires_login_and_stays_inside_media_root(self):
        self.assertEqual(self.client.get("/media/photo.png").status_code, 302)
        self.client.force_login(User.objects.create_user("media-test"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "media"
            root.mkdir()
            (root / "photo.png").write_bytes(b"image")
            (Path(directory) / "outside.png").write_bytes(b"outside")
            (root / "unsafe.html").write_text("<script>alert(1)</script>")
            with override_settings(MEDIA_ROOT=root):
                response = self.client.get("/media/photo.png")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(b"".join(response.streaming_content), b"image")
                response.close()
                self.assertEqual(self.client.get("/media/../outside.png").status_code, 404)
                self.assertEqual(self.client.get("/media/unsafe.html").status_code, 404)
                self.assertEqual(self.client.get("/media/config/settings.py").status_code, 404)
