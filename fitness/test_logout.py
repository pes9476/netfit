from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse


class LogoutTests(TestCase):
    def test_logout_returns_public_home_and_clears_session(self):
        user = User.objects.create_user(username="logout-test", password="test-password")
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        dashboard = client.get(reverse("dashboard"))
        self.assertContains(dashboard, 'action="/logout/"')
        self.assertEqual(client.post(reverse("logout")).status_code, 403)
        response = client.post(reverse("logout"), {
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        }, follow=True)
        self.assertRedirects(response, reverse("dashboard"))
        self.assertTemplateUsed(response, "fitness/home.html")
        self.assertNotIn("_auth_user_id", client.session)
        self.assertContains(response, "로그인하고 시작하기")
        self.assertEqual(client.get(reverse("profile")).status_code, 302)

    def test_anonymous_home(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "fitness/home.html")
