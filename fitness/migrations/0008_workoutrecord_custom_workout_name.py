from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("fitness", "0007_dailyquest_custom_workout_name_and_more")]

    operations = [
        migrations.AddField(
            model_name="workoutrecord",
            name="custom_workout_name",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AlterField(
            model_name="workoutrecord",
            name="workout_type",
            field=models.CharField(
                choices=[
                    ("러닝", "러닝"), ("만보", "만보"), ("걷기", "걷기"),
                    ("헬스", "헬스"), ("자전거", "자전거"), ("수영", "수영"),
                    ("배드민턴", "배드민턴"), ("기타", "기타"),
                ],
                max_length=10,
            ),
        ),
    ]
