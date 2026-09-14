from django.urls import path
from .views import UserLogoutView, activity_view, add_friend, battle_arena, battle_view, create_battle, dashboard, demo_battle, demo_level, facilities_view, friends_view, login_view, profile_view, ranking_view, record_workout, region_view, register_view

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("register/", register_view, name="register"),
    path("login/", login_view, name="login"),
    path("logout/", UserLogoutView.as_view(), name="logout"),
    path("profile/", profile_view, name="profile"),
    path("activity/", activity_view, name="activity"),
    path("record/", record_workout, name="record_workout"),
    path("ranking/", ranking_view, name="ranking"),
    path("friends/", friends_view, name="friends"),
    path("friends/add/", add_friend, name="add_friend"),
    path("facilities/", facilities_view, name="facilities"),
    path("region/", region_view, name="region"),
    path("battle/", battle_view, name="battle"),
    path("battle/create/", create_battle, name="create_battle"),
    path("battle/<int:battle_id>/", battle_arena, name="battle_arena"),
    path("demo/level/", demo_level, name="demo_level"),
    path("demo/level/<int:target_level>/", demo_level, name="demo_level_target"),
    path("demo/battle/", demo_battle, name="demo_battle"),
]
