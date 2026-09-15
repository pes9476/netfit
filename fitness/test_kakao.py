import time
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

import requests
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import KakaoAccount


@override_settings(KAKAO_REST_API_KEY="test-key", KAKAO_CLIENT_SECRET="test-secret")
class KakaoLoginTests(TestCase):
    def start(self):
        response = self.client.get(reverse("kakao_login"))
        return parse_qs(urlparse(response.url).query)["state"][0]

    def callback(self, state):
        return self.client.get(reverse("kakao_callback"), {"state": state, "code": "test-code"})

    def test_login_offers_both_methods(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, reverse("kakao_login"))
        self.assertContains(response, 'name="password"')
        self.assertContains(response, reverse("register"))

    @override_settings(KAKAO_REST_API_KEY="")
    def test_missing_configuration(self):
        self.assertRedirects(self.client.get(reverse("kakao_login")), reverse("login"))

    @patch("fitness.kakao.requests.post")
    def test_bad_state_expiry_and_replay(self, post):
        self.start()
        self.assertRedirects(self.callback("wrong"), reverse("login"))
        state = self.start()
        session = self.client.session
        pending = session["kakao_oauth"]
        pending["created"] = time.time() - 601
        session["kakao_oauth"] = pending
        session.save()
        self.assertRedirects(self.callback(state), reverse("login"))
        self.assertRedirects(self.callback(state), reverse("login"))
        post.assert_not_called()

    @patch("fitness.kakao.requests.post")
    def test_cancellation(self, post):
        state = self.start()
        response = self.client.get(reverse("kakao_callback"), {"state": state, "error": "access_denied"})
        self.assertRedirects(response, reverse("login"))
        post.assert_not_called()

    @patch("fitness.kakao.requests.post", side_effect=requests.Timeout)
    def test_network_failure(self, post):
        self.assertRedirects(self.callback(self.start()), reverse("login"))
        self.assertEqual(User.objects.count(), 0)

    @patch("fitness.kakao.requests.get")
    @patch("fitness.kakao.requests.post")
    def test_create_repeat_and_inactive_account(self, post, get):
        post.return_value = Mock(json=Mock(return_value={"access_token": "test-token"}))
        get.return_value = Mock(json=Mock(return_value={"id": 1234}))
        existing = User.objects.create_user(username="kakao_1234", password="existing-password")
        self.assertRedirects(self.callback(self.start()), reverse("profile"))
        account = KakaoAccount.objects.get(kakao_id="1234")
        self.assertNotEqual(account.user_id, existing.pk)
        self.assertFalse(account.user.has_usable_password())
        self.assertIsNotNone(account.user.profile)
        self.assertIsNotNone(account.user.charactercard)
        self.assertEqual(post.call_args.kwargs["data"]["client_secret"], "test-secret")
        self.assertEqual(account.user.profile.display_name, "")
        for page in ("profile", "dashboard", "battle", "friends"):
            response = self.client.get(reverse(page))
            self.assertNotContains(response, account.user.username)
            self.assertNotContains(response, ">운동친구<")
        response = self.client.post(reverse("profile"), {
            "nickname": "달리는친구", "area": "서울특별시", "gender": "N",
            "avatar_preference": "AUTO", "measured_on": "2026-09-14",
        })
        self.assertRedirects(response, reverse("profile"))
        account.user.refresh_from_db()
        self.assertEqual(account.user.username, "달리는친구")
        self.assertContains(self.client.get(reverse("dashboard")), "달리는친구")
        self.client.logout()
        self.assertRedirects(self.callback(self.start()), reverse("dashboard"))
        self.assertEqual(User.objects.count(), 2)
        self.client.logout()
        account.user.is_active = False
        account.user.save()
        self.assertRedirects(self.callback(self.start()), reverse("login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    @patch("fitness.kakao.requests.get")
    @patch("fitness.kakao.requests.post")
    def test_invalid_provider_identity(self, post, get):
        post.return_value = Mock(json=Mock(return_value={"access_token": "test-token"}))
        for data in ({}, {"id": None}, {"id": True}, {"id": -1}):
            get.return_value = Mock(json=Mock(return_value=data))
            self.assertRedirects(self.callback(self.start()), reverse("login"))
        self.assertEqual(User.objects.count(), 0)
