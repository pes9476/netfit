from datetime import timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import BadgeAward, Facility, OutfitPurchase, PersonalDailyQuest, WorkoutRecord


class WebFlowTests(TestCase):
    """웹 우선 버전의 보호 페이지와 배지 지급 동작을 검증한다."""

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

    def test_workout_awards_silver_badge_and_session_persists(self):
        user = User.objects.create_user(username="runner", password=None)
        self.client.force_login(user)
        response = self.client.post(reverse("record_workout"), {
            "workout_type": "러닝", "minutes": 30, "distance_km": "3.00",
            "location": "공원", "next": "activity",
        })
        self.assertRedirects(response, reverse("activity"))
        record = user.workoutrecord_set.get()
        self.assertEqual(record.earned_xp, 0)
        self.assertEqual(record.badge_award.badge_type, BadgeAward.SILVER)
        self.assertEqual(record.badge_award.points, 50)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))

    def test_custom_workout_name_can_be_recorded(self):
        user = User.objects.create_user(username="custom-runner", password=None)
        self.client.force_login(user)
        response = self.client.post(reverse("record_workout"), {
            "workout_type": "기타", "custom_workout_name": "러닝 만보",
            "minutes": 60, "distance_km": "10.00", "next": "activity",
        })
        self.assertRedirects(response, reverse("activity"))
        record = user.workoutrecord_set.get()
        self.assertEqual(record.custom_workout_name, "러닝 만보")
        self.assertEqual(record.workout_name, "러닝 만보")
        self.assertContains(self.client.get(reverse("activity")), "러닝 만보")

    def test_workout_form_uses_running_walk_and_custom_choices(self):
        user = User.objects.create_user(username="choice-runner", password=None)
        self.client.force_login(user)
        response = self.client.get(reverse("activity"))
        choices = list(response.context["workout_form"].fields["workout_type"].choices)
        self.assertEqual([label for _, label in choices], [
            "러닝", "산책", "수영", "배드민턴", "자전거", "헬스",
            "등산", "축구", "농구", "요가", "직접입력",
        ])

    def test_badge_points_can_buy_and_equip_outfit(self):
        user = User.objects.create_user(username="shopper", password=None)
        self.client.force_login(user)
        for _ in range(2):
            self.client.post(reverse("record_workout"), {
                "workout_type": "러닝", "minutes": 60, "distance_km": "5", "next": "activity",
            })
        response = self.client.post(reverse("outfit_shop"), {"action": "buy", "outfit": "CAP"})
        self.assertRedirects(response, reverse("outfit_shop"))
        self.assertTrue(OutfitPurchase.objects.filter(user=user, outfit="CAP", cost=150).exists())
        self.client.post(reverse("outfit_shop"), {"action": "equip", "outfit": "CAP"})
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.equipped_outfit, "CAP")
        self.assertContains(self.client.get(reverse("dashboard")), "outfit-cap")

    def test_daily_quest_badge_is_awarded_only_once(self):
        user = User.objects.create_user(username="quest-runner", password=None)
        quest = PersonalDailyQuest.objects.create(
            user=user, title="한 시간 러닝", workout_type="러닝", target_minutes=60,
        )
        self.client.force_login(user)
        url = reverse("complete_daily_quest", args=["personal", quest.id])
        self.client.post(url)
        self.client.post(url)
        award = BadgeAward.objects.get(user=user, personal_quest=quest)
        self.assertEqual(award.badge_type, BadgeAward.GOLD)
        self.assertEqual(award.points, 100)
        self.assertEqual(BadgeAward.objects.filter(user=user, personal_quest=quest).count(), 1)
        dashboard = self.client.get(reverse("dashboard"))
        self.assertContains(dashboard, "한 시간 러닝")
        self.assertContains(dashboard, "완료")

    def test_profile_contains_workout_analytics(self):
        user = User.objects.create_user(username="analytics", password=None)
        WorkoutRecord.objects.create(user=user, workout_type="러닝", minutes=30, earned_xp=100)
        WorkoutRecord.objects.create(user=user, workout_type="수영", minutes=45, earned_xp=120)
        old = WorkoutRecord.objects.create(user=user, workout_type="걷기", minutes=20, earned_xp=50)
        WorkoutRecord.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=30))
        self.client.force_login(user)
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.context["workout_totals"], {"workouts": 3, "minutes": 95, "points": 0})
        self.assertEqual(sum(row["minutes"] for row in response.context["daily_chart"]), 75)
        self.assertContains(response, "daily-workout-data")

    def test_dashboard_uses_nickname_without_stats_or_tier(self):
        user = User.objects.create_user(username="내캐릭터이름", password=None)
        self.client.force_login(user)
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "내캐릭터이름")
        self.assertNotContains(response, "속도<b>", html=False)
        self.assertNotContains(response, "지구력<b>", html=False)
        self.assertNotContains(response, '<small class="tier-badge">', html=False)

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

    def test_facilities_can_sort_from_current_location(self):
        user = User.objects.create_user(username="nearby", password=None)
        Facility.objects.create(name="가까운 체육관", region=user.profile.area, latitude=37.5005, longitude=127.0005)
        Facility.objects.create(name="먼 체육관", region=user.profile.area, latitude=37.8, longitude=127.5)
        self.client.force_login(user)
        response = self.client.get(reverse("facilities"), {"lat": "37.5", "lon": "127.0"})
        self.assertContains(response, "현재 위치에서 가까운 시설")
        self.assertLess(response.content.find("가까운 체육관".encode()), response.content.find("먼 체육관".encode()))
