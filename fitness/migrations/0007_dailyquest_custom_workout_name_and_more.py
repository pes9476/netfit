from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("fitness", "0006_profile_accessibility_personaldailyquest")]
    operations = [
        migrations.AddField(model_name="dailyquest", name="custom_workout_name", field=models.CharField(blank=True, max_length=50)),
        migrations.AddField(model_name="personaldailyquest", name="custom_workout_name", field=models.CharField(blank=True, max_length=50)),
    ]
