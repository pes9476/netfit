from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("fitness", "0010_profile_equipped_outfit_outfitpurchase_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="party",
            name="challenge_reward",
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
