import csv
from django.core.management.base import BaseCommand
from fitness.models import Facility

class Command(BaseCommand):
    help = "전국공공체육시설 CSV를 SQLite DB에 불러옵니다."

    def add_arguments(self, parser):
        parser.add_argument("csv_path")

    def handle(self, *args, **options):
        count = 0
        region_map = {
            "전남광주통합특별시": "광주광역시",
            "강원도": "강원특별자치도",
            "전라북도": "전북특별자치도",
            "제주도": "제주특별자치도",
        }
        valid_regions = dict(Facility._meta.get_field("region").choices)
        with open(options["csv_path"], encoding="utf-8-sig", newline="") as file:
            for row in csv.DictReader(file):
                if row.get("DEL_AT") == "Y":
                    continue
                region = row.get("ROAD_NM_CTPRVN_NM") or row.get("POSESN_MBY_CTPRVN_NM")
                if not region:
                    continue
                region = region_map.get(region, region)
                Facility.objects.update_or_create(
                    name=row.get("FCLTY_NM", ""),
                    address=row.get("RDNMADR_NM", ""),
                    defaults={
                        "facility_type": row.get("FCLTY_TY_NM", ""),
                        "region": region if region in valid_regions else "서울특별시",
                        "longitude": row.get("FCLTY_LO") or None,
                        "latitude": row.get("FCLTY_LA") or None,
                        "homepage_url": row.get("FCLTY_HMPG_URL", ""),
                        "is_active": True,
                    },
                )
                count += 1
        self.stdout.write(self.style.SUCCESS(f"{count}개 시설을 불러왔습니다."))
