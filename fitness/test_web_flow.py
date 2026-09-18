from datetime import timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import (
    BadgeAward, DailyQuest, Facility, FriendLink, FriendRequest,
    OutfitPurchase, Party, PartyInvitation, PersonalDailyQuest, WorkoutRecord,
)


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

    def test_workout_awards_bronze_badge_and_session_persists(self):
        user = User.objects.create_user(username="runner", password=None)
        self.client.force_login(user)
        response = self.client.post(reverse("record_workout"), {
            "workout_type": "러닝", "minutes": 30, "distance_km": "3.00",
            "location": "공원", "next": "activity",
        })
        self.assertRedirects(response, reverse("activity"))
        record = user.workoutrecord_set.get()
        self.assertEqual(record.earned_xp, 0)
        self.assertEqual(record.badge_award.badge_type, BadgeAward.BRONZE)
        self.assertEqual(record.badge_award.points, 30)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))

        # 60분 은메달 & 90분 금메달 테스트
        self.assertEqual(BadgeAward.badge_for_minutes(60), BadgeAward.SILVER)
        self.assertEqual(BadgeAward.badge_for_minutes(90), BadgeAward.GOLD)

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
                "workout_type": "러닝", "minutes": 90, "distance_km": "5", "next": "activity",
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
            user=user, title="1시간 30분 러닝", workout_type="러닝", target_minutes=90,
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
        self.assertContains(dashboard, "1시간 30분 러닝")
        self.assertContains(dashboard, "완료")

    def test_daily_quest_with_proof_image_serves_media_and_renders_modal_btn(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        user = User.objects.create_user(username="photo-runner", password=None)
        quest = PersonalDailyQuest.objects.create(
            user=user, title="30분 산책", workout_type="산책", target_minutes=30,
        )
        self.client.force_login(user)
        test_image = SimpleUploadedFile(name="test_proof.jpg", content=b"\x47\x49\x46\x38\x39\x61", content_type="image/jpeg")
        url = reverse("complete_daily_quest", args=["personal", quest.id])
        resp = self.client.post(url, {"proof_image": test_image})
        self.assertRedirects(resp, reverse("dashboard"))
        award = BadgeAward.objects.get(user=user, personal_quest=quest)
        self.assertTrue(award.proof_image)
        self.assertTrue(award.proof_image.name.startswith("quest_proofs/"))
        dashboard = self.client.get(reverse("dashboard"))
        self.assertContains(dashboard, "등록된 인증 사진 보기")
        self.assertContains(dashboard, f"openProofModal('{award.proof_image.url}', 'personal', '{quest.id}')")
        # Check media URL serving
        media_resp = self.client.get(award.proof_image.url)
        self.assertEqual(media_resp.status_code, 200)

        # 2. 사진 변경 테스트
        new_image = SimpleUploadedFile(name="updated_proof.jpg", content=b"\x47\x49\x46\x38\x39\x61_updated", content_type="image/jpeg")
        resp2 = self.client.post(url, {"proof_image": new_image})
        self.assertRedirects(resp2, reverse("dashboard"))
        award.refresh_from_db()
        self.assertTrue("updated_proof" in award.proof_image.name)

        # 3. 사진 삭제(X) 테스트
        resp3 = self.client.post(url, {"action": "delete_proof"})
        self.assertRedirects(resp3, reverse("dashboard"))
        award.refresh_from_db()
        self.assertFalse(bool(award.proof_image))
        # 점수와 배지는 그대로 보존됨
        self.assertEqual(award.badge_type, BadgeAward.BRONZE)
        dashboard_after_del = self.client.get(reverse("dashboard"))
        self.assertContains(dashboard_after_del, "인증 사진 추가하기")


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
        self.assertContains(response, "https://map.kakao.com/link/to/")
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

    def test_activity_recommends_nearby_public_facilities(self):
        user = User.objects.create_user(username="activity-nearby", password=None)
        Facility.objects.create(name="가까운 운동장", region=user.profile.area, latitude=37.5002, longitude=127.0002)
        Facility.objects.create(name="먼 운동장", region=user.profile.area, latitude=37.9, longitude=127.8)
        self.client.force_login(user)
        response = self.client.get(reverse("activity"), {"lat": "37.5", "lon": "127.0"})
        self.assertContains(response, "내 주변 공공체육시설 추천")
        self.assertLess(response.content.find("가까운 운동장".encode()), response.content.find("먼 운동장".encode()))

    def test_daily_quest_completion_creates_workout_record_and_displays_in_feed(self):
        user = User.objects.create_user(username="quest_logger", password=None)
        quest = PersonalDailyQuest.objects.create(
            user=user, title="저녁 45분 러닝", workout_type="러닝", target_minutes=45,
        )
        self.client.force_login(user)
        url = reverse("complete_daily_quest", args=["personal", quest.id])
        res = self.client.post(url)
        self.assertRedirects(res, reverse("dashboard"))

        # WorkoutRecord 자동 생성 확인
        record = WorkoutRecord.objects.filter(user=user, location="일일미션 달성").first()
        self.assertIsNotNone(record)
        self.assertEqual(record.workout_type, "러닝")
        self.assertEqual(record.minutes, 45)
        self.assertIsNotNone(record.badge_award)

        # 대시보드 최근 운동 피드 확인
        dashboard = self.client.get(reverse("dashboard"))
        self.assertContains(dashboard, "저녁 45분 러닝")

        # 운동 기록(activity) 페이지 최근 운동 피드 확인
        activity = self.client.get(reverse("activity"))
        self.assertContains(activity, "최근 운동 기록")
        self.assertContains(activity, "일일미션 달성")

    def test_friend_request_flow_and_friends_page_rendering(self):
        user1 = User.objects.create_user(username="alice", password=None)
        user2 = User.objects.create_user(username="bob", password=None)

        # 1. alice가 bob에게 친구 요청 발송
        self.client.force_login(user1)
        res = self.client.post(reverse("add_friend"), {"friend_code": "bob"})
        self.assertRedirects(res, reverse("friends"))

        freq = FriendRequest.objects.get(from_user=user1, to_user=user2)
        self.assertEqual(freq.status, "PENDING")
        self.assertFalse(FriendLink.objects.filter(user=user1, friend=user2).exists())

        # 친구 목록 페이지에 '카드 배틀' 버튼이 없어야 함
        friends_page = self.client.get(reverse("friends"))
        self.assertNotContains(friends_page, "카드 배틀")
        self.assertContains(friends_page, "bob")

        # 2. bob 로그인 시 대시보드 및 친구 페이지에서 친구 요청 알림 확인
        self.client.force_login(user2)
        bob_dash = self.client.get(reverse("dashboard"))
        self.assertContains(bob_dash, "alice")
        self.assertContains(bob_dash, "친구 요청")

        bob_friends = self.client.get(reverse("friends"))
        self.assertContains(bob_friends, "받은 친구 요청")
        self.assertContains(bob_friends, "alice")

        # 3. bob이 수락
        accept_res = self.client.post(reverse("respond_friend_request", args=[freq.id, "accept"]))
        self.assertRedirects(accept_res, reverse("dashboard"))

        freq.refresh_from_db()
        self.assertEqual(freq.status, "ACCEPTED")
        self.assertTrue(FriendLink.objects.filter(user=user1, friend=user2).exists())
        self.assertTrue(FriendLink.objects.filter(user=user2, friend=user1).exists())

    def test_party_invitation_flow_and_dashboard_monitoring(self):
        creator = User.objects.create_user(username="host", password=None)
        guest = User.objects.create_user(username="guest", password=None)
        FriendLink.objects.create(user=creator, friend=guest)
        FriendLink.objects.create(user=guest, friend=creator)

        # 파티 생성 및 초대
        self.client.force_login(creator)
        res = self.client.post(reverse("onboarding_group"), {
            "action": "create_room", "room_name": "주말 라이딩", "invitees": [guest.id],
            "challenge_start": "2026-09-18", "challenge_end": "2026-09-25",
        })
        party = Party.objects.get(name="주말 라이딩")
        inv = PartyInvitation.objects.get(party=party, invitee=guest)
        self.assertEqual(inv.status, "PENDING")
        self.assertNotIn(guest, party.members.all())

        # 일일 미션 생성
        DailyQuest.objects.create(
            party=party, creator=creator, title="자전거 60분", workout_type="자전거", target_minutes=60,
        )

        # guest 로그인: 대시보드에 파티 초대 알림 표시
        self.client.force_login(guest)
        guest_dash = self.client.get(reverse("dashboard"))
        self.assertContains(guest_dash, "파티 초대")
        self.assertContains(guest_dash, "주말 라이딩")

        # guest 수락
        accept_res = self.client.post(reverse("respond_party_invitation", args=[inv.id, "accept"]))
        self.assertRedirects(accept_res, reverse("dashboard"))
        self.assertIn(guest, party.members.all())

        # 호스트 대시보드에서 파티원 모니터링 확인
        self.client.force_login(creator)
        host_dash = self.client.get(reverse("dashboard"))
        self.assertContains(host_dash, "파티원 오늘 미션 현황")
        self.assertContains(host_dash, "도전 중 ⏱️")

    def test_dashboard_region_ranking_link_and_time_category_chips(self):
        user = User.objects.create_user(username="tester", password=None)
        self.client.force_login(user)

        # 1. 대시보드 전국랭킹 -> 지역랭킹 확인
        dashboard = self.client.get(reverse("dashboard"))
        self.assertContains(dashboard, "지역 랭킹")
        self.assertContains(dashboard, f"{reverse('ranking')}?scope=region")

        # 2. 솔로 온보딩 시간 카테고리 칩 확인
        solo = self.client.get(reverse("onboarding_solo"))
        self.assertContains(solo, "30분")
        self.assertContains(solo, "1시간")
        self.assertContains(solo, "1시간 30분")
        self.assertContains(solo, "직접입력")

        # 3. 파티 온보딩 버튼 문구 확인
        group = self.client.get(reverse("onboarding_group"))
        self.assertContains(group, "파티미션설정 →")
