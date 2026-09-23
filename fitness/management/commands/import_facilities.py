import csv
from django.core.management.base import BaseCommand
from fitness.models import Facility
from fitness.facility_sync import (
    FacilityRowError,
    facility_defaults_from_row,
    facility_source_record_id,
)

class Command(BaseCommand):
    help = "전국공공체육시설 CSV를 현재 DB에 불러옵니다."

    def add_arguments(self, parser):
        parser.add_argument("csv_path")

    def handle(self, *args, **options):
        count = 0
        skipped = 0
        failed = 0
        with open(options["csv_path"], encoding="utf-8-sig", newline="") as file:
            for line_number, row in enumerate(csv.DictReader(file), start=2):
                if row.get("DEL_AT") == "Y":
                    skipped += 1
                    continue
                try:
                    source_record_id = facility_source_record_id(row)
                    defaults = facility_defaults_from_row(row)
                except FacilityRowError as exc:
                    failed += 1
                    self.stderr.write(f"{line_number}행 건너뜀: {exc}")
                    continue
                Facility.objects.update_or_create(
                    source_record_id=source_record_id,
                    defaults=defaults,
                )
                count += 1
        self.stdout.write(self.style.SUCCESS(
            f"시설 {count}개 저장, {skipped}개 제외, {failed}개 실패"
        ))
