import hashlib
import importlib
import io
from contextlib import redirect_stdout

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext


class FacilityBackfillTests(TransactionTestCase):
    def test_alignment_preserves_conflicts_explicit_ids_and_reimport(self):
        from django.core.management import call_command
        from .facility_sync import facility_source_record_id
        from .test_facility_sync import FacilityCommandTestMixin, facility_row
        before = [("fitness", "0022_facility_source_record_id_unique")]
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        executor.migrate(before)
        try:
            apps = executor.loader.project_state(before).apps
            Facility = apps.get_model("fitness", "Facility")
            row = facility_row(SOURCE_RECORD_ID="")
            name, address = row["FCLTY_NM"], row["RDNMADR_NM"]
            module = importlib.import_module("fitness.migrations.0023_align_facility_source_ids")
            old = module.digest(f"{module.normalize(name)}|{module.normalize(address)}")
            original = Facility.objects.create(name=name, address=address, region="서울특별시", source_record_id=old)
            explicit = Facility.objects.create(name="External", source_record_id=module.digest("source:external"))
            conflict_old = module.digest("conflict|road")
            conflict_new = module.digest("name:conflict|address:road")
            Facility.objects.create(name="Conflict", address="Road", source_record_id=conflict_old)
            Facility.objects.create(name="Conflict", address="Road", source_record_id=conflict_new)
            with redirect_stdout(io.StringIO()):
                MigrationExecutor(connection).migrate(latest)
            original.refresh_from_db()
            self.assertEqual(original.source_record_id, facility_source_record_id(row))
            explicit.refresh_from_db()
            self.assertEqual(explicit.source_record_id, module.digest("source:external"))
            self.assertTrue(Facility.objects.filter(source_record_id=conflict_old).exists())
            path = FacilityCommandTestMixin.write_csv(self, [row])
            call_command("sync_facilities", source_path=str(path), stdout=io.StringIO())
            call_command("sync_facilities", source_path=str(path), stdout=io.StringIO())
            self.assertEqual(Facility.objects.count(), 4)
            with connection.schema_editor() as editor, redirect_stdout(io.StringIO()):
                module.align_ids(apps, editor)
            self.assertEqual(Facility.objects.count(), 4)
        finally:
            MigrationExecutor(connection).migrate(latest)

    def test_existing_duplicate_rows_batch_boundary_and_unique_constraint(self):
        before = [("fitness", "0020_facility_source_record_id_datasyncrun")]
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        executor.migrate(before)
        try:
            apps = executor.loader.project_state(before).apps
            Facility = apps.get_model("fitness", "Facility")
            rows = [Facility(name=f"Gym {i}", address="Road", region="서울특별시")
                    for i in range(501)]
            rows[-1].name = rows[0].name
            Facility.objects.bulk_create(rows)
            migration = importlib.import_module(
                "fitness.migrations.0021_backfill_facility_source_record_id"
            )
            with connection.schema_editor() as editor:
                with CaptureQueriesContext(connection) as queries, redirect_stdout(io.StringIO()):
                    migration.backfill_source_record_ids(apps, editor)
            updates = [q for q in queries if q["sql"].lstrip().upper().startswith("UPDATE")]
            self.assertLess(len(updates), 10)
            saved = list(Facility.objects.order_by("pk"))
            self.assertEqual(len(saved), 501)
            self.assertEqual(len({x.source_record_id for x in saved}), 501)
            expected = hashlib.sha256(b"gym 0|road").hexdigest()
            self.assertEqual(saved[0].source_record_id, expected)
            duplicate = hashlib.sha256(
                f"legacy:{saved[-1].pk}:gym 0|road".encode()
            ).hexdigest()
            self.assertEqual(saved[-1].source_record_id, duplicate)
        finally:
            with redirect_stdout(io.StringIO()):
                MigrationExecutor(connection).migrate(latest)
