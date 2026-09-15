import random

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LogoutView
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from .forms import RegisterForm, BattleForm, FriendForm, ProfileForm, WorkoutForm
from .models import BodyMeasurement, CardBattle, Facility, FriendLink, WorkoutRecord
from .services import add_xp, battle_power, calculate_workout_xp, card_stats, total_card_xp

DEMO_OPPONENTS = [
    {"name": "민수 · 파워 트레이너", "level": 3, "power": 58, "reward": "치킨 사기 🍗"},
    {"name": "수빈 · 스피드 러너", "level": 6, "power": 72, "reward": "커피 사기 ☕"},
    {"name": "지훈 · 꾸준한 워커", "level": 10, "power": 88, "reward": "카페 디저트 사기 🍰"},
    {"name": "마포구 러너 팀", "level": 15, "power": 115, "reward": "영화 보여주기 🎬"},
    {"name": "부산 러닝 크루", "level": 22, "power": 150, "reward": "밥 사기 🍚"},
]

# 테스트 화면에서 바로 확인할 수 있도록 넣은 예시 데이터입니다.
# 실제 서비스에서는 사용자의 카드 데이터로 바꿔서 계산합니다.
DEMO_RANKINGS = [
    {"name": "러닝민수", "area": "서울특별시", "level": 18, "total_xp": 6840},
    {"name": "수영하는수빈", "area": "부산광역시", "level": 16, "total_xp": 5980},
    {"name": "헬스지훈", "area": "경기도", "level": 14, "total_xp": 4720},
    {"name": "배드민턴하늘", "area": "대전광역시", "level": 11, "total_xp": 3610},
    {"name": "자전거유진", "area": "인천광역시", "level": 9, "total_xp": 2790},
    {"name": "걷기왕소라", "area": "광주광역시", "level": 7, "total_xp": 1940},
]

SCENE_MAP = {
    "러닝": "run", "걷기": "walk", "헬스": "gym", "수영": "swim",
    "배드민턴": "badminton", "자전거": "bike",
}


def register_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegisterForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
        login(request, user)
        messages.success(request, "회원가입이 완료되었습니다. 프로필을 설정해 주세요.")
        return redirect("profile")
    return render(request, "fitness/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = AuthenticationForm(request, data=request.POST if request.method == "POST" else None)
    next_url = request.POST.get("next", request.GET.get("next", ""))
    if not url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        next_url = ""
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect(next_url or "dashboard")
    return render(request, "fitness/login.html", {"form": form, "next": next_url})


def dashboard(request):
    if not request.user.is_authenticated:
        return render(request, "fitness/home.html")
    card = request.user.charactercard
    records = WorkoutRecord.objects.filter(user=request.user)
    stats = card_stats(request.user)
    latest_record = records.order_by("-created_at").first()
    return render(request, "fitness/dashboard.html", {
        "card": card, "stats": stats, "power": battle_power(stats, card.level),
        "records": records.order_by("-created_at")[:5],
        "latest_record": latest_record,
        "scene_class": SCENE_MAP.get(latest_record.workout_type if latest_record else "", "run"),
        "friend_count": FriendLink.objects.filter(user=request.user).count(),
    })


@login_required
def profile_view(request):
    profile = request.user.profile
    form = ProfileForm(request.POST or None, instance=profile, user=request.user)
    if request.method == "POST" and form.is_valid():
        profile = form.save()
        if profile.height_cm and profile.weight_kg:
            BodyMeasurement.objects.create(
                user=request.user,
                measured_on=form.cleaned_data["measured_on"],
                height_cm=profile.height_cm,
                weight_kg=profile.weight_kg,
                skeletal_muscle_kg=profile.skeletal_muscle_kg,
                body_fat_percent=profile.body_fat_percent,
            )
        messages.success(request, "프로필과 인바디 정보를 저장했어요.")
        return redirect("profile")
    return render(request, "fitness/profile.html", {
        "form": form, "profile": profile, "card": request.user.charactercard,
        "measurements": BodyMeasurement.objects.filter(user=request.user)[:6],
    })


@login_required
def activity_view(request):
    return render(request, "fitness/activity.html", {
        "workout_form": WorkoutForm(),
        "records": WorkoutRecord.objects.filter(user=request.user).order_by("-created_at")[:20],
    })


@login_required
def record_workout(request):
    if request.method == "POST":
        form = WorkoutForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.user = request.user
            record.earned_xp = calculate_workout_xp(record.minutes, record.distance_km, record.with_party)
            record.save()
            add_xp(request.user.charactercard, record.earned_xp)
            messages.success(request, f"운동 기록 완료! +{record.earned_xp} 경험치를 받았어요.")
    return redirect(request.POST.get("next", "activity"))


@login_required
def ranking_view(request):
    scope = request.GET.get("scope", "national")
    current_user = request.user
    users = User.objects.select_related("profile", "charactercard").filter(profile__rank_participation=True)
    if scope == "region":
        users = users.filter(profile__area=current_user.profile.area)
    elif scope == "friends":
        friend_ids = FriendLink.objects.filter(user=current_user).values_list("friend_id", flat=True)
        users = users.filter(pk__in=list(friend_ids) + [current_user.pk])

    ranked = [{
        "name": user.profile.display_name, "area": user.profile.area,
        "level": user.charactercard.level, "total_xp": total_card_xp(user.charactercard),
        "is_me": user == current_user, "is_demo": False,
    } for user in users]
    if scope == "friends":
        demo_rows = DEMO_RANKINGS[:3]
    elif scope == "region":
        demo_rows = [row for row in DEMO_RANKINGS if row["area"] == current_user.profile.area]
        if not demo_rows:
            demo_rows = [{"name": f"{current_user.profile.area} 운동친구", "area": current_user.profile.area, "level": 8, "total_xp": 2420}]
    else:
        demo_rows = DEMO_RANKINGS
    ranked.extend({**row, "is_me": False, "is_demo": True} for row in demo_rows)
    ranked.sort(key=lambda item: item["total_xp"], reverse=True)
    for index, item in enumerate(ranked, 1):
        item["rank"] = index
    return render(request, "fitness/ranking.html", {
        "ranked": ranked, "scope": scope, "friend_count": FriendLink.objects.filter(user=current_user).count(),
    })


@login_required
def friends_view(request):
    friends = User.objects.filter(received_friend_links__user=request.user).select_related("profile", "charactercard")
    return render(request, "fitness/friends.html", {"friend_form": FriendForm(), "friends": friends})


@login_required
def add_friend(request):
    if request.method == "POST":
        form = FriendForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data["friend_code"].strip()
            friend = User.objects.filter(username__iexact=code).first()
            if not friend:
                messages.error(request, "일치하는 닉네임을 찾지 못했어요. 상대방의 닉네임을 확인해주세요.")
            elif friend == request.user:
                messages.error(request, "본인은 친구로 추가할 수 없어요.")
            elif FriendLink.objects.filter(user=request.user, friend=friend).exists():
                messages.error(request, "이미 추가한 친구예요.")
            else:
                FriendLink.objects.get_or_create(user=request.user, friend=friend)
                FriendLink.objects.get_or_create(user=friend, friend=request.user)
                messages.success(request, f"{friend.username}님을 친구로 추가했어요!")
    return redirect("friends")


@login_required
def facilities_view(request):
    profile = request.user.profile
    facilities = Facility.objects.filter(region=profile.area, is_active=True)[:30]
    return render(request, "fitness/facilities.html", {
        "facilities": facilities, "area": profile.area,
    })


@login_required
def region_view(request):
    card = request.user.charactercard
    return render(request, "fitness/region.html", {
        "card": card, "stats": card_stats(request.user),
        "power": battle_power(card_stats(request.user), card.level),
        "region_rows": DEMO_RANKINGS[:5],
    })


@login_required
def battle_view(request):
    card = request.user.charactercard
    battles = CardBattle.objects.filter(challenger=request.user).order_by("-created_at")[:6]
    return render(request, "fitness/battle.html", {
        "card": card, "stats": card_stats(request.user),
        "power": battle_power(card_stats(request.user), card.level),
        "battle_form": BattleForm(initial={
            "scope": request.GET.get("scope", "PARTY"),
            "region_name": request.GET.get("region", ""),
        }), "battles": battles,
        "demo_opponents": DEMO_OPPONENTS,
    })


@login_required
def create_battle(request):
    if request.method == "POST":
        form = BattleForm(request.POST)
        if form.is_valid():
            battle = form.save(commit=False)
            battle.challenger = request.user
            card = request.user.charactercard
            stats = card_stats(request.user)
            battle.challenger_power = battle_power(stats, card.level)
            battle.opponent_power = max(50, battle.challenger_power + random.randint(-15, 15))
            battle.opponent_level = max(1, card.level + random.randint(-3, 4))
            if battle.scope == "REGION" and card.level < 5:
                messages.error(request, "지역 카드 배틀은 레벨 5부터 참여할 수 있어요.")
                return redirect("battle")
            if battle.reward != "CUSTOM":
                battle.custom_reward = ""
            battle.is_finished = True
            battle.save()
            return redirect("battle_arena", battle_id=battle.pk)
    return redirect("battle")


def opponent_visual(name, level):
    seed = sum(ord(char) for char in name)
    scenes = ["run", "walk", "gym", "swim", "badminton", "bike"]
    gender = "F" if seed % 2 else "M"
    age = 10 + seed % 65
    styles = ["SLIM", "BALANCED", "SOFT", "ACTIVE", "MUSCULAR"]
    return {
        "gender": gender, "sprite_gender": "female" if gender == "F" else "male",
        "age": age, "age_group": "child" if age < 18 else "senior" if age >= 60 else "adult",
        "body_style": styles[seed % len(styles)],
        "height": 155 + seed % 27, "weight": 52 + seed % 28,
        "muscle": 19 + seed % 17, "fat": 16 + seed % 15,
        "scene": scenes[seed % len(scenes)], "level": level,
    }


@login_required
def battle_arena(request, battle_id):
    battle = get_object_or_404(CardBattle, pk=battle_id, challenger=request.user)
    latest = WorkoutRecord.objects.filter(user=request.user).order_by("-created_at").first()
    return render(request, "fitness/battle_arena.html", {
        "battle": battle, "card": request.user.charactercard, "stats": card_stats(request.user),
        "opponent": opponent_visual(battle.opponent_name, battle.opponent_level),
        "own_scene": SCENE_MAP.get(latest.workout_type if latest else "", "run"),
    })


@login_required
def demo_level(request, target_level=None):
    if request.method == "POST":
        card = request.user.charactercard
        if target_level:
            card.level = target_level
            card.xp = 0
            card.frame = card.card_tier
            card.save()
            messages.success(request, f"테스트 모드: 레벨 {target_level} 카드 프레임으로 바꿨어요.")
        else:
            add_xp(card, card.next_level_xp)
            messages.success(request, f"테스트 모드: 레벨 {card.level}이 되었어요.")
    return redirect("dashboard")


@login_required
def demo_battle(request):
    if request.method == "POST":
        card = request.user.charactercard
        try:
            opponent = DEMO_OPPONENTS[int(request.POST.get("opponent_index", "-1"))]
        except (ValueError, IndexError):
            opponent = random.choice(DEMO_OPPONENTS)
        own_power = max(45, battle_power(card_stats(request.user), card.level))
        battle = CardBattle.objects.create(
            challenger=request.user,
            scope="REGION" if "구" in opponent["name"] or "부산" in opponent["name"] else "PARTY",
            opponent_name=opponent["name"], opponent_level=opponent["level"],
            region_name=request.user.profile.area, reward="CUSTOM", custom_reward=opponent["reward"],
            challenger_power=own_power, opponent_power=opponent["power"], is_finished=True,
        )
        return redirect("battle_arena", battle_id=battle.pk)
    return redirect("battle")


class UserLogoutView(LogoutView):
    pass
