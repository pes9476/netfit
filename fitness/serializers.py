from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import (
    BattleParticipant, BattleRoom, Mission, MissionParticipant, Party,
    Profile, ProofSubmission, WorkoutRecord,
)
from .services import add_xp, calculate_workout_xp


class UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username")


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    area = serializers.ChoiceField(choices=Profile._meta.get_field("area").choices, write_only=True)

    class Meta:
        model = User
        fields = ("id", "username", "password", "area")

    def create(self, validated_data):
        area = validated_data.pop("area")
        user = User.objects.create_user(
            **validated_data,
            is_staff=False,
            is_superuser=False,
        )
        user.profile.area = area
        user.profile.save(update_fields=["area"])
        return user


class ProfileSerializer(serializers.ModelSerializer):
    nickname = serializers.CharField(source="user.username")
    bmi = serializers.FloatField(read_only=True)
    bmi_status = serializers.CharField(read_only=True)

    class Meta:
        model = Profile
        fields = (
            "nickname", "area", "age", "gender", "height_cm", "weight_kg",
            "skeletal_muscle_kg", "body_fat_percent", "rank_participation",
            "preferred_activity_mode", "disability_status", "wheelchair_usage",
            "onboarding_completed", "bmi", "bmi_status",
        )

    def validate(self, attrs):
        disability = attrs.get("disability_status", getattr(self.instance, "disability_status", "UNSET"))
        wheelchair = attrs.get("wheelchair_usage", getattr(self.instance, "wheelchair_usage", "UNSET"))
        if disability != "DISABLED" and wheelchair not in ("UNSET", "NO"):
            raise serializers.ValidationError({"wheelchair_usage": "장애인 선택 시에만 휠체어 이용 정보를 입력할 수 있습니다."})
        wants_complete = attrs.get("onboarding_completed", getattr(self.instance, "onboarding_completed", False))
        if wants_complete:
            required = {
                "age": attrs.get("age", getattr(self.instance, "age", None)),
                "height_cm": attrs.get("height_cm", getattr(self.instance, "height_cm", None)),
                "weight_kg": attrs.get("weight_kg", getattr(self.instance, "weight_kg", None)),
                "preferred_activity_mode": attrs.get("preferred_activity_mode", getattr(self.instance, "preferred_activity_mode", "UNSET")),
            }
            errors = {field: "온보딩 완료에 필요한 값입니다." for field, value in required.items() if value in (None, "", "UNSET")}
            if errors:
                raise serializers.ValidationError(errors)
        return attrs

    @transaction.atomic
    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        nickname = user_data.get("username")
        if nickname:
            if User.objects.filter(username__iexact=nickname).exclude(pk=instance.user_id).exists():
                raise serializers.ValidationError({"nickname": "이미 사용 중인 닉네임입니다."})
            instance.user.username = nickname
            instance.user.save(update_fields=["username"])
        return super().update(instance, validated_data)


class WorkoutRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkoutRecord
        fields = ("id", "workout_type", "minutes", "distance_km", "location", "with_party", "earned_xp", "created_at")
        read_only_fields = ("earned_xp", "created_at")

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data["earned_xp"] = calculate_workout_xp(
            validated_data["minutes"], validated_data.get("distance_km", 0), validated_data.get("with_party", False)
        )
        with transaction.atomic():
            record = WorkoutRecord.objects.create(user=user, **validated_data)
            add_xp(user.charactercard, record.earned_xp)
        return record


class PartySerializer(serializers.ModelSerializer):
    owner = UserSummarySerializer(read_only=True)
    members = UserSummarySerializer(many=True, read_only=True)

    class Meta:
        model = Party
        fields = ("id", "name", "goal_km", "max_members", "owner", "members", "created_at")
        read_only_fields = ("created_at",)

    def validate_max_members(self, value):
        if value < 1 or value > 4:
            raise serializers.ValidationError("그룹 인원은 1~4명이어야 합니다.")
        return value

    def create(self, validated_data):
        user = self.context["request"].user
        party = Party.objects.create(owner=user, **validated_data)
        party.members.add(user)
        return party


class MissionParticipantSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)

    class Meta:
        model = MissionParticipant
        fields = ("id", "user", "progress_count", "completed_at")


class MissionSerializer(serializers.ModelSerializer):
    creator = UserSummarySerializer(read_only=True)
    participations = MissionParticipantSerializer(many=True, read_only=True)

    class Meta:
        model = Mission
        fields = (
            "id", "creator", "party", "mode", "title", "description", "target_count",
            "requires_photo", "starts_at", "ends_at", "status", "participations", "created_at",
        )
        read_only_fields = ("created_at",)

    def validate(self, attrs):
        if attrs["starts_at"] >= attrs["ends_at"]:
            raise serializers.ValidationError({"ends_at": "종료 시각은 시작 시각보다 늦어야 합니다."})
        mode, party = attrs["mode"], attrs.get("party")
        user = self.context["request"].user
        if mode == "SOLO" and party:
            raise serializers.ValidationError({"party": "솔로 미션에는 그룹을 지정할 수 없습니다."})
        if mode == "GROUP" and (not party or not party.members.filter(pk=user.pk).exists()):
            raise serializers.ValidationError({"party": "가입한 그룹만 그룹 미션으로 지정할 수 있습니다."})
        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        with transaction.atomic():
            mission = Mission.objects.create(creator=user, **validated_data)
            users = [user] if mission.mode == "SOLO" else mission.party.members.all()
            MissionParticipant.objects.bulk_create(MissionParticipant(mission=mission, user=member) for member in users)
        return mission


class BattleParticipantSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)

    class Meta:
        model = BattleParticipant
        fields = ("id", "user", "team", "score", "joined_at")


class BattleRoomSerializer(serializers.ModelSerializer):
    creator = UserSummarySerializer(read_only=True)
    entries = BattleParticipantSerializer(many=True, read_only=True)

    class Meta:
        model = BattleRoom
        fields = ("id", "creator", "mission", "title", "capacity", "penalty", "status", "entries", "created_at")
        read_only_fields = ("created_at",)

    def validate_mission(self, mission):
        user = self.context["request"].user
        if mission.creator_id != user.id or mission.mode != "GROUP":
            raise serializers.ValidationError("본인이 만든 그룹 미션만 대결에 사용할 수 있습니다.")
        if hasattr(mission, "battle_room"):
            raise serializers.ValidationError("이미 대결에 연결된 미션입니다.")
        return mission

    def create(self, validated_data):
        user = self.context["request"].user
        battle = BattleRoom.objects.create(creator=user, **validated_data)
        BattleParticipant.objects.create(battle=battle, user=user, team=1)
        return battle


class ProofSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProofSubmission
        fields = ("id", "participant", "photo", "captured_at", "status", "created_at")
        read_only_fields = ("status", "created_at")

    def validate_participant(self, participant):
        if participant.user_id != self.context["request"].user.id:
            raise serializers.ValidationError("본인의 미션에만 인증할 수 있습니다.")
        return participant

    def validate_captured_at(self, value):
        if value > timezone.now() + timezone.timedelta(minutes=5):
            raise serializers.ValidationError("촬영 시각이 현재보다 미래일 수 없습니다.")
        return value

    def validate_photo(self, value):
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("사진은 10MB 이하여야 합니다.")
        if value.content_type not in ("image/jpeg", "image/png", "image/webp"):
            raise serializers.ValidationError("JPEG, PNG, WEBP 사진만 허용합니다.")
        return value
