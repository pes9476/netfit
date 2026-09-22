import csv
import hashlib
import io
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.utils import timezone

from fitness.facility_sync import (
    FacilityRowError,
    facility_defaults_from_row,
    facility_source_record_id,
    redact_error_summary,
    sanitize_source_url,
)
from fitness.models import DataSyncRun, Facility


REQUIRED_COLUMNS = {
    "FCLTY_NM",
    "FCLTY_TY_NM",
    "ROAD_NM_CTPRVN_NM",
    "POSESN_MBY_CTPRVN_NM",
    "RDNMADR_NM",
    "FCLTY_LO",
    "FCLTY_LA",
    "DEL_AT",
}


class Command(BaseCommand):
    help = "검증, 중복 방지, 실행 이력을 포함해 시설 CSV를 동기화합니다."

    def add_arguments(self, parser):
        source = parser.add_mutually_exclusive_group(required=True)
        source.add_argument("--source-path")
        source.add_argument("--source-url")
        parser.add_argument("--allow-large-drop", action="store_true")

    def _finish(self, run, status, **values):
        for name, value in values.items():
            setattr(run, name, value)
        run.status = status
        run.finished_at = timezone.now()
        run.save()

    def _fail(self, run, message, **values):
        safe_message = redact_error_summary(message)
        self._finish(run, DataSyncRun.STATUS_FAILED, error_summary=safe_message, **values)
        raise CommandError(safe_message)

    def handle(self, *args, **options):
        source_url = options.get("source_url")
        if source_url:
            safe_url = sanitize_source_url(source_url)
            run = DataSyncRun.objects.create(
                status=DataSyncRun.STATUS_RUNNING,
                source_name="facility-url",
                source_url=safe_url,
            )
            self._fail(run, "공식 시설 데이터 URL이 확정되지 않아 URL 동기화를 사용할 수 없습니다.")

        path = Path(options["source_path"])
        source_name = path.name or "facility-csv"
        try:
            run = DataSyncRun.objects.create(
                status=DataSyncRun.STATUS_RUNNING,
                source_name=source_name,
            )
        except IntegrityError as exc:
            raise CommandError(f"{source_name} 동기화가 이미 실행 중입니다.") from exc

        try:
            raw = path.read_bytes()
            if not raw.strip():
                self._fail(run, "빈 시설 파일은 동기화할 수 없습니다.")
            checksum = hashlib.sha256(raw).hexdigest()
            run.checksum = checksum
            run.save(update_fields=["checksum"])

            previous_same = DataSyncRun.objects.filter(
                checksum=checksum,
                status__in=[DataSyncRun.STATUS_SUCCESS, DataSyncRun.STATUS_SKIPPED_NO_CHANGE],
            ).exclude(pk=run.pk).exists()
            if previous_same:
                self._finish(run, DataSyncRun.STATUS_SKIPPED_NO_CHANGE)
                self.stdout.write(self.style.WARNING("동일한 원본이 이미 처리되어 생략했습니다."))
                return

            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                self._fail(run, "CSV는 UTF-8 형식이어야 합니다.")
            reader = csv.DictReader(io.StringIO(text))
            fieldnames = set(reader.fieldnames or [])
            missing = sorted(REQUIRED_COLUMNS - fieldnames)
            if missing:
                self._fail(run, f"필수 컬럼이 없습니다: {', '.join(missing)}")
            rows = list(reader)
            if not rows:
                self._fail(run, "헤더만 있는 빈 시설 파일은 동기화할 수 없습니다.")

            source_count = len(rows)
            run.source_count = source_count
            run.save(update_fields=["source_count"])
            previous_success = DataSyncRun.objects.filter(
                status=DataSyncRun.STATUS_SUCCESS,
            ).exclude(pk=run.pk).order_by("-finished_at").first()
            if (
                previous_success
                and previous_success.source_count
                and source_count < previous_success.source_count * 0.7
                and not options["allow_large_drop"]
            ):
                self._fail(
                    run,
                    "원본 행 수가 직전 성공 실행보다 30% 이상 감소했습니다. "
                    "검토 후 --allow-large-drop을 사용하세요.",
                    source_count=source_count,
                )

            created = updated = skipped = failed = 0
            errors = []
            try:
                with transaction.atomic():
                    for line_number, row in enumerate(rows, start=2):
                        if (row.get("DEL_AT") or "").strip().upper() == "Y":
                            skipped += 1
                            continue
                        try:
                            source_record_id = facility_source_record_id(row)
                            defaults = facility_defaults_from_row(row)
                        except FacilityRowError as exc:
                            failed += 1
                            errors.append(f"{line_number}행: {exc}")
                            continue
                        _, was_created = Facility.objects.update_or_create(
                            source_record_id=source_record_id,
                            defaults=defaults,
                        )
                        if was_created:
                            created += 1
                        else:
                            updated += 1
            except Exception as exc:
                self._fail(
                    run,
                    f"시설 저장 중 오류가 발생해 전체 변경을 취소했습니다: {exc}",
                    source_count=source_count,
                    failed_count=failed + 1,
                )

            self._finish(
                run,
                DataSyncRun.STATUS_SUCCESS,
                source_count=source_count,
                created_count=created,
                updated_count=updated,
                skipped_count=skipped,
                failed_count=failed,
                error_summary="\n".join(errors[:20]),
            )
            self.stdout.write(self.style.SUCCESS(
                f"동기화 성공: 생성 {created}, 수정 {updated}, 제외 {skipped}, 실패 {failed}"
            ))
        except CommandError:
            raise
        except Exception as exc:
            self._fail(run, f"시설 동기화 실패: {exc}")
