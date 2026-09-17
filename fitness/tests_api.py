from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import MissionParticipant


class NetFitAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="runner", password="strong-pass-123")
        self.client.force_authenticate(self.user)

    def test_profile_update_returns_bmi(self):
        response = self.client.patch("/api/v1/profile/me/", {
            "nickname": "runner-new", "age": 25, "height_cm": "170.0", "weight_kg": "68.0",
            "preferred_activity_mode": "SOLO", "onboarding_completed": True,
        }, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["bmi"], 23.5)

    def test_workout_awards_xp_and_summary(self):
        response = self.client.post("/api/v1/workouts/", {
            "workout_type": "러닝", "minutes": 30, "distance_km": "5.00", "with_party": False,
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["earned_xp"], 130)
        self.user.charactercard.refresh_from_db()
        self.assertEqual(self.user.charactercard.xp, 130)
        self.assertEqual(self.client.get("/api/v1/workouts/summary/").data[0]["minutes"], 30)

    def test_group_mission_and_two_person_battle_flow(self):
        friend = User.objects.create_user(username="friend", password="strong-pass-123")
        group = self.client.post("/api/v1/groups/", {"name": "러닝팀", "goal_km": 30, "max_members": 2}, format="json")
        self.assertEqual(group.status_code, 201)

        self.client.force_authenticate(friend)
        self.assertEqual(self.client.post(f"/api/v1/groups/{group.data['id']}/join/", {}, format="json").status_code, 200)

        self.client.force_authenticate(self.user)
        mission = self.client.post("/api/v1/missions/", {
            "party": group.data["id"], "mode": "GROUP", "title": "매일 30분 걷기", "target_count": 3,
            "starts_at": timezone.now().isoformat(), "ends_at": (timezone.now() + timedelta(days=7)).isoformat(),
        }, format="json")
        self.assertEqual(mission.status_code, 201, mission.data)
        self.assertEqual(MissionParticipant.objects.filter(mission_id=mission.data["id"]).count(), 2)

        battle = self.client.post("/api/v1/battles/", {
            "mission": mission.data["id"], "title": "친구 배틀", "capacity": 2, "penalty": "커피 사기",
        }, format="json")
        self.assertEqual(battle.status_code, 201, battle.data)

        self.client.force_authenticate(friend)
        joined = self.client.post(f"/api/v1/battles/{battle.data['id']}/join/", {"team": 2}, format="json")
        self.assertEqual(joined.status_code, 200)
        self.assertEqual(joined.data["status"], "ACTIVE")

    def test_anonymous_api_is_rejected(self):
        self.client.force_authenticate(user=None)
        self.assertIn(self.client.get("/api/v1/profile/me/").status_code, (401, 403))
