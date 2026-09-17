from django.contrib import admin
from .models import BodyMeasurement, BattleParticipant, BattleRoom, CardBattle, CharacterCard, Facility, FriendLink, Mission, MissionParticipant, Party, Profile, ProofSubmission, WorkoutRecord

admin.site.register([Profile, CharacterCard, WorkoutRecord, Facility, Party, CardBattle, BodyMeasurement, FriendLink, Mission, MissionParticipant, BattleRoom, BattleParticipant, ProofSubmission])

admin.site.site_header = "NetFit 관리자"
admin.site.site_title = "NetFit 관리"
admin.site.index_title = "NetFit 서비스 데이터 관리"
