from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class WebFlowTests(TestCase):
    """웹 우선 버전의 보호 페이지와 기존 경험치 지급 동작을 검증한다."""

    def test_anonymous_protected_pages(self):
        for path in (
            "/profile/", "/activity/", "/record/", "/ranking/", "/friends/",
            "/friends/add/", "/facilities/", "/region/", "/battle/",
            "/battle/create/", "/battle/1/", "/demo/level/", "/demo/battle/",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith("/login/?next="))

    def test_workout_xp_level_and_session_persist(self):
        user = User.objects.create_user(username="runner", password=None)
        self.client.force_login(user)
        card = user.charactercard
        card.xp = 290
        card.save()
        response = self.client.post(reverse("record_workout"), {
            "workout_type": "러닝", "minutes": 30, "distance_km": "3.00",
            "location": "공원", "next": "activity",
        })
        self.assertRedirects(response, reverse("activity"))
        card.refresh_from_db()
        self.assertEqual(card.level, 2)
        self.assertEqual(card.xp, 100)
        self.assertEqual(user.workoutrecord_set.get().earned_xp, 110)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))
