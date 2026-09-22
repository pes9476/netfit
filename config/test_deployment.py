import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import OperationalError
from django.test import SimpleTestCase, TestCase, override_settings


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


class RenderSettingsTests(SimpleTestCase):
    def test_render_hostname_and_secure_defaults_are_detected(self):
        environment = os.environ.copy()
        for name in ("USE_SQLITE", "RAILWAY_ENVIRONMENT_ID", "RAILWAY_PUBLIC_DOMAIN"):
            environment.pop(name, None)
        environment.update({
            "RENDER": "true",
            "RENDER_EXTERNAL_HOSTNAME": "netfit-test.onrender.com",
            "DEBUG": "False",
            "SECRET_KEY": "render-settings-test-only",
            "DATABASE_URL": "postgresql://user:password@localhost:5432/netfit",
            "ALLOWED_HOSTS": "",
            "CSRF_TRUSTED_ORIGINS": "",
        })
        script = """
import json
from config import settings
print(json.dumps({
    "on_render": settings.ON_RENDER,
    "allowed_hosts": settings.ALLOWED_HOSTS,
    "csrf": settings.CSRF_TRUSTED_ORIGINS,
    "ssl_redirect": settings.SECURE_SSL_REDIRECT,
    "session_secure": settings.SESSION_COOKIE_SECURE,
    "csrf_secure": settings.CSRF_COOKIE_SECURE,
}))
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).resolve().parent.parent,
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        )
        values = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertTrue(values["on_render"])
        self.assertIn("netfit-test.onrender.com", values["allowed_hosts"])
        self.assertIn("https://netfit-test.onrender.com", values["csrf"])
        self.assertTrue(values["ssl_redirect"])
        self.assertTrue(values["session_secure"])
        self.assertTrue(values["csrf_secure"])
