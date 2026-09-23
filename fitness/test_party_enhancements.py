from datetime import date, timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from fitness.models import DailyQuest, Party, PartyInvitation
from fitness.services import generate_party_daily_missions


class PartyEnhancementsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password123")
        self.user.profile.area = "서울특별시"
        self.user.profile.workout_mode = "GROUP"
        self.user.profile.save()

        self.friend = User.objects.create_user(username="frienduser", password="password123")
        self.friend.profile.area = "서울특별시"
        self.friend.profile.workout_mode = "GROUP"
        self.friend.profile.save()

        self.party = Party.objects.create(
            name="러닝 파티",
            owner=self.user,
            workout_type="러닝",
            challenge_start=date.today(),
            challenge_end=date.today() + timedelta(days=7),
        )
        self.party.members.add(self.user, self.friend)

    def test_direct_quest_does_not_create_ai_missions(self):
        """직접 입력으로 파티 퀘스트 생성 시 AI 퀘스트가 자동 생성되지 않고 내가 만든 퀘스트만 유지된다."""
        q1 = DailyQuest.objects.create(
            party=self.party,
            creator=self.user,
            title="나의 직접입력 러닝 40분",
            workout_type="러닝",
            target_minutes=40,
            period_type="DAILY",
            mission_category="WORKOUT",
            source="DIRECT",
            quest_date=date.today(),
            is_active=True,
        )

        missions = generate_party_daily_missions(self.party)
        self.assertEqual(len(missions), 1)
        self.assertEqual(missions[0].id, q1.id)
        self.assertEqual(missions[0].source, "DIRECT")

        # DB에 AI 퀘스트가 일절 생성되지 않았는지 확인
        ai_count = DailyQuest.objects.filter(party=self.party, source="AI").count()
        self.assertEqual(ai_count, 0)

    def test_unlimited_party_quests_more_than_three(self):
        """3개 이후로도 퀘스트를 계속 만들 수 있고 강제로 3개로 잘리지 않는다."""
        for i in range(1, 6):
            DailyQuest.objects.create(
                party=self.party,
                creator=self.user,
                title=f"직접 미션 {i}",
                workout_type="러닝",
                target_minutes=20 + i * 5,
                period_type="DAILY",
                mission_category="WORKOUT",
                source="DIRECT",
                quest_date=date.today(),
                is_active=True,
            )

        missions = generate_party_daily_missions(self.party)
        self.assertEqual(len(missions), 5)
        titles = [m.title for m in missions]
        self.assertIn("직접 미션 1", titles)
        self.assertIn("직접 미션 5", titles)

    def test_onboarding_group_quest_continuous_add_and_delete(self):
        """onboarding_group_quest에서 'add_more'로 퀘스트 연속 추가 및 삭제 동작 검증"""
        self.client.login(username="testuser", password="password123")

        # 1. 미션 추가하고 계속 작성 (add_more)
        res1 = self.client.post(reverse("onboarding_group_quest", args=[self.party.id]), {
            "action": "direct",
            "submit_action": "add_more",
            "title": "연속 추가 미션 1",
            "workout_type": "러닝",
            "target_minutes": 30,
        })
        self.assertEqual(res1.status_code, 302)
        self.assertIn(reverse("onboarding_group_quest", args=[self.party.id]), res1.url)

        # 2. 두 번째 미션 추가
        self.client.post(reverse("onboarding_group_quest", args=[self.party.id]), {
            "action": "direct",
            "submit_action": "add_more",
            "title": "연속 추가 미션 2",
            "workout_type": "러닝",
            "target_minutes": 45,
        })

        self.assertEqual(DailyQuest.objects.filter(party=self.party, source="DIRECT").count(), 2)

        # 3. 미션 삭제
        q_to_del = DailyQuest.objects.filter(party=self.party, title="연속 추가 미션 1").first()
        res_del = self.client.post(reverse("onboarding_group_quest", args=[self.party.id]), {
            "action": "delete_quest",
            "quest_id": q_to_del.id,
        })
        self.assertEqual(res_del.status_code, 302)
        self.assertEqual(DailyQuest.objects.filter(party=self.party, source="DIRECT").count(), 1)

    def test_search_users_api(self):
        """전체 계정 닉네임/아이디 검색 API 정상 응답 및 미존재 시 '등록되지 않은 사용자' 메시지 검증"""
        self.client.login(username="testuser", password="password123")

        # 존재하는 유저 검색
        res = self.client.get(reverse("search_users_api"), {"q": "friend"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["username"], "frienduser")

        # 존재하지 않는 유저 검색
        res_none = self.client.get(reverse("search_users_api"), {"q": "nonexistent_xyz"})
        self.assertEqual(res_none.status_code, 200)
        data_none = res_none.json()
        self.assertEqual(data_none["count"], 0)
        self.assertIn("등록되지 않은 사용자", data_none["message"])

    def test_invite_unregistered_user_error_message(self):
        """대시보드 모달 및 파티 초대 시 등록되지 않은 사용자 에러 안내 검증"""
        self.client.login(username="testuser", password="password123")

        res = self.client.post(reverse("invite_party_member", args=[self.party.id]), {
            "friend_name": "없는사람닉네임",
        }, follow=True)

        messages = list(res.context["messages"])
        self.assertTrue(any("등록되지 않은 사용자입니다" in m.message for m in messages))
