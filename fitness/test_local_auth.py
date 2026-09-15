from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse


class LocalAuthTests(TestCase):
    def signup(self, **overrides):
        data = dict(username="newrunner", password1="Runner-test-934!", password2="Runner-test-934!", area="부산광역시")
        data.update(overrides)
        return self.client.post(reverse("register"), data)

    def test_registration_creates_profile_card_and_session(self):
        self.assertContains(self.client.get(reverse("register")), 'name="password1"')
        self.assertRedirects(self.signup(), reverse("profile"))
        user = User.objects.get(username="newrunner")
        self.assertTrue(user.check_password("Runner-test-934!"))
        self.assertEqual(user.profile.area, "부산광역시")
        self.assertEqual(user.charactercard.level, 1)
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))

    def test_invalid_registration_does_not_create_user(self):
        for overrides in ({"password2": "mismatch"}, {"area": "invalid"}):
            response = self.signup(**overrides)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
            self.assertFalse(User.objects.exists())
        User.objects.create_user(username="newrunner", password="existing")
        response = self.signup()
        self.assertIn("username", response.context["form"].errors)
        self.assertEqual(User.objects.count(), 1)

    def test_login_and_safe_redirect(self):
        user = User.objects.create_user(username="runner", password="test-password")
        for target, expected in (("/activity/", "/activity/"), ("https://evil.example/", "/"), ("//evil.example/", "/")):
            self.client.logout()
            response = self.client.post(reverse("login"), {"username": "runner", "password": "test-password", "next": target})
            self.assertRedirects(response, expected)
            self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))
        for page in ("register", "login"):
            self.assertRedirects(self.client.get(reverse(page)), reverse("dashboard"))

    def test_invalid_inactive_and_social_password_login(self):
        user = User.objects.create_user(username="runner", password="test-password")
        for password in ("wrong", ""):
            response = self.client.post(reverse("login"), {"username": user.username, "password": password})
            self.assertTrue(response.context["form"].errors)
            self.assertNotIn("_auth_user_id", self.client.session)
        user.is_active = False
        user.save()
        response = self.client.post(reverse("login"), {"username": user.username, "password": "test-password"})
        self.assertTrue(response.context["form"].errors)
        user.is_active = True
        user.set_unusable_password()
        user.save()
        self.client.post(reverse("login"), {"username": user.username, "password": "test-password"})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_csrf_required(self):
        client = Client(enforce_csrf_checks=True)
        for page in ("register", "login"):
            self.assertEqual(client.post(reverse(page), {}).status_code, 403)
