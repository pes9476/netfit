from django.db import migrations, models


UNIFIED_REGION = "전남광주통합특별시"


def merge_regions(apps, schema_editor):
    Profile = apps.get_model("fitness", "Profile")
    Facility = apps.get_model("fitness", "Facility")
    old_regions = ["광주광역시", "전라남도"]
    Profile.objects.filter(area__in=old_regions).update(area=UNIFIED_REGION)
    Facility.objects.filter(region__in=old_regions).update(region=UNIFIED_REGION)


def restore_regions(apps, schema_editor):
    Profile = apps.get_model("fitness", "Profile")
    Facility = apps.get_model("fitness", "Facility")
    Profile.objects.filter(area=UNIFIED_REGION).update(area="광주광역시")
    Facility.objects.filter(region=UNIFIED_REGION).update(region="광주광역시")


REGION_CHOICES = [
    ("서울특별시", "서울특별시"),
    ("부산광역시", "부산광역시"),
    ("대구광역시", "대구광역시"),
    ("인천광역시", "인천광역시"),
    (UNIFIED_REGION, UNIFIED_REGION),
    ("대전광역시", "대전광역시"),
    ("울산광역시", "울산광역시"),
    ("세종특별자치시", "세종특별자치시"),
    ("경기도", "경기도"),
    ("강원특별자치도", "강원특별자치도"),
    ("충청북도", "충청북도"),
    ("충청남도", "충청남도"),
    ("전북특별자치도", "전북특별자치도"),
    ("경상북도", "경상북도"),
    ("경상남도", "경상남도"),
    ("제주특별자치도", "제주특별자치도"),
]


class Migration(migrations.Migration):
    dependencies = [("fitness", "0011_party_challenge_reward")]

    operations = [
        migrations.RunPython(merge_regions, restore_regions),
        migrations.AlterField(
            model_name="profile",
            name="area",
            field=models.CharField(choices=REGION_CHOICES, default="서울특별시", max_length=20),
        ),
        migrations.AlterField(
            model_name="facility",
            name="region",
            field=models.CharField(choices=REGION_CHOICES, max_length=30),
        ),
    ]
