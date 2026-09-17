from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import BattleParticipant, BattleRoom, Mission, Party, ProofSubmission, WorkoutRecord
from .serializers import (
    BattleRoomSerializer, MissionSerializer, PartySerializer, ProfileSerializer,
    ProofSubmissionSerializer, RegisterSerializer, UserSummarySerializer,
    WorkoutRecordSerializer,
)


class RegisterAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        login(request, user)
        return Response({
            "user": UserSummarySerializer(user).data,
            "onboarding_completed": False,
            "next": "/api/v1/profile/me/",
        }, status=status.HTTP_201_CREATED)


class LoginAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        user = authenticate(request, username=request.data.get("username"), password=request.data.get("password"))
        if not user:
            return Response({"detail": "아이디 또는 비밀번호가 올바르지 않습니다."}, status=status.HTTP_400_BAD_REQUEST)
        login(request, user)
        return Response({
            "user": UserSummarySerializer(user).data,
            "onboarding_completed": user.profile.onboarding_completed,
            "next": "/" if user.profile.onboarding_completed else "/profile/",
        })


class LogoutAPIView(APIView):
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyProfileAPIView(APIView):
    def get(self, request):
        return Response(ProfileSerializer(request.user.profile).data)

    def patch(self, request):
        serializer = ProfileSerializer(request.user.profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class WorkoutViewSet(viewsets.ModelViewSet):
    serializer_class = WorkoutRecordSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return WorkoutRecord.objects.filter(user=self.request.user).order_by("-created_at")

    @action(detail=False, methods=["get"])
    def summary(self, request):
        rows = list(self.get_queryset().annotate(day=TruncDate("created_at")).values("day").annotate(
            minutes=Sum("minutes"), distance_km=Sum("distance_km"), workouts=Count("id")
        ).order_by("day"))
        return Response(rows)


class PartyViewSet(viewsets.ModelViewSet):
    serializer_class = PartySerializer

    def get_queryset(self):
        return Party.objects.filter(members=self.request.user).select_related("owner").prefetch_related("members").distinct()

    def perform_update(self, serializer):
        if serializer.instance.owner_id != self.request.user.id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("그룹장만 그룹을 수정할 수 있습니다.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.owner_id != self.request.user.id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("그룹장만 그룹을 삭제할 수 있습니다.")
        instance.delete()

    @action(detail=True, methods=["post"])
    def join(self, request, pk=None):
        party = get_object_or_404(Party, pk=pk)
        with transaction.atomic():
            locked = Party.objects.select_for_update().get(pk=party.pk)
            if locked.members.count() >= locked.max_members:
                return Response({"detail": "그룹 정원이 가득 찼습니다."}, status=status.HTTP_409_CONFLICT)
            locked.members.add(request.user)
        return Response(self.get_serializer(locked).data)


class MissionViewSet(viewsets.ModelViewSet):
    serializer_class = MissionSerializer

    def get_queryset(self):
        return Mission.objects.filter(participants=self.request.user).select_related("creator", "party").prefetch_related("participations__user").distinct()

    def perform_update(self, serializer):
        if serializer.instance.creator_id != self.request.user.id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("미션 생성자만 수정할 수 있습니다.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.creator_id != self.request.user.id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("미션 생성자만 삭제할 수 있습니다.")
        instance.delete()


class BattleRoomViewSet(viewsets.ModelViewSet):
    serializer_class = BattleRoomSerializer

    def get_queryset(self):
        return BattleRoom.objects.filter(participants=self.request.user).select_related("creator", "mission").prefetch_related("entries__user").distinct()

    def perform_update(self, serializer):
        if serializer.instance.creator_id != self.request.user.id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("방장만 대결을 수정할 수 있습니다.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.creator_id != self.request.user.id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("방장만 대결을 삭제할 수 있습니다.")
        instance.delete()

    @action(detail=True, methods=["post"])
    def join(self, request, pk=None):
        with transaction.atomic():
            battle = get_object_or_404(BattleRoom.objects.select_for_update(), pk=pk)
            if battle.status != "RECRUITING":
                return Response({"detail": "모집 중인 대결이 아닙니다."}, status=status.HTTP_409_CONFLICT)
            if battle.entries.filter(user=request.user).exists():
                return Response(self.get_serializer(battle).data)
            if battle.entries.count() >= battle.capacity:
                return Response({"detail": "대결 정원이 가득 찼습니다."}, status=status.HTTP_409_CONFLICT)
            team = int(request.data.get("team", 2))
            if team not in (1, 2):
                return Response({"team": "팀은 1 또는 2여야 합니다."}, status=status.HTTP_400_BAD_REQUEST)
            BattleParticipant.objects.create(battle=battle, user=request.user, team=team)
            if battle.entries.count() == battle.capacity:
                battle.status = "ACTIVE"
                battle.save(update_fields=["status"])
        return Response(self.get_serializer(battle).data)


class ProofSubmissionViewSet(viewsets.ModelViewSet):
    serializer_class = ProofSubmissionSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return ProofSubmission.objects.filter(participant__user=self.request.user).select_related("participant__mission")
