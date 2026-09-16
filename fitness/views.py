import random
import math
from datetime import date, timedelta
from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LogoutView
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import RegisterForm, BattleForm, FriendForm, ProfileForm, WorkoutForm
from .models import BadgeAward, BodyMeasurement, CardBattle, DailyQuest, Facility, FriendLink, OutfitPurchase, Party, PersonalDailyQuest, WorkoutRecord
from .services import add_xp, battle_power, calculate_workout_xp, card_stats, get_sports_news, total_card_xp

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
    "러닝": "run", "만보": "walk", "걷기": "walk", "헬스": "gym", "수영": "swim",
    "배드민턴": "badminton", "자전거": "bike",
}

REGION_COORDINATES = {
    "서울": (37.5665, 126.9780), "부산": (35.1796, 129.0756), "대구": (35.8714, 128.6014),
    "인천": (37.4563, 126.7052), "광주": (35.1595, 126.8526), "대전": (36.3504, 127.3845),
    "울산": (35.5384, 129.3114), "세종": (36.4800, 127.2890), "경기": (37.4138, 127.5183),
    "강원": (37.8228, 128.1555), "충청북": (36.6357, 127.4917), "충청남": (36.5184, 126.8000),
    "전북": (35.7175, 127.1530), "전라북": (35.7175, 127.1530), "전라남": (34.8679, 126.9910),
    "경상북": (36.4919, 128.8889), "경상남": (35.4606, 128.2132), "제주": (33.4996, 126.5312),
}


def weather_coordinates(area):
    for prefix, coordinates in REGION_COORDINATES.items():
        if area.startswith(prefix):
            return coordinates
    return REGION_COORDINATES["서울"]


def badge_summary(user):
    awards = BadgeAward.objects.filter(user=user)
    counts = {row["badge_type"]: row["count"] for row in awards.values("badge_type").annotate(count=Count("id"))}
    spent = OutfitPurchase.objects.filter(user=user).aggregate(total=Sum("cost"))["total"] or 0
    total = awards.aggregate(total=Sum("points"))["total"] or 0
    return {
        "gold": counts.get(BadgeAward.GOLD, 0), "silver": counts.get(BadgeAward.SILVER, 0),
        "bronze": counts.get(BadgeAward.BRONZE, 0),
        "total_points": total, "available_points": max(0, total - spent),
    }


def register_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegisterForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
        messages.success(request, "회원가입이 완료되었습니다. 로그인하면 서비스 안내가 시작됩니다.")
        return redirect("login")
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
        return redirect(next_url or "onboarding")
    return render(request, "fitness/login.html", {"form": form, "next": next_url})


def dashboard(request):
    if not request.user.is_authenticated:
        return render(request, "fitness/home.html")
    card = request.user.charactercard
    records = WorkoutRecord.objects.filter(user=request.user)
    stats = card_stats(request.user)
    latest_record = records.order_by("-created_at").first()
    latitude, longitude = weather_coordinates(request.user.profile.area)
    personal_quests = PersonalDailyQuest.objects.filter(user=request.user, is_active=True)[:3]
    group_quests = DailyQuest.objects.filter(
        party__members=request.user, is_active=True,
    ).filter(Q(party__challenge_end__isnull=True) | Q(party__challenge_end__gte=timezone.localdate())).select_related("party")[:3]
    completed_personal_ids = set(BadgeAward.objects.filter(user=request.user, personal_quest__in=personal_quests).values_list("personal_quest_id", flat=True))
    completed_group_ids = set(BadgeAward.objects.filter(user=request.user, daily_quest__in=group_quests).values_list("daily_quest_id", flat=True))
    party_challenges = []
    for party in request.user.parties.all():
        if not party.challenge_start or not party.challenge_end:
            continue
        rows = []
        for member in party.members.select_related("profile"):
            points = BadgeAward.objects.filter(
                user=member,
                awarded_at__date__range=(party.challenge_start, party.challenge_end),
            ).aggregate(total=Sum("points"))["total"] or 0
            rows.append({"name": member.profile.display_name or member.username, "points": points, "is_me": member == request.user})
        rows.sort(key=lambda row: row["points"], reverse=True)
        party_challenges.append({"party": party, "rows": rows})
    return render(request, "fitness/dashboard.html", {
        "card": card, "stats": stats, "power": battle_power(stats, card.level),
        "records": records.order_by("-created_at")[:5],
        "latest_record": latest_record,
        "scene_class": SCENE_MAP.get(latest_record.workout_type if latest_record else "", "run"),
        "friend_count": FriendLink.objects.filter(user=request.user).count(),
        "group_quests": group_quests, "personal_quests": personal_quests,
        "completed_personal_ids": completed_personal_ids, "completed_group_ids": completed_group_ids,
        "badge_summary": badge_summary(request.user),
        "party_challenges": party_challenges, "weather_latitude": latitude, "weather_longitude": longitude,
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
    records = WorkoutRecord.objects.filter(user=request.user)
    today = timezone.localdate()
    chart_start = today - timedelta(days=13)
    daily_rows = {
        row["day"]: row
        for row in records.filter(created_at__date__gte=chart_start)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(minutes=Sum("minutes"), workouts=Count("id"))
    }
    daily_chart = []
    for offset in range(14):
        day = chart_start + timedelta(days=offset)
        row = daily_rows.get(day, {})
        daily_chart.append({"label": day.strftime("%m.%d"), "minutes": row.get("minutes", 0), "workouts": row.get("workouts", 0)})
    type_chart = list(records.values("workout_type").annotate(minutes=Sum("minutes"), workouts=Count("id")).order_by("-minutes", "workout_type"))
    totals = records.aggregate(workouts=Count("id"), minutes=Sum("minutes"))
    badge_points = BadgeAward.objects.filter(user=request.user).aggregate(total=Sum("points"))["total"] or 0
    return render(request, "fitness/profile.html", {
        "form": form, "profile": profile, "card": request.user.charactercard,
        "measurements": BodyMeasurement.objects.filter(user=request.user)[:6],
        "daily_chart": daily_chart, "type_chart": type_chart,
        "workout_totals": {"workouts": totals["workouts"] or 0, "minutes": totals["minutes"] or 0, "points": badge_points},
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
            record.earned_xp = 0
            record.save()
            badge_type = BadgeAward.badge_for_minutes(record.minutes)
            award = BadgeAward.objects.create(
                user=request.user, badge_type=badge_type, source="WORKOUT", workout_record=record,
            )
            messages.success(request, f"운동 기록 완료! {award.get_badge_type_display()} 배지 {award.points}점을 받았어요.")
    return redirect(request.POST.get("next", "activity"))


@login_required
def complete_daily_quest(request, quest_kind, quest_id):
    if request.method != "POST":
        return redirect("dashboard")
    if quest_kind == "personal":
        quest = get_object_or_404(PersonalDailyQuest, pk=quest_id, user=request.user, is_active=True)
        award, created = BadgeAward.objects.get_or_create(
            user=request.user, personal_quest=quest,
            defaults={"badge_type": BadgeAward.badge_for_minutes(quest.target_minutes), "source": "DAILY_QUEST"},
        )
    else:
        quest = get_object_or_404(
            DailyQuest.objects.filter(
                Q(party__challenge_end__isnull=True) | Q(party__challenge_end__gte=timezone.localdate())
            ),
            pk=quest_id, party__members=request.user, is_active=True,
        )
        award, created = BadgeAward.objects.get_or_create(
            user=request.user, daily_quest=quest,
            defaults={"badge_type": BadgeAward.badge_for_minutes(quest.target_minutes), "source": "DAILY_QUEST"},
        )
    if created:
        messages.success(request, f"일퀘 완료! {award.get_badge_type_display()} 배지 {award.points}점을 받았어요.")
    else:
        messages.info(request, "이미 완료하고 배지를 받은 일퀘예요.")
    return redirect("dashboard")


@login_required
def ranking_view(request):
    scope = request.GET.get("scope", "region")
    if scope not in {"region", "party", "friends"}:
        scope = "region"
    current_user = request.user
    users = User.objects.select_related("profile", "charactercard").filter(profile__rank_participation=True)
    if scope == "region":
        users = users.filter(profile__area=current_user.profile.area)
    elif scope == "party":
        party_user_ids = User.objects.filter(parties__members=current_user).values_list("id", flat=True)
        users = users.filter(pk__in=party_user_ids).distinct()
    elif scope == "friends":
        friend_ids = FriendLink.objects.filter(user=current_user).values_list("friend_id", flat=True)
        users = users.filter(pk__in=list(friend_ids) + [current_user.pk])

    ranked = [{
        "name": user.profile.display_name, "area": user.profile.area,
        "level": user.charactercard.level,
        "total_score": BadgeAward.objects.filter(user=user).aggregate(total=Sum("points"))["total"] or 0,
        "is_me": user == current_user, "is_demo": False,
    } for user in users]
    if scope == "friends":
        demo_rows = DEMO_RANKINGS[:3]
    elif scope == "party":
        demo_rows = []
    elif scope == "region":
        demo_rows = [row for row in DEMO_RANKINGS if row["area"] == current_user.profile.area]
        if not demo_rows:
            demo_rows = [{"name": f"{current_user.profile.area} 운동친구", "area": current_user.profile.area, "level": 8, "total_xp": 2420}]
    else:
        demo_rows = DEMO_RANKINGS
    ranked.extend({**row, "total_score": row["total_xp"], "is_me": False, "is_demo": True} for row in demo_rows)
    ranked.sort(key=lambda item: item["total_score"], reverse=True)
    for index, item in enumerate(ranked, 1):
        item["rank"] = index
    return render(request, "fitness/ranking.html", {
        "ranked": ranked, "scope": scope, "friend_count": FriendLink.objects.filter(user=current_user).count(),
    })


@login_required
def outfit_shop(request):
    catalog = [
        {"code": "CAP", "name": "운동 모자", "icon": "🧢", "cost": 150},
        {"code": "SPORT", "name": "스포츠 유니폼", "icon": "👕", "cost": 250},
        {"code": "CROWN", "name": "챔피언 왕관", "icon": "👑", "cost": 400},
    ]
    valid_codes = {item[0] for item in OutfitPurchase.OUTFIT_CHOICES}
    if request.method == "POST":
        action = request.POST.get("action")
        code = request.POST.get("outfit", "")
        if action == "unequip":
            request.user.profile.equipped_outfit = "NONE"
            request.user.profile.save(update_fields=["equipped_outfit"])
            messages.success(request, "기본 모습으로 변경했어요.")
        elif code in valid_codes and action == "buy":
            summary = badge_summary(request.user)
            cost = OutfitPurchase.COSTS[code]
            if OutfitPurchase.objects.filter(user=request.user, outfit=code).exists():
                messages.info(request, "이미 보유한 의상이에요.")
            elif summary["available_points"] < cost:
                messages.error(request, "사용 가능한 배지 포인트가 부족해요.")
            else:
                OutfitPurchase.objects.create(user=request.user, outfit=code, cost=cost)
                messages.success(request, f"{dict(OutfitPurchase.OUTFIT_CHOICES)[code]}을 구매했어요!")
        elif code in valid_codes and action == "equip":
            if OutfitPurchase.objects.filter(user=request.user, outfit=code).exists():
                request.user.profile.equipped_outfit = code
                request.user.profile.save(update_fields=["equipped_outfit"])
                messages.success(request, "캐릭터 의상을 변경했어요.")
        return redirect("outfit_shop")
    owned = set(OutfitPurchase.objects.filter(user=request.user).values_list("outfit", flat=True))
    return render(request, "fitness/outfit_shop.html", {
        "catalog": catalog, "owned_outfits": owned, "badge_summary": badge_summary(request.user),
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
    keyword = request.GET.get("q", "").strip()[:80]
    category = request.GET.get("category", "all")
    categories = [
        ("all", "전체", ""), ("baseball", "야구장", "야구"), ("tennis", "테니스장", "테니스"),
        ("soccer", "축구장", "축구"), ("swimming", "수영장", "수영"),
        ("gym", "체육관", "체육관"), ("field", "운동장", "운동장"),
    ]
    category_terms = {key: term for key, _, term in categories}
    if category not in category_terms:
        category = "all"
    try:
        current_lat = float(request.GET.get("lat", ""))
        current_lon = float(request.GET.get("lon", ""))
        use_current_location = -90 <= current_lat <= 90 and -180 <= current_lon <= 180
    except (TypeError, ValueError):
        current_lat = current_lon = None
        use_current_location = False
    facilities = Facility.objects.filter(is_active=True)
    if not use_current_location:
        facilities = facilities.filter(region=profile.area)
    if keyword:
        facilities = facilities.filter(Q(name__icontains=keyword) | Q(facility_type__icontains=keyword) | Q(address__icontains=keyword))
    if category_terms[category]:
        term = category_terms[category]
        facilities = facilities.filter(Q(name__icontains=term) | Q(facility_type__icontains=term))
    facility_rows = []
    candidates = list(facilities[:500] if use_current_location else facilities[:60])
    for facility in candidates:
        if use_current_location and facility.latitude is not None and facility.longitude is not None:
            lat1, lat2 = math.radians(current_lat), math.radians(facility.latitude)
            dlat = lat2 - lat1
            dlon = math.radians(facility.longitude - current_lon)
            a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
            facility.distance_km = round(6371 * 2 * math.asin(math.sqrt(a)), 1)
        elif use_current_location:
            continue
        destination = quote(facility.name, safe="")
        if facility.longitude is not None and facility.latitude is not None:
            facility.naver_directions_url = "https://map.naver.com/p/directions/-/" + f"{facility.longitude},{facility.latitude},{destination},PLACE_POI/-/transit"
        else:
            facility.naver_directions_url = "https://map.naver.com/p/search/" + quote(f"{facility.name} {facility.address}".strip(), safe="")
        facility_rows.append(facility)
    if use_current_location:
        facility_rows.sort(key=lambda facility: facility.distance_km)
        facility_rows = facility_rows[:60]
    return render(request, "fitness/facilities.html", {
        "facilities": facility_rows, "area": profile.area,
        "keyword": keyword, "category": category, "categories": categories,
        "use_current_location": use_current_location, "current_lat": current_lat, "current_lon": current_lon,
    })


@login_required
def sports_news_api(request):
    return JsonResponse({"news": get_sports_news(limit=6)})


@login_required
def onboarding_entry(request):
    if request.user.profile.onboarding_completed:
        return redirect("dashboard")
    return redirect("onboarding_intro")


@login_required
def onboarding_intro(request):
    return render(request, "fitness/onboarding_intro.html")


@login_required
def onboarding_profile(request):
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
        return redirect("onboarding_mode")
    return render(request, "fitness/onboarding_profile.html", {"form": form, "profile": profile})


@login_required
def onboarding_course(request):
    return redirect("onboarding_mode")


@login_required
def onboarding_mode(request):
    profile = request.user.profile
    if request.method == "POST":
        mode = request.POST.get("mode", "")
        if mode in {key for key, _ in profile.MODE_CHOICES}:
            profile.workout_mode = mode
            if mode == "GROUP":
                profile.onboarding_completed = False
                profile.save(update_fields=["workout_mode", "onboarding_completed"])
                return redirect("onboarding_group")
            profile.onboarding_completed = False
            profile.save(update_fields=["workout_mode", "onboarding_completed"])
            return redirect("onboarding_solo")
        messages.error(request, "운동 방식을 선택해 주세요.")
    return render(request, "fitness/onboarding_mode.html")


@login_required
def onboarding_solo(request):
    profile = request.user.profile
    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "facility":
            profile.workout_mode = "SOLO"
            profile.onboarding_completed = True
            profile.save(update_fields=["workout_mode", "onboarding_completed"])
            return redirect("facilities")
        if action == "ai":
            title, workout_type, minutes = (
                ("가볍게 산책", "걷기", 20) if not profile.age or profile.age >= 60
                else ("활력 러닝", "러닝", 30)
            )
            PersonalDailyQuest.objects.create(
                user=request.user, title=title, workout_type=workout_type,
                target_minutes=minutes, source="AI",
            )
        elif action == "direct":
            title = request.POST.get("title", "").strip()[:100]
            workout_type = request.POST.get("workout_type", "")
            custom_workout_name = request.POST.get("custom_workout_name", "").strip()[:50]
            try:
                minutes = int(request.POST.get("target_minutes", 0))
            except (TypeError, ValueError):
                minutes = 0
            if not title or workout_type not in {key for key, _ in WorkoutRecord.WORKOUT_CHOICES} or (workout_type == "기타" and not custom_workout_name) or not 5 <= minutes <= 300:
                messages.error(request, "일퀘 이름, 운동 종류, 목표 시간(5~300분)을 확인해 주세요.")
                return render(request, "fitness/onboarding_solo.html", {"workout_choices": WorkoutRecord.WORKOUT_CHOICES})
            PersonalDailyQuest.objects.create(
                user=request.user, title=title, workout_type=workout_type,
                custom_workout_name=custom_workout_name,
                target_minutes=minutes, source="DIRECT",
            )
        else:
            messages.error(request, "솔로 일퀘 방식을 선택해 주세요.")
            return redirect("onboarding_solo")
        profile.workout_mode = "SOLO"
        profile.onboarding_completed = True
        profile.save(update_fields=["workout_mode", "onboarding_completed"])
        messages.success(request, "오늘의 솔로 일퀘를 만들었어요.")
        return redirect("dashboard")
    return render(request, "fitness/onboarding_solo.html", {
        "workout_choices": WorkoutRecord.WORKOUT_CHOICES,
    })


@login_required
def onboarding_group(request):
    friends = User.objects.filter(
        received_friend_links__user=request.user
    ).select_related("profile").distinct()
    if request.method == "POST" and request.POST.get("action") == "add_friend":
        code = request.POST.get("friend_code", "").strip()
        friend = User.objects.filter(username__iexact=code).first()
        if not friend:
            messages.error(request, "일치하는 친구를 찾지 못했어요.")
        elif friend == request.user:
            messages.error(request, "본인은 친구로 추가할 수 없어요.")
        elif FriendLink.objects.filter(user=request.user, friend=friend).exists():
            messages.info(request, "이미 친구 목록에 있어요.")
        else:
            FriendLink.objects.get_or_create(user=request.user, friend=friend)
            FriendLink.objects.get_or_create(user=friend, friend=request.user)
            messages.success(request, f"{friend.username}님을 친구로 추가했어요.")
        return redirect("onboarding_group")
    if request.method == "POST" and request.POST.get("action") == "create_room":
        room_name = request.POST.get("room_name", "").strip()[:100]
        challenge_reward = request.POST.get("challenge_reward", "").strip()[:200]
        try:
            challenge_start = date.fromisoformat(request.POST.get("challenge_start", ""))
            challenge_end = date.fromisoformat(request.POST.get("challenge_end", ""))
        except (TypeError, ValueError):
            challenge_start = challenge_end = None
        if not room_name or not challenge_start or not challenge_end or challenge_end < challenge_start:
            messages.error(request, "파티 이름과 올바른 내기 시작일·종료일을 입력해 주세요.")
        else:
            friend_ids = set(friends.values_list("id", flat=True))
            invited_ids = {
                int(value) for value in request.POST.getlist("invitees")
                if value.isdigit() and int(value) in friend_ids
            }
            with transaction.atomic():
                party = Party.objects.create(
                    name=room_name, owner=request.user,
                    challenge_start=challenge_start, challenge_end=challenge_end,
                    challenge_reward=challenge_reward,
                )
                party.members.add(request.user, *User.objects.filter(id__in=invited_ids))
                profile = request.user.profile
                profile.workout_mode = "GROUP"
                profile.save(update_fields=["workout_mode"])
            return redirect("onboarding_group_quest", party_id=party.id)
    return render(request, "fitness/onboarding_group.html", {
        "friends": friends, "friend_form": FriendForm(),
    })


@login_required
def onboarding_group_quest(request, party_id):
    party = get_object_or_404(Party, pk=party_id, owner=request.user)
    workout_choices = WorkoutRecord.WORKOUT_CHOICES
    if request.method == "POST":
        title = request.POST.get("title", "").strip()[:100]
        workout_type = request.POST.get("workout_type", "")
        custom_workout_name = request.POST.get("custom_workout_name", "").strip()[:50]
        try:
            target_minutes = int(request.POST.get("target_minutes", 0))
        except (TypeError, ValueError):
            target_minutes = 0
        valid_types = {key for key, _ in workout_choices}
        if not title or workout_type not in valid_types or (workout_type == "기타" and not custom_workout_name) or not 5 <= target_minutes <= 300:
            messages.error(request, "퀘스트 이름, 운동 종류, 목표 시간(5~300분)을 확인해 주세요.")
        else:
            DailyQuest.objects.create(
                party=party, creator=request.user, title=title,
                workout_type=workout_type, custom_workout_name=custom_workout_name,
                target_minutes=target_minutes,
            )
            profile = request.user.profile
            profile.workout_mode = "GROUP"
            profile.onboarding_completed = True
            profile.save(update_fields=["workout_mode", "onboarding_completed"])
            messages.success(request, f"{party.name}의 일일 퀘스트를 만들었어요.")
            return redirect("dashboard")
    return render(request, "fitness/onboarding_group_quest.html", {
        "party": party, "workout_choices": workout_choices,
        "members": party.members.select_related("profile").all(),
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
