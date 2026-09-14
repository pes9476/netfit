from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CharacterCard, Profile

@receiver(post_save, sender=User)
def create_user_game_data(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
        CharacterCard.objects.create(user=instance)
