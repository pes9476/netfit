# Generated for the Fit Battle integrated version.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("fitness", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="rank_participation",
            field=models.BooleanField(default=True),
        ),
        migrations.CreateModel(
            name="BodyMeasurement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("measured_on", models.DateField()),
                ("height_cm", models.DecimalField(decimal_places=1, max_digits=5)),
                ("weight_kg", models.DecimalField(decimal_places=1, max_digits=5)),
                ("skeletal_muscle_kg", models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True)),
                ("body_fat_percent", models.DecimalField(blank=True, decimal_places=1, max_digits=4, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="body_measurements", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-measured_on", "-created_at"]},
        ),
        migrations.CreateModel(
            name="FriendLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("friend", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="received_friend_links", to=settings.AUTH_USER_MODEL)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sent_friend_links", to=settings.AUTH_USER_MODEL)),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("user", "friend"), name="unique_friend_link")]},
        ),
    ]
