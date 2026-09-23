from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("fitness", "0021_backfill_facility_source_record_id")]

    operations = [
        migrations.AlterField(
            model_name="facility",
            name="source_record_id",
            field=models.CharField(
                blank=True,
                help_text="원본 시설 식별자 또는 정규화된 시설 정보의 SHA-256 값",
                max_length=64,
                null=True,
                unique=True,
            ),
        )
    ]
