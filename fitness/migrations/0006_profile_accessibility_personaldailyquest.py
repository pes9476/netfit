from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("fitness", "0005_party_owner_dailyquest"),
    ]
    operations = [
        migrations.AddField(
            model_name="profile", name="accessibility_type",
            field=models.CharField(choices=[("NON_DISABLED", "비장애인"), ("DISABLED", "장애인")], default="NON_DISABLED", max_length=12),
        ),
        migrations.CreateModel(
            name="PersonalDailyQuest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=100)),
                ("workout_type", models.CharField(choices=[("러닝", "러닝"), ("걷기", "걷기"), ("헬스", "헬스"), ("자전거", "자전거"), ("수영", "수영"), ("배드민턴", "배드민턴"), ("기타", "기타")], max_length=10)),
                ("target_minutes", models.PositiveIntegerField()),
                ("source", models.CharField(choices=[("DIRECT", "직접 입력"), ("AI", "AI 추천")], default="DIRECT", max_length=8)),
                ("quest_date", models.DateField(default=django.utils.timezone.localdate)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="personal_daily_quests", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-quest_date", "-created_at"]},
        ),
    ]
