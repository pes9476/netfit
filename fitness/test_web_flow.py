from datetime import timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Facility, WorkoutRecord


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

    def test_profile_contains_workout_analytics(self):
        user = User.objects.create_user(username="analytics", password=None)
        WorkoutRecord.objects.create(user=user, workout_type="러닝", minutes=30, earned_xp=100)
        WorkoutRecord.objects.create(user=user, workout_type="수영", minutes=45, earned_xp=120)
        old = WorkoutRecord.objects.create(user=user, workout_type="걷기", minutes=20, earned_xp=50)
        WorkoutRecord.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=30))
        self.client.force_login(user)
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.context["workout_totals"], {"workouts": 3, "minutes": 95, "xp": 270})
        self.assertEqual(sum(row["minutes"] for row in response.context["daily_chart"]), 75)
        self.assertContains(response, "daily-workout-data")

    def test_facility_search_category_and_naver_link(self):
        user = User.objects.create_user(username="searcher", password=None)
        Facility.objects.create(name="시민 야구장", facility_type="야구장", region=user.profile.area, address="서울시 운동로 1", longitude=127.1, latitude=37.5)
        Facility.objects.create(name="푸른 수영장", facility_type="수영장", region=user.profile.area)
        self.client.force_login(user)
        response = self.client.get(reverse("facilities"), {"category": "baseball"})
        self.assertContains(response, "시민 야구장")
        self.assertNotContains(response, "푸른 수영장")
        self.assertContains(response, "https://map.naver.com/p/directions/-/127.1,37.5")
        response = self.client.get(reverse("facilities"), {"q": "수영"})
        self.assertContains(response, "푸른 수영장")
        self.assertNotContains(response, "시민 야구장")
