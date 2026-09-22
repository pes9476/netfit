from django.contrib import admin
from .models import BadgeAward, BodyMeasurement, CardBattle, CharacterCard, DataSyncRun, Facility, FriendLink, OutfitPurchase, Party, Profile, WorkoutRecord

admin.site.register([Profile, CharacterCard, WorkoutRecord, BadgeAward, OutfitPurchase, Facility, DataSyncRun, Party, CardBattle, BodyMeasurement, FriendLink])
