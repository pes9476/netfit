from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api_views import (
    BattleRoomViewSet, LoginAPIView, LogoutAPIView, MissionViewSet,
    MyProfileAPIView, PartyViewSet, ProofSubmissionViewSet,
    RegisterAPIView, WorkoutViewSet,
)

router = DefaultRouter()
router.register("workouts", WorkoutViewSet, basename="api-workout")
router.register("groups", PartyViewSet, basename="api-group")
router.register("missions", MissionViewSet, basename="api-mission")
router.register("battles", BattleRoomViewSet, basename="api-battle")
router.register("proofs", ProofSubmissionViewSet, basename="api-proof")

urlpatterns = [
    path("auth/register/", RegisterAPIView.as_view(), name="api-register"),
    path("auth/login/", LoginAPIView.as_view(), name="api-login"),
    path("auth/logout/", LogoutAPIView.as_view(), name="api-logout"),
    path("profile/me/", MyProfileAPIView.as_view(), name="api-my-profile"),
    path("", include(router.urls)),
]
