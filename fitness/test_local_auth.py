from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from .models import DailyQuest, FriendLink, Party


class LocalAuthTests(TestCase):
    def signup(self, **overrides):
        data = dict(username="newrunner", password1="Runner-test-934!", password2="Runner-test-934!", area="부산광역시")
        data.update(overrides)
        return self.client.post(reverse("register"), data)

    def test_registration_creates_profile_card_then_requires_login(self):
        self.assertContains(self.client.get(reverse("register")), 'name="password1"')
        self.assertRedirects(self.signup(), reverse("login"))
        user = User.objects.get(username="newrunner")
        self.assertTrue(user.check_password("Runner-test-934!"))
        self.assertEqual(user.profile.area, "부산광역시")
        self.assertEqual(user.charactercard.level, 1)
        self.assertNotIn("_auth_user_id", self.client.session)

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
        for target, expected in (("/activity/", "/activity/"), ("https://evil.example/", "/onboarding/"), ("//evil.example/", "/onboarding/")):
            self.client.logout()
            response = self.client.post(reverse("login"), {"username": "runner", "password": "test-password", "next": target})
            self.assertRedirects(response, expected, fetch_redirect_response=expected != "/onboarding/")
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

    def test_first_login_onboarding_sequence(self):
        user = User.objects.create_user(username="starter", password="test-password")
        response = self.client.post(reverse("login"), {"username": "starter", "password": "test-password"})
        self.assertRedirects(response, reverse("onboarding"), fetch_redirect_response=False)
        self.assertRedirects(self.client.get(reverse("onboarding")), reverse("onboarding_intro"))
        self.assertContains(self.client.get(reverse("onboarding_intro")), "프로필 등록하기")
        profile_data = {
            "nickname": "starter", "area": "서울특별시", "gender": "N",
            "avatar_preference": "ACTIVE", "measured_on": "2026-09-15",
            "rank_participation": "on",
        }
        self.assertRedirects(self.client.post(reverse("onboarding_profile"), profile_data), reverse("onboarding_mode"))
        profile_page = self.client.get(reverse("onboarding_profile"))
        self.assertContains(profile_page, "장애 여부")
        self.assertNotContains(profile_page, "골격근량")
        self.assertNotContains(profile_page, "체지방률")
        self.assertRedirects(self.client.post(reverse("onboarding_mode"), {"mode": "GROUP"}), reverse("onboarding_group"))
        friend = User.objects.create_user(username="workout_friend", password="test-password")
        FriendLink.objects.create(user=user, friend=friend)
        FriendLink.objects.create(user=friend, friend=user)
        response = self.client.post(reverse("onboarding_group"), {
            "action": "create_room", "room_name": "아침 운동방", "invitees": [friend.id],
            "challenge_start": "2026-09-16", "challenge_end": "2026-09-30",
        })
        party = Party.objects.get(name="아침 운동방")
        self.assertRedirects(response, reverse("onboarding_group_quest", args=[party.id]))
        self.assertEqual(set(party.members.values_list("id", flat=True)), {user.id, friend.id})
        self.assertRedirects(self.client.post(reverse("onboarding_group_quest", args=[party.id]), {
            "title": "오늘 30분 걷기", "workout_type": "걷기", "target_minutes": "30",
        }), reverse("dashboard"))
        user.profile.refresh_from_db()
        self.assertTrue(user.profile.onboarding_completed)
        self.assertEqual(user.profile.workout_mode, "GROUP")
        self.assertTrue(DailyQuest.objects.filter(party=party, title="오늘 30분 걷기").exists())
        self.assertRedirects(self.client.get(reverse("onboarding")), reverse("dashboard"))

    def test_solo_mode_finishes_guide_without_group_room(self):
        user = User.objects.create_user(username="solo", password="test-password")
        self.client.force_login(user)
        self.assertRedirects(
            self.client.post(reverse("onboarding_mode"), {"mode": "SOLO"}),
            reverse("onboarding_solo"),
        )
        self.assertRedirects(
            self.client.post(reverse("onboarding_solo"), {"action": "ai"}),
            reverse("dashboard"),
        )
        user.profile.refresh_from_db()
        self.assertTrue(user.profile.onboarding_completed)
        self.assertEqual(user.profile.workout_mode, "SOLO")
