import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL), ("fitness", "0009_badgeaward_party_challenge_dates")]
    operations = [
        migrations.AddField(model_name="profile", name="equipped_outfit", field=models.CharField(choices=[("NONE", "기본"), ("CAP", "운동 모자"), ("SPORT", "스포츠 유니폼"), ("CROWN", "챔피언 왕관")], default="NONE", max_length=10)),
        migrations.AlterField(model_name="workoutrecord", name="workout_type", field=models.CharField(choices=[("러닝", "러닝"), ("만보", "만보"), ("걷기", "산책"), ("헬스", "헬스"), ("자전거", "자전거"), ("수영", "수영"), ("배드민턴", "배드민턴"), ("등산", "등산"), ("축구", "축구"), ("농구", "농구"), ("요가", "요가"), ("기타", "기타")], max_length=10)),
        migrations.AlterField(model_name="dailyquest", name="workout_type", field=models.CharField(choices=[("러닝", "러닝"), ("걷기", "산책"), ("헬스", "헬스"), ("자전거", "자전거"), ("수영", "수영"), ("배드민턴", "배드민턴"), ("등산", "등산"), ("축구", "축구"), ("농구", "농구"), ("요가", "요가"), ("기타", "기타")], max_length=10)),
        migrations.AlterField(model_name="personaldailyquest", name="workout_type", field=models.CharField(choices=[("러닝", "러닝"), ("걷기", "산책"), ("헬스", "헬스"), ("자전거", "자전거"), ("수영", "수영"), ("배드민턴", "배드민턴"), ("등산", "등산"), ("축구", "축구"), ("농구", "농구"), ("요가", "요가"), ("기타", "기타")], max_length=10)),
        migrations.CreateModel(name="OutfitPurchase", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("outfit", models.CharField(choices=[("CAP", "운동 모자"), ("SPORT", "스포츠 유니폼"), ("CROWN", "챔피언 왕관")], max_length=10)), ("cost", models.PositiveIntegerField()), ("purchased_at", models.DateTimeField(auto_now_add=True)), ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="outfit_purchases", to=settings.AUTH_USER_MODEL))]),
        migrations.AddConstraint(model_name="outfitpurchase", constraint=models.UniqueConstraint(fields=("user", "outfit"), name="unique_user_outfit")),
    ]
