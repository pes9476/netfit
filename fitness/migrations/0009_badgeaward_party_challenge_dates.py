import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("fitness", "0008_workoutrecord_custom_workout_name"),
    ]

    operations = [
        migrations.AddField(model_name="party", name="challenge_start", field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="party", name="challenge_end", field=models.DateField(blank=True, null=True)),
        migrations.CreateModel(
            name="BadgeAward",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("badge_type", models.CharField(choices=[("GOLD", "금"), ("SILVER", "은"), ("BRONZE", "동")], max_length=8)),
                ("points", models.PositiveSmallIntegerField()),
                ("source", models.CharField(choices=[("WORKOUT", "운동 기록"), ("DAILY_QUEST", "일퀘 완료")], max_length=12)),
                ("awarded_at", models.DateTimeField(auto_now_add=True)),
                ("daily_quest", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="badge_awards", to="fitness.dailyquest")),
                ("personal_quest", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="badge_awards", to="fitness.personaldailyquest")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="badge_awards", to=settings.AUTH_USER_MODEL)),
                ("workout_record", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="badge_award", to="fitness.workoutrecord")),
            ],
            options={"ordering": ["-awarded_at"]},
        ),
        migrations.AddConstraint(model_name="badgeaward", constraint=models.UniqueConstraint(condition=models.Q(("daily_quest__isnull", False)), fields=("user", "daily_quest"), name="unique_group_quest_badge_per_user")),
        migrations.AddConstraint(model_name="badgeaward", constraint=models.UniqueConstraint(condition=models.Q(("personal_quest__isnull", False)), fields=("user", "personal_quest"), name="unique_personal_quest_badge_per_user")),
    ]
