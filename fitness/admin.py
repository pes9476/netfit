from django.contrib import admin
from .models import BodyMeasurement, CardBattle, CharacterCard, Facility, FriendLink, Party, Profile, WorkoutRecord

admin.site.register([Profile, CharacterCard, WorkoutRecord, Facility, Party, CardBattle, BodyMeasurement, FriendLink])
