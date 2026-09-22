import csv
import io
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase

from .facility_sync import facility_source_record_id, redact_error_summary, sanitize_source_url
from .models import DataSyncRun, Facility


CSV_COLUMNS = [
    "SOURCE_RECORD_ID",
    "FCLTY_NM",
    "FCLTY_TY_NM",
    "ROAD_NM_CTPRVN_NM",
    "POSESN_MBY_CTPRVN_NM",
    "RDNMADR_NM",
    "FCLTY_LO",
    "FCLTY_LA",
    "FCLTY_HMPG_URL",
    "DEL_AT",
]


def facility_row(**values):
    row = {
        "SOURCE_RECORD_ID": "facility-1",
        "FCLTY_NM": "시민 체육관",
        "FCLTY_TY_NM": "체육관",
        "ROAD_NM_CTPRVN_NM": "서울특별시",
        "POSESN_MBY_CTPRVN_NM": "",
        "RDNMADR_NM": "서울시 운동로 1",
        "FCLTY_LO": "127.01",
        "FCLTY_LA": "37.51",
        "FCLTY_HMPG_URL": "https://example.com/facility",
        "DEL_AT": "N",
    }
    row.update(values)
    return row


class FacilityCommandTestMixin:
    def write_csv(self, rows, columns=CSV_COLUMNS, name="facilities.csv"):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / name
        with path.open("w", encoding="utf-8-sig", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        return path


class ImportFacilitiesTests(FacilityCommandTestMixin, TestCase):
    def test_valid_region_is_saved_and_deleted_row_is_skipped(self):
        path = self.write_csv([
            facility_row(),
            facility_row(SOURCE_RECORD_ID="facility-2", FCLTY_NM="삭제 시설", DEL_AT="Y"),
        ])

        call_command("import_facilities", path, stdout=io.StringIO(), stderr=io.StringIO())

        self.assertEqual(Facility.objects.count(), 1)
        self.assertEqual(Facility.objects.get().region, "서울특별시")

    def test_unsupported_region_is_not_saved_as_seoul(self):
        path = self.write_csv([facility_row(ROAD_NM_CTPRVN_NM="지원하지않는지역")])
        errors = io.StringIO()

        call_command("import_facilities", path, stdout=io.StringIO(), stderr=errors)

        self.assertFalse(Facility.objects.exists())
        self.assertIn("지원하지 않는 지역", errors.getvalue())


class FacilityIdentityTests(TestCase):
    def test_normalized_fallback_identity_is_stable(self):
        first = facility_row(SOURCE_RECORD_ID="", FCLTY_NM=" 시민   체육관 ")
        second = facility_row(SOURCE_RECORD_ID="", FCLTY_NM="시민 체육관")
        self.assertEqual(facility_source_record_id(first), facility_source_record_id(second))

    def test_database_constraint_rejects_duplicate_source_id(self):
        values = {"source_record_id": "duplicate", "name": "A", "region": "서울특별시"}
        Facility.objects.create(**values)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Facility.objects.create(**values)

    def test_source_url_drops_credentials_query_and_fragment(self):
        sanitized = sanitize_source_url("https://user:secret@example.com/data.csv?token=secret#part")
        self.assertEqual(sanitized, "https://example.com/data.csv")

    def test_error_summary_redacts_database_urls_and_tokens(self):
        summary = redact_error_summary(
            "postgresql://user:password@example.com/db token=private-value"
        )
        self.assertNotIn("password", summary)
        self.assertNotIn("private-value", summary)
        self.assertIn("[redacted]", summary)


class SyncFacilitiesTests(FacilityCommandTestMixin, TestCase):
    def run_sync(self, path, **options):
        output = io.StringIO()
        call_command("sync_facilities", source_path=str(path), stdout=output, **options)
        return output.getvalue()

    def test_first_load_records_success_and_counts(self):
        path = self.write_csv([facility_row()])

        self.run_sync(path)

        run = DataSyncRun.objects.get()
        self.assertEqual(run.status, DataSyncRun.STATUS_SUCCESS)
        self.assertEqual((run.source_count, run.created_count, run.updated_count), (1, 1, 0))
        self.assertIsNotNone(run.finished_at)
        self.assertEqual(Facility.objects.count(), 1)

    def test_same_checksum_is_skipped_without_new_facilities(self):
        path = self.write_csv([facility_row()])
        self.run_sync(path)

        self.run_sync(path)

        self.assertEqual(Facility.objects.count(), 1)
        self.assertEqual(
            DataSyncRun.objects.filter(status=DataSyncRun.STATUS_SKIPPED_NO_CHANGE).count(), 1,
        )

    def test_same_explicit_source_id_updates_name(self):
        first = self.write_csv([facility_row(FCLTY_NM="변경 전")], name="source.csv")
        self.run_sync(first)
        second = self.write_csv([facility_row(FCLTY_NM="변경 후")], name="source.csv")

        self.run_sync(second)

        self.assertEqual(Facility.objects.count(), 1)
        self.assertEqual(Facility.objects.get().name, "변경 후")
        self.assertEqual(DataSyncRun.objects.latest("started_at").updated_count, 1)

    def test_different_source_ids_create_separate_facilities(self):
        path = self.write_csv([
            facility_row(SOURCE_RECORD_ID="one", FCLTY_NM="시설 1"),
            facility_row(SOURCE_RECORD_ID="two", FCLTY_NM="시설 2"),
        ])
        self.run_sync(path)
        self.assertEqual(Facility.objects.count(), 2)

    def test_missing_columns_and_empty_file_fail(self):
        missing = self.write_csv([{"FCLTY_NM": "시설"}], columns=["FCLTY_NM"])
        with self.assertRaises(CommandError):
            self.run_sync(missing)
        self.assertEqual(DataSyncRun.objects.latest("started_at").status, DataSyncRun.STATUS_FAILED)

        empty = self.write_csv([], columns=[])
        with self.assertRaises(CommandError):
            self.run_sync(empty)
        self.assertEqual(DataSyncRun.objects.latest("started_at").status, DataSyncRun.STATUS_FAILED)

    def test_invalid_coordinates_and_region_are_isolated(self):
        path = self.write_csv([
            facility_row(SOURCE_RECORD_ID="bad-coordinate", FCLTY_LO="999"),
            facility_row(SOURCE_RECORD_ID="bad-region", ROAD_NM_CTPRVN_NM="알수없음"),
            facility_row(SOURCE_RECORD_ID="good", FCLTY_NM="정상 시설"),
        ])

        self.run_sync(path)

        run = DataSyncRun.objects.get()
        self.assertEqual(run.status, DataSyncRun.STATUS_SUCCESS)
        self.assertEqual(run.failed_count, 2)
        self.assertEqual(Facility.objects.values_list("name", flat=True).get(), "정상 시설")

    def test_unexpected_database_error_rolls_back_all_facilities(self):
        path = self.write_csv([
            facility_row(SOURCE_RECORD_ID="one", FCLTY_NM="시설 1"),
            facility_row(SOURCE_RECORD_ID="two", FCLTY_NM="시설 2"),
        ])
        calls = 0

        def fail_on_second(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("database write failed")
            return Facility.objects.create(
                source_record_id=kwargs["source_record_id"], **kwargs["defaults"]
            ), True

        with patch(
            "fitness.management.commands.sync_facilities.Facility.objects.update_or_create",
            side_effect=fail_on_second,
        ), self.assertRaises(CommandError):
            self.run_sync(path)

        self.assertFalse(Facility.objects.exists())
        self.assertEqual(DataSyncRun.objects.get().status, DataSyncRun.STATUS_FAILED)

    def test_running_status_is_visible_while_rows_are_written(self):
        path = self.write_csv([facility_row()])

        def observe_running(**kwargs):
            self.assertTrue(DataSyncRun.objects.filter(status=DataSyncRun.STATUS_RUNNING).exists())
            return Facility.objects.create(
                source_record_id=kwargs["source_record_id"], **kwargs["defaults"]
            ), True

        with patch(
            "fitness.management.commands.sync_facilities.Facility.objects.update_or_create",
            side_effect=observe_running,
        ):
            self.run_sync(path)

    def test_large_source_drop_requires_explicit_override(self):
        original = self.write_csv([
            facility_row(SOURCE_RECORD_ID=f"id-{index}", FCLTY_NM=f"시설 {index}")
            for index in range(10)
        ], name="source.csv")
        self.run_sync(original)
        reduced = self.write_csv([
            facility_row(SOURCE_RECORD_ID=f"id-{index}", FCLTY_NM=f"시설 {index}")
            for index in range(6)
        ], name="source.csv")

        with self.assertRaises(CommandError):
            self.run_sync(reduced)

        self.assertEqual(DataSyncRun.objects.latest("started_at").status, DataSyncRun.STATUS_FAILED)
        self.assertEqual(Facility.objects.count(), 10)

    def test_source_url_is_explicitly_disabled_and_sanitized(self):
        with self.assertRaises(CommandError):
            call_command(
                "sync_facilities",
                source_url="https://user:secret@example.com/data.csv?token=secret",
            )
        run = DataSyncRun.objects.get()
        self.assertEqual(run.status, DataSyncRun.STATUS_FAILED)
        self.assertEqual(run.source_url, "https://example.com/data.csv")
