from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import DataSyncRun, Facility


class DataMonitorTests(TestCase):
    def setUp(self):
        self.url = reverse("admin:fitness_datasyncrun_changelist")
        self.admin = get_user_model().objects.create_superuser(
            username="monitor-admin", email="monitor@example.com", password="test-only"
        )

    def test_anonymous_and_unprivileged_staff_cannot_read_dashboard(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        staff = get_user_model().objects.create_user(username="staff", is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_empty_history_does_not_invent_counts(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertContains(response, "아직 동기화 이력이 없습니다")
        self.assertEqual(response.context["facility_stats"]["total"], 0)

    def test_real_counts_and_last_success_survive_no_change_run(self):
        self.client.force_login(self.admin)
        Facility.objects.create(name="활성 시설", is_active=True, latitude=37, longitude=127)
        Facility.objects.create(name="비활성 시설", is_active=False)
        success = DataSyncRun.objects.create(
            source_name="test", status="SUCCESS", source_count=10,
            created_count=6, updated_count=2, skipped_count=1, failed_count=1,
        )
        latest = DataSyncRun.objects.create(source_name="test", status="SKIPPED_NO_CHANGE")
        response = self.client.get(self.url)
        self.assertEqual(response.context["latest_success"], success)
        self.assertEqual(response.context["latest_run"], latest)
        self.assertEqual(response.context["facility_stats"],
                         {"total": 2, "active": 1, "inactive": 1, "located": 1})
        self.assertEqual([bar["count"] for bar in response.context["sync_bars"]], [6, 2, 1, 1])
        self.assertContains(response, "이전 성공 실행 기준")
        self.assertEqual(self.client.get(reverse("admin:fitness_datasyncrun_change", args=[success.pk])).status_code, 200)

    def test_history_is_read_only(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(reverse("admin:fitness_datasyncrun_add"), {}).status_code, 403)
