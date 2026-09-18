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
from .models import BadgeAward, BodyMeasurement, CardBattle, DailyQuest, Facility, FriendLink, FriendRequest, OutfitPurchase, Party, PartyInvitation, PersonalDailyQuest, WorkoutRecord
from .services import add_xp, battle_power, calculate_workout_xp, card_stats, get_sports_news, get_weather_data, total_card_xp

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
    {"name": "걷기왕소라", "area": "전남광주통합특별시", "level": 7, "total_xp": 1940},
]

SCENE_MAP = {
    "러닝": "run", "만보": "walk", "걷기": "walk", "헬스": "gym", "수영": "swim",
    "배드민턴": "badminton", "자전거": "bike",
}

REGION_COORDINATES = {
    "서울": (37.5665, 126.9780), "부산": (35.1796, 129.0756), "대구": (35.8714, 128.6014),
    "인천": (37.4563, 126.7052), "전남광주": (35.1595, 126.8526), "대전": (36.3504, 127.3845),
    "울산": (35.5384, 129.3114), "세종": (36.4800, 127.2890), "경기": (37.4138, 127.5183),
    "강원": (37.8228, 128.1555), "충청북": (36.6357, 127.4917), "충청남": (36.5184, 126.8000),
    "전북": (35.7175, 127.1530), "전라북": (35.7175, 127.1530),
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
        user = form.get_user()
        login(request, user)
        return redirect(next_url or ("dashboard" if user.profile.onboarding_completed else "onboarding"))
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

    today = timezone.localdate()
    today_records = list(records.filter(created_at__date=today))

    personal_badge_map = {
        award.personal_quest_id: award
        for award in BadgeAward.objects.filter(user=request.user, personal_quest__in=personal_quests)
    }
    group_badge_map = {
        award.daily_quest_id: award
        for award in BadgeAward.objects.filter(user=request.user, daily_quest__in=group_quests)
    }

    for quest in personal_quests:
        is_done = quest.id in completed_personal_ids
        quest.is_completed = is_done
        quest.badge_award = personal_badge_map.get(quest.id)
        if is_done:
            quest.progress_percent = 100
            quest.done_minutes = quest.target_minutes
            quest.remaining_minutes = 0
        else:
            done_mins = sum(r.minutes for r in today_records if r.workout_type == quest.workout_type or quest.workout_type == "기타")
            quest.done_minutes = min(done_mins, quest.target_minutes)
            quest.remaining_minutes = max(0, quest.target_minutes - done_mins)
            quest.progress_percent = min(100, int((done_mins / quest.target_minutes * 100))) if quest.target_minutes else 0

    for quest in group_quests:
        is_done = quest.id in completed_group_ids
        quest.is_completed = is_done
        quest.badge_award = group_badge_map.get(quest.id)
        if is_done:
            quest.progress_percent = 100
            quest.done_minutes = quest.target_minutes
            quest.remaining_minutes = 0
        else:
            done_mins = sum(r.minutes for r in today_records if r.workout_type == quest.workout_type or quest.workout_type == "기타")
            quest.done_minutes = min(done_mins, quest.target_minutes)
            quest.remaining_minutes = max(0, quest.target_minutes - done_mins)
            quest.progress_percent = min(100, int((done_mins / quest.target_minutes * 100))) if quest.target_minutes else 0

        # 👥 파티원 참여자 모니터링 (각 파티원의 오늘 미션 달성 여부)
        members_status = []
        party_members = quest.party.members.all().select_related("profile", "charactercard")
        for m in party_members:
            has_done = BadgeAward.objects.filter(user=m, daily_quest=quest, awarded_at__date=today).exists()
            members_status.append({
                "user": m,
                "name": m.profile.display_name or m.username,
                "level": getattr(getattr(m, "charactercard", None), "level", 1),
                "is_done": has_done,
                "is_me": (m == request.user),
            })
        quest.members_monitoring = members_status

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

    # 🔔 대기 중인 친구 요청 및 파티 초대
    pending_friend_requests = FriendRequest.objects.filter(
        to_user=request.user, status="PENDING"
    ).select_related("from_user__profile", "from_user__charactercard")
    pending_party_invitations = PartyInvitation.objects.filter(
        invitee=request.user, status="PENDING"
    ).select_related("party", "inviter__profile")

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
        "pending_friend_requests": pending_friend_requests,
        "pending_party_invitations": pending_party_invitations,
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
    try:
        current_lat = float(request.GET.get("lat", ""))
        current_lon = float(request.GET.get("lon", ""))
        use_current_location = -90 <= current_lat <= 90 and -180 <= current_lon <= 180
    except (TypeError, ValueError):
        current_lat = current_lon = None
        use_current_location = False
    facilities = Facility.objects.filter(is_active=True)
    if not use_current_location:
        facilities = facilities.filter(region=request.user.profile.area)
    recommendations = []
    for facility in list(facilities[:500] if use_current_location else facilities[:3]):
        if use_current_location:
            if facility.latitude is None or facility.longitude is None:
                continue
            lat1, lat2 = math.radians(current_lat), math.radians(facility.latitude)
            dlat, dlon = lat2 - lat1, math.radians(facility.longitude - current_lon)
            value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
            facility.distance_km = round(6371 * 2 * math.asin(math.sqrt(value)), 1)
        query = quote(f"{facility.name} {facility.address}".strip(), safe="")
        facility.kakao_map_url = (
            f"https://map.kakao.com/link/to/{quote(facility.name, safe='')},{facility.latitude},{facility.longitude}"
            if facility.latitude is not None and facility.longitude is not None
            else f"https://map.kakao.com/link/search/{query}"
        )
        recommendations.append(facility)
    if use_current_location:
        recommendations.sort(key=lambda item: item.distance_km)
        recommendations = recommendations[:3]
    return render(request, "fitness/activity.html", {
        "workout_form": WorkoutForm(),
        "records": WorkoutRecord.objects.filter(user=request.user).order_by("-created_at")[:20],
        "recommended_facilities": recommendations,
        "use_current_location": use_current_location,
    })


@login_required
def record_workout(request):
    if request.method == "POST":
        form = WorkoutForm(request.POST, request.FILES)
        if form.is_valid():
            record = form.save(commit=False)
            record.user = request.user
            record.earned_xp = 0
            record.save()
            badge_type = BadgeAward.badge_for_minutes(record.minutes)
            award = BadgeAward.objects.create(
                user=request.user, badge_type=badge_type, source="WORKOUT", workout_record=record,
                proof_image=record.proof_image,
            )
            messages.success(request, f"운동 기록 완료! {award.get_badge_type_display()} 배지 {award.points}점을 받았어요.")
    return redirect(request.POST.get("next", "activity"))


@login_required
def complete_daily_quest(request, quest_kind, quest_id):
    if request.method != "POST":
        return redirect("dashboard")
    action = request.POST.get("action", "complete")
    proof_image = request.FILES.get("proof_image")
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

    # 1. 인증 사진 삭제 액션
    if action == "delete_proof":
        if award.proof_image:
            award.proof_image.delete(save=False)
            award.proof_image = None
            award.save(update_fields=["proof_image"])
            if hasattr(award, "workout_record") and award.workout_record:
                award.workout_record.proof_image = None
                award.workout_record.save(update_fields=["proof_image"])
            messages.success(request, "등록된 인증 사진이 삭제되었습니다.")
        else:
            messages.info(request, "삭제할 인증 사진이 없습니다.")
        return redirect("dashboard")

    # 2. 최초 완료 시 (최근 운동 기록에 자동 등록)
    if created:
        if proof_image:
            award.proof_image = proof_image
            award.save(update_fields=["proof_image"])
        w_type = quest.workout_type if quest.workout_type in dict(WorkoutRecord.WORKOUT_CHOICES) else "기타"
        custom_name = getattr(quest, "custom_workout_name", "") or (quest.title if w_type == "기타" else "")
        rec = WorkoutRecord.objects.create(
            user=request.user,
            workout_type=w_type,
            custom_workout_name=custom_name,
            minutes=quest.target_minutes,
            location="일일미션 달성",
            proof_image=award.proof_image,
        )
        award.workout_record = rec
        award.save(update_fields=["workout_record"])
        messages.success(request, f"일일미션 완료! {award.get_badge_type_display()} 배지와 {award.points}점을 받았어요. (최근 운동기록 자동 등록)")
    else:
        # 3. 이미 완료된 미션의 사진 변경/수정 또는 신규 등록
        if proof_image:
            is_update = bool(award.proof_image)
            award.proof_image = proof_image
            award.save(update_fields=["proof_image"])
            if hasattr(award, "workout_record") and award.workout_record:
                award.workout_record.proof_image = award.proof_image
                award.workout_record.save(update_fields=["proof_image"])
            if is_update:
                messages.success(request, "인증 사진이 새로운 사진으로 성공적으로 변경되었습니다!")
            else:
                messages.success(request, "인증 사진이 성공적으로 등록되었습니다!")
        else:
            messages.info(request, "이미 완료하고 배지를 받은 일일미션이에요.")
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
        {
            "code": "BAND",
            "name": "스포티 네온 헤어밴드",
            "icon": "⚡",
            "category": "머리 장식",
            "filter_group": "head",
            "cost": 50,
            "medals": 3,
            "desc": "네온 민트 컬러의 땀흡수 스포츠 헤어밴드. 열정적인 러너의 상징!",
        },
        {
            "code": "GLASS",
            "name": "사이버 네온 선글라스",
            "icon": "🕶️",
            "category": "페이스/안경",
            "filter_group": "head",
            "cost": 80,
            "medals": 5,
            "desc": "사이버펑크 감성의 고글 선글라스. 자외선과 상대방의 기세를 차단합니다.",
        },
        {
            "code": "HEADSET",
            "name": "사이버 게이밍 헤드셋",
            "icon": "🎧",
            "category": "머리 장식",
            "filter_group": "head",
            "cost": 100,
            "medals": 6,
            "desc": "비트감 넘치는 운동 BGM을 선사하는 네온 LED 게이밍 헤드셋.",
        },
        {
            "code": "MASK",
            "name": "사이버 닌자 마스크",
            "icon": "🥷",
            "category": "페이스/안경",
            "filter_group": "head",
            "cost": 110,
            "medals": 7,
            "desc": "미세먼지와 바람을 완벽 차단하는 하이테크 네온 방진 마스크.",
        },
        {
            "code": "BELT",
            "name": "골드 챔피언 벨트",
            "icon": "🥋",
            "category": "의상/벨트",
            "filter_group": "body",
            "cost": 120,
            "medals": 8,
            "desc": "피트니스 아레나 챔피언의 황금 버클 벨트. 당당한 승리자의 상징.",
        },
        {
            "code": "CAP",
            "name": "운동 모자",
            "icon": "🧢",
            "category": "머리 장식",
            "filter_group": "head",
            "cost": 150,
            "medals": 10,
            "desc": "어떤 운동에도 잘 어울리는 기본 스포츠 스트릿 캡.",
        },
        {
            "code": "MEDAL",
            "name": "골드 빅토리 목걸이",
            "icon": "🥇",
            "category": "액세서리",
            "filter_group": "body",
            "cost": 180,
            "medals": 12,
            "desc": "가장 먼저 결승선을 통과한 1등 러너에게 수여된 순금 메달 목걸이.",
        },
        {
            "code": "GLOVES",
            "name": "파이어 복싱 글러브",
            "icon": "🥊",
            "category": "액세서리",
            "filter_group": "body",
            "cost": 200,
            "medals": 14,
            "desc": "강력한 펀치 파워와 악력을 불어넣는 화염 가죽 복싱 글러브.",
        },
        {
            "code": "SPORT",
            "name": "스포츠 유니폼",
            "icon": "👕",
            "category": "의상/벨트",
            "filter_group": "body",
            "cost": 250,
            "medals": 15,
            "desc": "통기성과 탄력이 뛰어난 기능성 프로 스포츠 유니폼.",
        },
        {
            "code": "CLOAK",
            "name": "다크 히어로 망토",
            "icon": "🦸",
            "category": "특수/이펙트",
            "filter_group": "special",
            "cost": 300,
            "medals": 18,
            "desc": "바람에 휘날리며 위엄을 드러내는 보랏빛 사이버 히어로 망토.",
        },
        {
            "code": "SWORD",
            "name": "네온 빔세이버",
            "icon": "⚔️",
            "category": "특수/이펙트",
            "filter_group": "special",
            "cost": 350,
            "medals": 20,
            "desc": "빛의 에너지 입자를 칼날로 형상화한 하이테크 레이저 세이버.",
        },
        {
            "code": "CROWN",
            "name": "챔피언 왕관",
            "icon": "👑",
            "category": "머리 장식",
            "filter_group": "head",
            "cost": 400,
            "medals": 22,
            "desc": "NETFIT 최정상 파이터에게 걸맞은 번쩍이는 황금 왕관.",
        },
        {
            "code": "WING",
            "name": "사이버 홀로그램 윙",
            "icon": "🪽",
            "category": "특수/이펙트",
            "filter_group": "special",
            "cost": 500,
            "medals": 25,
            "desc": "빛의 속도로 질주하는 러너를 위한 홀로그램 날개 이펙트.",
        },
        {
            "code": "DRAGON",
            "name": "미니 파이어 펫",
            "icon": "🐲",
            "category": "동반자/펫",
            "filter_group": "special",
            "cost": 550,
            "medals": 28,
            "desc": "러너의 곁을 든든하게 날아다니며 응원해주는 수호신 아기 드래곤.",
        },
        {
            "code": "AURA",
            "name": "불꽃 버닝 파이어 오라",
            "icon": "🔥",
            "category": "특수/이펙트",
            "filter_group": "special",
            "cost": 650,
            "medals": 35,
            "desc": "운동 에너지가 임계점을 넘을 때 발현되는 압도적인 화염 오라.",
        },
        {
            "code": "VICTORY",
            "name": "골드 빅토리 트로피",
            "icon": "🏆",
            "category": "특수/이펙트",
            "filter_group": "special",
            "cost": 800,
            "medals": 40,
            "desc": "모든 챌린지를 정복한 전설의 챔피언에게 수여되는 레전드 트로피.",
        },
    ]
    valid_codes = {item[0] for item in OutfitPurchase.OUTFIT_CHOICES}
    if request.method == "POST":
        action = request.POST.get("action")
        code = request.POST.get("outfit", "").strip()
        msg_text = ""
        msg_type = "info"
        if action == "unequip_all":
            request.user.profile.unequip_outfit(None)
            request.user.profile.save(update_fields=["equipped_outfit"])
            msg_text = "모든 장착 아이템을 해제했어요."
            msg_type = "success"
        elif action == "unequip":
            request.user.profile.unequip_outfit(code if code else None)
            request.user.profile.save(update_fields=["equipped_outfit"])
            msg_text = "장착을 해제했어요."
            msg_type = "success"
        elif code in valid_codes and action == "buy":
            summary = badge_summary(request.user)
            cost = OutfitPurchase.COSTS[code]
            if OutfitPurchase.objects.filter(user=request.user, outfit=code).exists():
                msg_text = "이미 보유한 아이템이에요."
                msg_type = "info"
            elif summary["available_points"] < cost:
                msg_text = "사용 가능한 배지 포인트(메달)가 부족해요."
                msg_type = "error"
            else:
                OutfitPurchase.objects.create(user=request.user, outfit=code, cost=cost)
                request.user.profile.equip_outfit(code)
                request.user.profile.save(update_fields=["equipped_outfit"])
                msg_text = f"🎉 {dict(OutfitPurchase.OUTFIT_CHOICES)[code]}을(를) 구매하고 장착했어요!"
                msg_type = "success"
        elif code in valid_codes and action == "equip":
            if OutfitPurchase.objects.filter(user=request.user, outfit=code).exists():
                request.user.profile.equip_outfit(code)
                request.user.profile.save(update_fields=["equipped_outfit"])
                msg_text = f"✨ {dict(OutfitPurchase.OUTFIT_CHOICES)[code]}을(를) 착용했어요."
                msg_type = "success"

        is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest" or request.POST.get("ajax") == "1"
        if not is_ajax and msg_text:
            if msg_type == "success":
                messages.success(request, msg_text)
            elif msg_type == "info":
                messages.info(request, msg_text)
            elif msg_type == "error":
                messages.error(request, msg_text)

        if is_ajax:
            owned = list(OutfitPurchase.objects.filter(user=request.user).values_list("outfit", flat=True))
            summary = badge_summary(request.user)
            spent_points = max(0, summary["total_points"] - summary["available_points"])
            equipped_codes = request.user.profile.equipped_outfits_list
            base_sprite_outfit = ""
            if "CAP" in equipped_codes:
                base_sprite_outfit = "cap"
            elif "SPORT" in equipped_codes:
                base_sprite_outfit = "sport"
            elif "CROWN" in equipped_codes:
                base_sprite_outfit = "crown"
            equipped_items_data = [
                {"code": it["code"], "name": it["name"], "icon": it["icon"], "category": it["category"], "cost": it["cost"]}
                for it in catalog if it["code"] in equipped_codes
            ]
            return JsonResponse({
                "status": msg_type,
                "message": msg_text,
                "equipped_codes": equipped_codes,
                "owned_outfits": owned,
                "available_points": summary["available_points"],
                "spent_points": spent_points,
                "total_points": summary["total_points"],
                "equipped_items": equipped_items_data,
                "base_sprite_outfit": base_sprite_outfit,
            })

        return redirect("outfit_shop")

    owned = set(OutfitPurchase.objects.filter(user=request.user).values_list("outfit", flat=True))
    summary = badge_summary(request.user)
    spent_points = max(0, summary["total_points"] - summary["available_points"])

    equipped_codes = request.user.profile.equipped_outfits_list
    equipped_items = [it for it in catalog if it["code"] in equipped_codes]

    base_sprite_outfit = ""
    if "CAP" in equipped_codes:
        base_sprite_outfit = "cap"
    elif "SPORT" in equipped_codes:
        base_sprite_outfit = "sport"
    elif "CROWN" in equipped_codes:
        base_sprite_outfit = "crown"

    return render(request, "fitness/outfit_shop.html", {
        "catalog": catalog,
        "owned_outfits": owned,
        "badge_summary": summary,
        "spent_points": spent_points,
        "equipped_codes": set(equipped_codes),
        "equipped_items": equipped_items,
        "base_sprite_outfit": base_sprite_outfit,
        "equipped_item": equipped_items[0] if equipped_items else None,
    })


@login_required
def friends_view(request):
    friends = User.objects.filter(received_friend_links__user=request.user).select_related("profile", "charactercard")
    pending_received_requests = FriendRequest.objects.filter(to_user=request.user, status="PENDING").select_related("from_user__profile", "from_user__charactercard")
    pending_sent_requests = FriendRequest.objects.filter(from_user=request.user, status="PENDING").select_related("to_user__profile")
    return render(request, "fitness/friends.html", {
        "friend_form": FriendForm(),
        "friends": friends,
        "pending_received_requests": pending_received_requests,
        "pending_sent_requests": pending_sent_requests,
    })


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
                messages.info(request, f"{friend.username}님과는 이미 친구예요.")
            elif FriendRequest.objects.filter(from_user=request.user, to_user=friend, status="PENDING").exists():
                messages.info(request, f"{friend.username}님에게 이미 친구 요청을 보냈어요. 상대방의 수락을 기다리는 중입니다.")
            elif FriendRequest.objects.filter(from_user=friend, to_user=request.user, status="PENDING").exists():
                fr = FriendRequest.objects.get(from_user=friend, to_user=request.user, status="PENDING")
                fr.status = "ACCEPTED"
                fr.save(update_fields=["status"])
                FriendLink.objects.get_or_create(user=request.user, friend=friend)
                FriendLink.objects.get_or_create(user=friend, friend=request.user)
                messages.success(request, f"{friend.username}님의 친구 요청을 수락하여 서로 친구가 되었어요!")
            else:
                FriendRequest.objects.create(from_user=request.user, to_user=friend, status="PENDING")
                messages.success(request, f"{friend.username}님에게 친구 요청을 보냈습니다! 상대방이 수락하면 친구로 등록됩니다.")
    return redirect(request.POST.get("next") or "friends")


@login_required
def respond_friend_request(request, request_id, action):
    if request.method == "POST":
        freq = get_object_or_404(FriendRequest, pk=request_id, to_user=request.user, status="PENDING")
        if action == "accept":
            freq.status = "ACCEPTED"
            freq.save(update_fields=["status"])
            FriendLink.objects.get_or_create(user=request.user, friend=freq.from_user)
            FriendLink.objects.get_or_create(user=freq.from_user, friend=request.user)
            messages.success(request, f"{freq.from_user.username}님의 친구 요청을 수락했습니다! 이제 함께 운동할 수 있어요.")
        elif action == "reject":
            freq.status = "REJECTED"
            freq.save(update_fields=["status"])
            messages.info(request, f"{freq.from_user.username}님의 친구 요청을 거절했습니다.")
    return redirect(request.POST.get("next") or request.META.get("HTTP_REFERER") or "dashboard")


@login_required
def respond_party_invitation(request, invitation_id, action):
    if request.method == "POST":
        inv = get_object_or_404(PartyInvitation, pk=invitation_id, invitee=request.user, status="PENDING")
        if action == "accept":
            inv.status = "ACCEPTED"
            inv.save(update_fields=["status"])
            inv.party.members.add(request.user)
            messages.success(request, f"'{inv.party.name}' 파티 초대를 수락했습니다! 파티 일일미션에 참여해보세요.")
        elif action == "reject":
            inv.status = "REJECTED"
            inv.save(update_fields=["status"])
            messages.info(request, f"'{inv.party.name}' 파티 초대를 거절했습니다.")
    return redirect(request.POST.get("next") or request.META.get("HTTP_REFERER") or "dashboard")


PRESET_LOCATIONS = {
    "bupyeong": (37.4988, 126.7237, "인천 부평"),
    "gasan": (37.4812, 126.8827, "서울 가산동"),
    "gangnam": (37.4979, 127.0276, "서울 강남"),
    "songdo": (37.3888, 126.6533, "인천 송도"),
    "hongdae": (37.5575, 126.9244, "서울 홍대"),
    "pangyo": (37.3947, 127.1111, "경기 판교"),
}

PRESET_BUTTONS = [
    {"key": "bupyeong", "name": "인천 부평", "icon": "fa-building"},
    {"key": "gasan", "name": "서울 가산동", "icon": "fa-briefcase"},
    {"key": "gangnam", "name": "서울 강남", "icon": "fa-city"},
    {"key": "songdo", "name": "인천 송도", "icon": "fa-water"},
    {"key": "hongdae", "name": "서울 홍대", "icon": "fa-compass"},
    {"key": "pangyo", "name": "경기 판교", "icon": "fa-laptop-code"},
]


@login_required
def facilities_view(request):
    profile = request.user.profile
    keyword = request.GET.get("q", "").strip()[:80]
    query = keyword
    f_type = request.GET.get("type", "").strip()
    category = request.GET.get("category", "all")
    preset_key = request.GET.get("preset", "").strip()

    categories = [
        ("all", "전체", ""), ("baseball", "야구장", "야구"), ("tennis", "테니스장", "테니스"),
        ("soccer", "축구장", "축구"), ("swimming", "수영장", "수영"),
        ("gym", "체육관", "체육관"), ("field", "운동장", "운동장"),
    ]
    types = ["전체", "축구장", "야구장", "수영장", "테니스장", "배드민턴", "체육관", "간이운동장"]

    user_lat = None
    user_lng = None
    current_location_label = None
    is_gps = False

    # 1. 퀵 프리셋 선택 시 (인천 부평, 서울 가산동 등)
    if preset_key in PRESET_LOCATIONS:
        p_lat, p_lng, p_label = PRESET_LOCATIONS[preset_key]
        user_lat, user_lng = p_lat, p_lng
        current_location_label = p_label
    # 2. GPS 파라미터 (lat/lng 또는 lat/lon)
    elif request.GET.get("lat") and (request.GET.get("lng") or request.GET.get("lon")):
        try:
            user_lat = float(request.GET.get("lat"))
            user_lng = float(request.GET.get("lng") or request.GET.get("lon"))
            if -90 <= user_lat <= 90 and -180 <= user_lng <= 180:
                current_location_label = request.GET.get("loc_name", "실시간 GPS 위치")
                is_gps = True
            else:
                user_lat, user_lng = None, None
        except (TypeError, ValueError):
            user_lat, user_lng = None, None

    use_current_location = user_lat is not None and user_lng is not None

    facilities_qs = Facility.objects.filter(is_active=True)

    if use_current_location:
        facilities_qs = facilities_qs.filter(latitude__isnull=False, longitude__isnull=False)
        # 1차 정밀 반경 (±0.18도 ≈ 반경 20km 이내 집중 탐색)
        lat_range = 0.18
        lng_range = 0.22
        local_qs = facilities_qs.filter(
            latitude__gte=user_lat - lat_range,
            latitude__lte=user_lat + lat_range,
            longitude__gte=user_lng - lng_range,
            longitude__lte=user_lng + lng_range,
        )
        # 외곽 지역이거나 시설 수가 적을 경우 반경 45km로 안전 확장
        if local_qs.count() < 15:
            lat_range = 0.45
            lng_range = 0.55
            local_qs = facilities_qs.filter(
                latitude__gte=user_lat - lat_range,
                latitude__lte=user_lat + lat_range,
                longitude__gte=user_lng - lng_range,
                longitude__lte=user_lng + lng_range,
            )
        facilities_qs = local_qs
    else:
        if not keyword:
            facilities_qs = facilities_qs.filter(region=profile.area)
            current_location_label = f"홈 지역 ({profile.area})"
        else:
            current_location_label = f"'{keyword}' 검색 결과"

    if keyword:
        facilities_qs = facilities_qs.filter(
            Q(name__icontains=keyword) | Q(facility_type__icontains=keyword) | Q(address__icontains=keyword)
        )

    # 종목별 필터: type 파라미터 우선, 없으면 category 파라미터
    target_type = f_type if f_type and f_type != "전체" else ""
    if not target_type and category != "all":
        category_terms = {k: t for k, _, t in categories}
        target_type = category_terms.get(category, "")

    if target_type:
        facilities_qs = facilities_qs.filter(Q(name__icontains=target_type) | Q(facility_type__icontains=target_type))

    candidate_list = list(facilities_qs[:1000] if use_current_location else facilities_qs[:60])
    facility_rows = []

    for facility in candidate_list:
        if use_current_location and facility.latitude is not None and facility.longitude is not None:
            lat1, lat2 = math.radians(user_lat), math.radians(facility.latitude)
            dlat = lat2 - lat1
            dlon = math.radians(facility.longitude - user_lng)
            a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
            dist = 6371 * 2 * math.asin(math.sqrt(a))
            facility.distance_km = round(dist, 1)
            if dist < 1.0:
                facility.distance_str = f"{int(dist * 1000)}m"
            else:
                facility.distance_str = f"{dist:.1f}km"
        else:
            facility.distance_km = 9999
            facility.distance_str = "-"

        destination = quote(facility.name, safe="")
        if facility.longitude is not None and facility.latitude is not None:
            facility.naver_directions_url = f"https://map.naver.com/p/directions/-/{facility.longitude},{facility.latitude},{destination},PLACE_POI/-/transit"
            facility.kakao_map_url = f"https://map.kakao.com/link/to/{destination},{facility.latitude},{facility.longitude}"
        else:
            search_query = quote(f"{facility.name} {facility.address}".strip(), safe="")
            facility.naver_directions_url = f"https://map.naver.com/p/search/{search_query}"
            facility.kakao_map_url = f"https://map.kakao.com/link/search/{search_query}"
        facility.naver_map_url = facility.naver_directions_url

        facility_rows.append(facility)

    if use_current_location:
        facility_rows.sort(key=lambda f: f.distance_km)
        total_count = len(facility_rows)
        facility_rows = facility_rows[:60]
    else:
        total_count = facilities_qs.count()

    return render(request, "fitness/facilities.html", {
        "facilities": facility_rows,
        "area": profile.area,
        "total_count": total_count,
        "keyword": keyword,
        "query": query,
        "category": category,
        "categories": categories,
        "selected_type": f_type or (category if category != "all" else "전체"),
        "types": types,
        "user_lat": user_lat,
        "user_lng": user_lng,
        "current_lat": user_lat,
        "current_lon": user_lng,
        "current_location_label": current_location_label or f"홈 지역 ({profile.area})",
        "selected_preset": preset_key,
        "presets": PRESET_BUTTONS,
        "is_gps": is_gps,
        "use_current_location": use_current_location,
    })


def weather_api(request):
    """실시간 GPS 좌표를 받아 즉시 날씨 JSON을 반환하는 API 엔드포인트"""
    lat = request.GET.get("lat")
    lng = request.GET.get("lng")
    loc_name = request.GET.get("loc_name", "")
    user_area = request.user.profile.area if request.user.is_authenticated else "서울특별시"

    if lat and lng:
        try:
            w = get_weather_data(lat=float(lat), lon=float(lng), location_name=loc_name, is_gps=True)
            return JsonResponse({"status": "success", "weather": w})
        except ValueError:
            pass

    coords = weather_coordinates(user_area)
    w = get_weather_data(lat=coords[0], lon=coords[1], location_name=user_area, is_gps=False)
    return JsonResponse({"status": "success", "weather": w})


@login_required
def sports_news_api(request):
    force_refresh = request.GET.get("refresh") in ("1", "true", "True")
    try:
        page = int(request.GET.get("page")) if request.GET.get("page") is not None else None
    except (TypeError, ValueError):
        page = None
    news = get_sports_news(limit=6, refresh=force_refresh, page=page)
    return JsonResponse({"status": "success", "news": news})


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
                messages.error(request, "일일미션 이름, 운동 종류, 목표 시간(5~300분)을 확인해 주세요.")
                return render(request, "fitness/onboarding_solo.html", {"workout_choices": WorkoutRecord.WORKOUT_CHOICES})
            PersonalDailyQuest.objects.create(
                user=request.user, title=title, workout_type=workout_type,
                custom_workout_name=custom_workout_name,
                target_minutes=minutes, source="DIRECT",
            )
        else:
            messages.error(request, "솔로 일일미션 방식을 선택해 주세요.")
            return redirect("onboarding_solo")
        profile.workout_mode = "SOLO"
        profile.onboarding_completed = True
        profile.save(update_fields=["workout_mode", "onboarding_completed"])
        messages.success(request, "오늘의 솔로 일일미션을 만들었어요.")
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
            messages.info(request, f"{friend.username}님과는 이미 친구예요.")
        elif FriendRequest.objects.filter(from_user=request.user, to_user=friend, status="PENDING").exists():
            messages.info(request, f"{friend.username}님에게 이미 친구 요청을 보냈어요. 상대방의 수락을 기다리는 중입니다.")
        elif FriendRequest.objects.filter(from_user=friend, to_user=request.user, status="PENDING").exists():
            fr = FriendRequest.objects.get(from_user=friend, to_user=request.user, status="PENDING")
            fr.status = "ACCEPTED"
            fr.save(update_fields=["status"])
            FriendLink.objects.get_or_create(user=request.user, friend=friend)
            FriendLink.objects.get_or_create(user=friend, friend=request.user)
            messages.success(request, f"{friend.username}님의 친구 요청을 수락하여 서로 친구가 되었어요!")
        else:
            FriendRequest.objects.create(from_user=request.user, to_user=friend, status="PENDING")
            messages.success(request, f"{friend.username}님에게 친구 요청을 보냈습니다! 상대방이 수락하면 친구로 등록됩니다.")
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
                party.members.add(request.user)
                for inv_user in User.objects.filter(id__in=invited_ids):
                    PartyInvitation.objects.get_or_create(
                        party=party,
                        inviter=request.user,
                        invitee=inv_user,
                        defaults={"status": "PENDING"}
                    )
                profile = request.user.profile
                profile.workout_mode = "GROUP"
                profile.save(update_fields=["workout_mode"])
            if invited_ids:
                messages.success(request, f"'{party.name}' 파티를 만들고 {len(invited_ids)}명의 친구에게 초대를 보냈어요!")
            else:
                messages.success(request, f"'{party.name}' 파티를 만들었어요!")
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
            messages.error(request, "미션 이름, 운동 종류, 목표 시간(5~300분)을 확인해 주세요.")
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
            messages.success(request, f"{party.name}의 일일 미션을 만들었어요.")
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
    def dispatch(self, request, *args, **kwargs):
        storage = messages.get_messages(request)
        for _ in storage:
            pass
        return super().dispatch(request, *args, **kwargs)
