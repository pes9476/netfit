from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("fitness", "0004_profile_onboarding"),
    ]

    operations = [
        migrations.CreateModel(
            name="DailyQuest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=100)),
                ("workout_type", models.CharField(choices=[("러닝", "러닝"), ("걷기", "걷기"), ("헬스", "헬스"), ("자전거", "자전거"), ("수영", "수영"), ("배드민턴", "배드민턴"), ("기타", "기타")], max_length=10)),
                ("target_minutes", models.PositiveIntegerField()),
                ("quest_date", models.DateField(default=django.utils.timezone.localdate)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("creator", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="created_daily_quests", to=settings.AUTH_USER_MODEL)),
                ("party", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="daily_quests", to="fitness.party")),
            ],
            options={"ordering": ["-quest_date", "-created_at"]},
        ),
    ]
