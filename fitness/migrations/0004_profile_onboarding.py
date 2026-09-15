from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("fitness", "0004_party_created_at_party_max_members_party_owner_and_more")]

    operations = [
        migrations.AddField(model_name="profile", name="workout_goal", field=models.CharField(blank=True, choices=[("HEALTH", "건강 습관"), ("DIET", "체중 관리"), ("STRENGTH", "근력 향상"), ("ENDURANCE", "체력 향상")], max_length=12)),
        migrations.AddField(model_name="profile", name="workout_days", field=models.PositiveSmallIntegerField(default=3)),
        migrations.AddField(model_name="profile", name="workout_mode", field=models.CharField(blank=True, choices=[("SOLO", "혼자 운동"), ("GROUP", "그룹 운동")], max_length=8)),
    ]
