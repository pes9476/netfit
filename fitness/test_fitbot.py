import json
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from fitness.models import Facility
from fitness.services import search_facilities_for_fitbot


@override_settings(GEMINI_API_KEY="test-gemini-key")
class FitbotTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testrunner", password="password123")
        self.bootstrap_url = reverse("fitbot_bootstrap")
        self.chat_url = reverse("fitbot_chat")

        # Create test facilities
        self.fac1 = Facility.objects.create(
            name="강남 러닝센터",
            facility_type="러닝",
            region="서울특별시",
            address="서울특별시 강남구 테헤란로 123",
            latitude=37.5,
            longitude=127.0,
            is_active=True,
        )
        self.fac2 = Facility.objects.create(
            name="서초 수영장",
            facility_type="수영",
            region="서울특별시",
            address="서울특별시 서초구 서초대로 456",
            is_active=True,
        )
        self.fac_inactive = Facility.objects.create(
            name="폐쇄된 체육관",
            facility_type="헬스",
            region="서울특별시",
            address="서울특별시 강남구 역삼로 789",
            is_active=False,
        )

    def test_search_facilities_for_fitbot_service(self):
        # 1. Search by region and query
        results = search_facilities_for_fitbot(region="서울특별시", query="러닝")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "강남 러닝센터")
        self.assertTrue(results[0]["url"])

        # 2. Inactive facilities excluded
        inactive_results = search_facilities_for_fitbot(region="서울특별시", query="폐쇄")
        self.assertEqual(len(inactive_results), 0)

        # 3. Search all in region
        all_seoul = search_facilities_for_fitbot(region="서울특별시", query="")
        self.assertEqual(len(all_seoul), 2)

    def test_bootstrap_anonymous_403(self):
        response = self.client.get(self.bootstrap_url)
        self.assertEqual(response.status_code, 403)
        self.assertIn("error", response.json())

    def test_bootstrap_authenticated_200(self):
        self.client.login(username="testrunner", password="password123")
        response = self.client.get(self.bootstrap_url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("csrf_token", data)
        self.assertIn("regions", data)
        self.assertIn("서울특별시", data["regions"])

    def test_chat_anonymous_403(self):
        response = self.client.post(
            self.chat_url,
            data=json.dumps({"role": "coach", "message": "안녕"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_chat_oversized_payload_413(self):
        self.client.login(username="testrunner", password="password123")
        large_text = "x" * 13000
        response = self.client.post(
            self.chat_url,
            data=large_text,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 413)

    def test_chat_invalid_role_400(self):
        self.client.login(username="testrunner", password="password123")
        response = self.client.post(
            self.chat_url,
            data=json.dumps({"role": "unknown_role", "message": "안녕"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_chat_empty_message_400(self):
        self.client.login(username="testrunner", password="password123")
        response = self.client.post(
            self.chat_url,
            data=json.dumps({"role": "coach", "message": "   "}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    @patch("fitness.fitbot_api.requests.post")
    def test_chat_coach_success(self, mock_post):
        self.client.login(username="testrunner", password="password123")
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "오늘 30분 러닝 어때요? 파이팅입니다!"}]}}]
        }
        mock_post.return_value = mock_response

        payload = {
            "role": "coach",
            "message": "오늘 어떤 운동 할까?",
            "history": [{"role": "user", "text": "안녕"}],
        }
        response = self.client.post(
            self.chat_url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["reply"], "오늘 30분 러닝 어때요? 파이팅입니다!")
        self.assertEqual(data["facilities"], [])

    @patch("fitness.fitbot_api.requests.post")
    def test_chat_facility_with_database_results(self, mock_post):
        self.client.login(username="testrunner", password="password123")
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "서울특별시 강남구에 강남 러닝센터가 등록되어 있어요!"}]}}]
        }
        mock_post.return_value = mock_response

        payload = {
            "role": "facility",
            "region": "서울특별시",
            "query": "러닝",
            "message": "서울특별시 러닝 시설 찾아줘",
        }
        response = self.client.post(
            self.chat_url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["reply"], "서울특별시 강남구에 강남 러닝센터가 등록되어 있어요!")
        self.assertEqual(len(data["facilities"]), 1)
        self.assertEqual(data["facilities"][0]["name"], "강남 러닝센터")

    def test_chat_facility_no_results(self):
        self.client.login(username="testrunner", password="password123")
        payload = {
            "role": "facility",
            "region": "서울특별시",
            "query": "존재하지않는시설검색어123",
            "message": "시설 찾아줘",
        }
        response = self.client.post(
            self.chat_url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("등록된 시설을 찾지 못했어요", data["reply"])
        self.assertEqual(data["facilities"], [])

    @override_settings(GEMINI_API_KEY="")
    def test_chat_missing_gemini_key_503(self):
        self.client.login(username="testrunner", password="password123")
        payload = {
            "role": "coach",
            "message": "운동 추천해줘",
        }
        response = self.client.post(
            self.chat_url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 503)
        self.assertIn("AI 연결 설정이 필요합니다", response.json()["error"])

    @patch("fitness.fitbot_api.requests.post")
    def test_chat_rate_limit_429(self, mock_post):
        self.client.login(username="testrunner", password="password123")
        mock_post.return_value = MagicMock(status_code=429)

        payload = {
            "role": "meal",
            "message": "식단 조언해줘",
        }
        response = self.client.post(
            self.chat_url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 429)
        self.assertIn("무료 이용 한도에 도달했어요", response.json()["error"])
