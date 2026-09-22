import random
import math
from datetime import date, datetime, time, timedelta
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
from django.urls import reverse
from django.utils import timezone

from .forms import RegisterForm, BattleForm, FriendForm, ProfileForm, WorkoutForm
from .models import BadgeAward, BodyMeasurement, CardBattle, DailyQuest, Facility, FriendLink, FriendRequest, OutfitPurchase, Party, PartyInvitation, PersonalDailyQuest, PokeNotification, WorkoutRecord, needs_kakao_nickname
from .services import (
    add_xp, battle_power, calculate_workout_xp, card_stats,
    check_in_daily_attendance, get_sports_news, get_weather_data,
    sync_mission_progress, sync_party_mission_progress, total_card_xp,
)

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
        user = form.get_user()
        login(request, user)
        return redirect(next_url or ("dashboard" if user.profile.onboarding_completed else "onboarding"))
    return render(request, "fitness/login.html", {"form": form, "next": next_url})


def get_user_party_challenges(user):
    party_challenges = []
    today = timezone.localdate()
    for party in user.parties.all():
        if not party.challenge_start or not party.challenge_end:
            continue
        members = list(party.members.select_related("profile"))
        points_map = dict(
            BadgeAward.objects.filter(
                user__in=members,
                awarded_at__date__range=(party.challenge_start, party.challenge_end),
            )
            .values("user_id")
            .annotate(total=Sum("points"))
            .values_list("user_id", "total")
        )
        rows = []
        for member in members:
            points = points_map.get(member.id, 0) or 0
            rows.append({
                "user_id": member.id,
                "name": member.profile.display_name or member.username,
                "username": member.username,
                "points": points,
                "is_me": member == user,
            })
        rows.sort(key=lambda row: row["points"], reverse=True)
        my_rank = None
        my_points = 0
        for idx, row in enumerate(rows, start=1):
            row["rank"] = idx
            if row["is_me"]:
                my_rank = idx
                my_points = row["points"]
        end_time = party.challenge_end_time or time(23, 59, 59)
        deadline_dt = timezone.make_aware(datetime.combine(party.challenge_end, end_time))
        now = timezone.now()
        is_ended = bool(deadline_dt < now)
        remaining_seconds = max(0, int((deadline_dt - now).total_seconds())) if not is_ended else 0
        days_left = remaining_seconds // 86400
        is_dday = bool(not is_ended and days_left == 0)
        is_urgent = bool(not is_ended and 0 <= days_left <= 2)

        # 실시간 역전 가이드 & 추격 위기 분석
        reversal_guide = None
        pursuit_warning = None
        gap_to_lead = 0
        leader = rows[0] if rows else None
        runner_up = rows[1] if len(rows) > 1 else None

        if not is_ended and len(rows) > 1:
            if my_rank == 1 and runner_up:
                gap = my_points - runner_up["points"]
                if gap <= 0:
                    pursuit_warning = f"⚠️ {runner_up['name']}님과 공동 1위! 지금 운동하고 단독 1위를 굳히세요!"
                elif gap <= 50:
                    pursuit_warning = f"⚠️ 2위 {runner_up['name']}님이 단 {gap}점 차로 맹추격 중! 방심은 금물입니다!"
                else:
                    pursuit_warning = f"👑 2위와 +{gap}점 격차로 독보적인 1위 질주 중!"
            elif my_rank and my_rank > 1 and leader:
                gap_to_lead = leader["points"] - my_points
                if gap_to_lead == 0:
                    reversal_guide = f"🔥 1위 {leader['name']}님과 동점! 지금 30분만 운동하면 즉시 단독 1위 역전!"
                else:
                    if gap_to_lead <= 30:
                        suggested_mins = 30
                    elif gap_to_lead <= 50:
                        suggested_mins = 60
                    elif gap_to_lead <= 100:
                        suggested_mins = 90
                    else:
                        suggested_mins = (gap_to_lead // 100 + 1) * 90
                    reversal_guide = f"🔥 {gap_to_lead}점만 더 따면 1위 {leader['name']}님 역전 가능! (러닝 {suggested_mins}분 추천)"

        party_challenges.append({
            "party": party,
            "rows": rows,
            "is_ended": is_ended,
            "my_rank": my_rank or (len(rows) if rows else 1),
            "my_points": my_points,
            "total_members": len(rows),
            "days_left": max(0, days_left),
            "is_dday": is_dday,
            "is_urgent": is_urgent,
            "deadline_iso": deadline_dt.isoformat(),
            "remaining_seconds": remaining_seconds,
            "end_time_formatted": end_time.strftime("%H:%M"),
            "reversal_guide": reversal_guide,
            "pursuit_warning": pursuit_warning,
            "gap_to_lead": gap_to_lead,
        })
    active_challenges = [c for c in party_challenges if not c["is_ended"]]
    ended_challenges = [c for c in party_challenges if c["is_ended"]]
    return party_challenges, active_challenges, ended_challenges


def dashboard(request):
    if not request.user.is_authenticated:
        return render(request, "fitness/home.html")
    card = request.user.charactercard
    records = WorkoutRecord.objects.filter(user=request.user)
    stats = card_stats(request.user)
    latest_record = records.order_by("-created_at").first()
    latitude, longitude = weather_coordinates(request.user.profile.area)
    
    # 🎯 일일 미션(3개) & 주간 미션(10개) 동기화 및 진행률 계산
    mission_data = sync_mission_progress(request.user)
    daily_missions = mission_data["daily_missions"]
    weekly_missions = mission_data["weekly_missions"]
    today_attended = mission_data["today_attended"]
    week_attendances = mission_data["week_attendances"]
    personal_quests = daily_missions
    completed_personal_ids = {q.id for q in daily_missions if q.is_completed}

    # 👥 파티 미션 허브 (일일 3개 + 주간 10개 순수 파티 협동 미션)
    party_id_param = request.GET.get("party_id")
    if party_id_param and request.user.parties.filter(id=party_id_param).exists():
        active_party = request.user.parties.get(id=party_id_param)
        request.session["active_party_id"] = active_party.id
    elif "active_party_id" in request.session and request.user.parties.filter(id=request.session["active_party_id"]).exists():
        active_party = request.user.parties.get(id=request.session["active_party_id"])
    else:
        user_parties = request.user.parties.order_by("-id")
        active_party = user_parties.filter(
            Q(challenge_end__isnull=True) | Q(challenge_end__gte=timezone.localdate())
        ).first() or user_parties.first()

    party_daily_missions = []
    party_weekly_missions = []
    if active_party:
        party_data = sync_party_mission_progress(active_party, request.user)
        party_daily_missions = party_data["daily_missions"]
        party_weekly_missions = party_data["weekly_missions"]
        group_quests = party_daily_missions
    else:
        group_quests = []

    completed_group_ids = {
        q.id for q in (party_daily_missions + party_weekly_missions)
        if getattr(q, 'is_completed', False)
    }

    party_challenges, active_challenges, ended_challenges = get_user_party_challenges(request.user)
    active_challenge = None
    if active_party:
        active_challenge = next((c for c in party_challenges if c["party"].id == active_party.id), None)

    # 🔔 대기 중인 친구 요청 및 파티 초대
    pending_friend_requests = FriendRequest.objects.filter(
        to_user=request.user, status="PENDING"
    ).select_related("from_user__profile", "from_user__charactercard")
    pending_party_invitations = PartyInvitation.objects.filter(
        invitee=request.user, status="PENDING"
    ).select_related("party", "inviter__profile")

    # 🎉 친구 요청 수락 완료 알림 (내가 보낸 요청 중 상대방이 수락하여 아직 확인하지 않은 알림)
    accepted_friend_requests = FriendRequest.objects.filter(
        from_user=request.user, status="ACCEPTED", sender_viewed=False
    ).select_related("to_user__profile")

    # 🎉 파티 초대 수락 완료 알림 (내가 보낸 파티 초대 중 상대방이 수락하여 아직 확인하지 않은 알림)
    accepted_party_invitations = PartyInvitation.objects.filter(
        inviter=request.user, status="ACCEPTED", inviter_viewed=False
    ).select_related("invitee__profile", "party")

    # 👉 콕 찌르기 (Poke) 미확인 알림
    unread_pokes = PokeNotification.objects.filter(
        receiver=request.user, is_read=False
    ).select_related("sender__profile", "party")[:5]

    return render(request, "fitness/dashboard.html", {
        "card": card, "stats": stats, "power": battle_power(stats, card.level),
        "records": records.order_by("-created_at")[:5],
        "latest_record": latest_record,
        "scene_class": SCENE_MAP.get(latest_record.workout_type if latest_record else "", "run"),
        "friend_count": FriendLink.objects.filter(user=request.user).count(),
        "daily_missions": daily_missions,
        "weekly_missions": weekly_missions,
        "today_attended": today_attended,
        "week_attendances": week_attendances,
        "active_party": active_party,
        "user_all_parties": request.user.parties.all(),
        "party_daily_missions": party_daily_missions,
        "party_weekly_missions": party_weekly_missions,
        "group_quests": group_quests, "personal_quests": personal_quests,
        "completed_personal_ids": completed_personal_ids, "completed_group_ids": completed_group_ids,
        "badge_summary": badge_summary(request.user),
        "party_challenges": party_challenges,
        "active_challenges": active_challenges,
        "active_challenge": active_challenge,
        "ended_challenges": ended_challenges,
        "weather_latitude": latitude, "weather_longitude": longitude,
        "pending_friend_requests": pending_friend_requests,
        "pending_party_invitations": pending_party_invitations,
        "accepted_friend_requests": accepted_friend_requests,
        "accepted_party_invitations": accepted_party_invitations,
        "unread_pokes": unread_pokes,
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


SPORT_FACILITY_CONFIG = {
    "수영": {
        "primary_types": ["수영장"],
        "name_keywords": ["수영", "물놀이", "아쿠아", "풀장"],
    },
    "테니스": {
        "primary_types": ["테니스장"],
        "name_keywords": ["테니스", "라켓"],
    },
    "축구": {
        "primary_types": ["축구장", "풋살장"],
        "name_keywords": ["축구", "풋살"],
    },
    "농구": {
        "primary_types": ["구기체육관"],
        "name_keywords": ["농구", "구기"],
        "secondary_types": ["생활체육관"],
    },
    "배드민턴": {
        "primary_types": ["생활체육관"],
        "name_keywords": ["배드민턴", "셔틀콕"],
        "secondary_types": ["구기체육관"],
    },
    "헬스": {
        "primary_types": ["기타체육시설(체력단련장)"],
        "name_keywords": ["체력단련", "헬스", "웨이트", "피트니스"],
        "secondary_types": ["생활체육관"],
    },
    "러닝": {
        "primary_types": ["육상경기장"],
        "name_keywords": ["육상", "트랙", "러닝", "달리기"],
        "secondary_keywords": ["운동장", "체육공원"],
    },
    "걷기": {
        "primary_types": ["전천후게이트볼장", "파크골프장"],
        "name_keywords": ["산책", "둘레길", "공원", "게이트볼"],
        "secondary_keywords": ["쉼터", "녹지"],
    },
    "만보": {
        "primary_types": ["전천후게이트볼장", "파크골프장"],
        "name_keywords": ["산책", "둘레길", "공원", "게이트볼"],
        "secondary_keywords": ["쉼터", "녹지"],
    },
    "자전거": {
        "primary_types": ["사이클경기장", "롤러스케이트장"],
        "name_keywords": ["자전거", "사이클", "벨로드롬"],
        "secondary_keywords": ["인라인", "스케이트"],
    },
    "등산": {
        "primary_types": ["실외인공암벽장", "실내인공암벽장"],
        "name_keywords": ["등산", "암벽", "클라이밍", "산악"],
        "secondary_keywords": ["산", "고개", "봉"],
    },
    "요가": {
        "primary_types": ["생활체육관"],
        "name_keywords": ["요가", "필라테스", "명상", "스트레칭", "문화체육"],
        "secondary_types": ["구기체육관"],
    },
}


@login_required
def activity_view(request):
    selected_workout = request.GET.get("workout_type", "").strip() or "러닝"
    try:
        current_lat = float(request.GET.get("lat", ""))
        current_lon = float(request.GET.get("lon", ""))
        use_current_location = -90 <= current_lat <= 90 and -180 <= current_lon <= 180
    except (TypeError, ValueError):
        current_lat = current_lon = None
        use_current_location = False

    # 운동 종목 맞춤 시설 필터링 (1순위 전문시설 -> 2순위 연관시설 -> 3순위 일반시설 순)
    cfg = SPORT_FACILITY_CONFIG.get(selected_workout, {})
    primary_q = Q()
    if "primary_types" in cfg:
        primary_q |= Q(facility_type__in=cfg["primary_types"])
    for kw in cfg.get("name_keywords", []):
        primary_q |= Q(name__icontains=kw) | Q(facility_type__icontains=kw)

    secondary_q = Q()
    if "secondary_types" in cfg:
        secondary_q |= Q(facility_type__in=cfg["secondary_types"])
    for kw in cfg.get("secondary_keywords", []):
        secondary_q |= Q(name__icontains=kw)

    # 사전 정의에 없는 커스텀 운동 종목인 경우 이름/유형 검색
    if not cfg and selected_workout:
        primary_q = Q(name__icontains=selected_workout) | Q(facility_type__icontains=selected_workout)

    recommendations = []
    if use_current_location:
        # GPS 위치 기준: 전문 시설 풀에서 최단거리 우선 탐색
        qs = Facility.objects.filter(is_active=True, latitude__isnull=False, longitude__isnull=False)
        pool = list(qs.filter(primary_q)[:400]) if primary_q else []
        if len(pool) < 10 and secondary_q:
            pool += list(qs.filter(secondary_q).exclude(id__in=[f.id for f in pool])[:200])
        if len(pool) < 3:
            pool += list(qs.exclude(id__in=[f.id for f in pool])[:100])

        for facility in pool:
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
        recommendations.sort(key=lambda item: item.distance_km)
        recommendations = recommendations[:3]
    else:
        # 지역 기준: 1순위 전문 시설 -> 2순위 연관 시설 -> 3순위 지역 일반 시설 순으로 보충
        base_qs = Facility.objects.filter(is_active=True, region=request.user.profile.area)
        matches = list(base_qs.filter(primary_q)[:3]) if primary_q else []
        if len(matches) < 3 and secondary_q:
            needed = 3 - len(matches)
            sec_matches = list(base_qs.filter(secondary_q).exclude(id__in=[f.id for f in matches])[:needed])
            matches.extend(sec_matches)
        if len(matches) < 3:
            needed = 3 - len(matches)
            fallback = list(base_qs.exclude(id__in=[f.id for f in matches])[:needed])
            matches.extend(fallback)
        recommendations = matches[:3]
        for facility in recommendations:
            query = quote(f"{facility.name} {facility.address}".strip(), safe="")
            facility.kakao_map_url = (
                f"https://map.kakao.com/link/to/{quote(facility.name, safe='')},{facility.latitude},{facility.longitude}"
                if facility.latitude is not None and facility.longitude is not None
                else f"https://map.kakao.com/link/search/{query}"
            )

    # AJAX 요청인 경우 JSON 응답 반환 (페이지 새로고침 방지 & 입력 데이터 보존)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.GET.get("ajax") == "1":
        return JsonResponse({
            "status": "success",
            "workout_type": selected_workout,
            "facilities": [
                {
                    "id": f.id,
                    "name": f.name,
                    "facility_type": f.facility_type or "공공체육시설",
                    "distance_km": f.distance_km if hasattr(f, "distance_km") else None,
                    "kakao_map_url": f.kakao_map_url,
                }
                for f in recommendations
            ]
        })

    party_challenges, active_challenges, ended_challenges = get_user_party_challenges(request.user)
    ended_count = len(ended_challenges)
    wins_count = sum(1 for c in ended_challenges if c["my_rank"] == 1)
    podium_count = sum(1 for c in ended_challenges if c["my_rank"] in (1, 2, 3))

    return render(request, "fitness/activity.html", {
        "workout_form": WorkoutForm(),
        "selected_workout": selected_workout,
        "records": WorkoutRecord.objects.filter(user=request.user).order_by("-created_at")[:20],
        "recommended_facilities": recommendations,
        "use_current_location": use_current_location,
        "party_challenges": party_challenges,
        "active_challenges": active_challenges,
        "ended_challenges": ended_challenges,
        "challenge_stats": {
            "total_ended": ended_count,
            "wins": wins_count,
            "podium": podium_count,
        },
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
def check_in_attendance(request):
    if request.method != "POST":
        return redirect("dashboard")
    is_first, count = check_in_daily_attendance(request.user)
    if is_first:
        messages.success(request, f"🎉 출석 체크 완료! 30점을 획득했습니다. (이번 주 누적 출석: {count}일)")
    else:
        messages.info(request, f"오늘 이미 출석 체크를 완료했습니다. (이번 주 누적 출석: {count}일)")
    return redirect("dashboard")


@login_required
def complete_daily_quest(request, quest_kind, quest_id):
    if request.method != "POST":
        return redirect("dashboard")
    action = request.POST.get("action", "complete")
    proof_image = request.FILES.get("proof_image")
    if quest_kind in ["personal", "daily", "weekly"]:
        quest = get_object_or_404(PersonalDailyQuest, pk=quest_id, user=request.user, is_active=True)
        if quest.target_minutes and quest.target_minutes > 0:
            b_type = BadgeAward.badge_for_minutes(quest.target_minutes)
            pts = BadgeAward.POINTS[b_type]
        else:
            pts = quest.reward_points or 30
            if pts >= 100:
                b_type = BadgeAward.GOLD
            elif pts >= 50:
                b_type = BadgeAward.SILVER
            else:
                b_type = BadgeAward.BRONZE
        award, created = BadgeAward.objects.get_or_create(
            user=request.user, personal_quest=quest,
            defaults={"badge_type": b_type, "points": pts, "source": "DAILY_QUEST"},
        )
    else:
        quest = get_object_or_404(
            DailyQuest.objects.filter(
                Q(party__challenge_end__isnull=True) | Q(party__challenge_end__gte=timezone.localdate())
            ),
            pk=quest_id, party__members=request.user, is_active=True,
        )
        if quest.target_minutes and quest.target_minutes > 0:
            b_type = BadgeAward.badge_for_minutes(quest.target_minutes)
            pts = BadgeAward.POINTS[b_type]
        else:
            pts = quest.reward_points or 30
            if pts >= 100:
                b_type = BadgeAward.GOLD
            elif pts >= 50:
                b_type = BadgeAward.SILVER
            else:
                b_type = BadgeAward.BRONZE
        award, created = BadgeAward.objects.get_or_create(
            user=request.user, daily_quest=quest,
            defaults={"badge_type": b_type, "points": pts, "source": "DAILY_QUEST"},
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
        is_party = hasattr(quest, "party")
        mission_prefix = ("파티 주간" if getattr(quest, "period_type", "DAILY") == "WEEKLY" else "파티 일일") if is_party else ("주간" if getattr(quest, "period_type", "DAILY") == "WEEKLY" else "일일")
        rec = WorkoutRecord.objects.create(
            user=request.user,
            workout_type=w_type,
            custom_workout_name=custom_name,
            minutes=quest.target_minutes or 20,
            location=f"{mission_prefix}미션 달성",
            proof_image=award.proof_image,
        )
        award.workout_record = rec
        award.save(update_fields=["workout_record"])
        messages.success(request, f"{mission_prefix}미션 완료! {award.get_badge_type_display()} 배지와 {award.points}점을 받았어요. (최근 운동기록 자동 등록)")
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
            messages.info(request, "이미 완료하고 배지를 받은 미션이에요.")
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
        "name": user.profile.display_name or user.username, "area": user.profile.area,
        "level": user.charactercard.level,
        "total_score": BadgeAward.objects.filter(user=user).aggregate(total=Sum("points"))["total"] or 0,
        "is_me": user == current_user, "is_demo": False,
    } for user in users]
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
    active_party = request.user.parties.order_by("-id").first()
    party_member_ids = set(active_party.members.values_list("id", flat=True)) if active_party else set()
    pending_received_requests = FriendRequest.objects.filter(to_user=request.user, status="PENDING").select_related("from_user__profile", "from_user__charactercard")
    pending_sent_requests = FriendRequest.objects.filter(from_user=request.user, status="PENDING").select_related("to_user__profile")
    accepted_requests = FriendRequest.objects.filter(from_user=request.user, status="ACCEPTED", sender_viewed=False).select_related("to_user__profile")
    return render(request, "fitness/friends.html", {
        "friend_form": FriendForm(),
        "friends": friends,
        "active_party": active_party,
        "party_member_ids": party_member_ids,
        "pending_received_requests": pending_received_requests,
        "pending_sent_requests": pending_sent_requests,
        "accepted_requests": accepted_requests,
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
                fr.sender_viewed = False
                fr.save(update_fields=["status", "sender_viewed"])
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
            freq.sender_viewed = False
            freq.save(update_fields=["status", "sender_viewed"])
            FriendLink.objects.get_or_create(user=request.user, friend=freq.from_user)
            FriendLink.objects.get_or_create(user=freq.from_user, friend=request.user)
            messages.success(request, f"{freq.from_user.username}님의 친구 요청을 수락했습니다! 이제 함께 운동할 수 있어요.")
        elif action == "reject":
            freq.status = "REJECTED"
            freq.save(update_fields=["status"])
            messages.info(request, f"{freq.from_user.username}님의 친구 요청을 거절했습니다.")
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"success": True, "action": action, "status": freq.status})
    return redirect(request.POST.get("next") or request.META.get("HTTP_REFERER") or "dashboard")


@login_required
def dismiss_friend_notification(request, request_id):
    if request.method == "POST":
        freq = get_object_or_404(FriendRequest, pk=request_id, from_user=request.user, status="ACCEPTED")
        freq.sender_viewed = True
        freq.save(update_fields=["sender_viewed"])
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"success": True})
    return redirect(request.POST.get("next") or request.META.get("HTTP_REFERER") or "dashboard")


@login_required
def respond_party_invitation(request, invitation_id, action):
    if request.method == "POST":
        inv = get_object_or_404(PartyInvitation, pk=invitation_id, invitee=request.user, status="PENDING")
        if action == "accept":
            inv.status = "ACCEPTED"
            inv.inviter_viewed = False
            inv.save(update_fields=["status", "inviter_viewed"])
            inv.party.members.add(request.user)
            request.session["active_party_id"] = inv.party.id
            messages.success(request, f"'{inv.party.name}' 파티 초대를 수락했습니다! 파티 일일미션 및 내기 챌린지에 참여해보세요.")
        elif action == "reject":
            inv.status = "REJECTED"
            inv.save(update_fields=["status"])
            messages.info(request, f"'{inv.party.name}' 파티 초대를 거절했습니다.")
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"success": True, "action": action, "status": inv.status})
    return redirect(request.POST.get("next") or request.META.get("HTTP_REFERER") or "dashboard")


@login_required
def dismiss_party_notification(request, invitation_id):
    if request.method == "POST":
        inv = get_object_or_404(PartyInvitation, pk=invitation_id, inviter=request.user, status="ACCEPTED")
        inv.inviter_viewed = True
        inv.save(update_fields=["inviter_viewed"])
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"success": True})
    return redirect(request.POST.get("next") or request.META.get("HTTP_REFERER") or "dashboard")


@login_required
def invite_party_member(request, party_id):
    if request.method == "POST":
        party = get_object_or_404(Party, pk=party_id)
        if not party.members.filter(id=request.user.id).exists():
            messages.error(request, "파티에 소속된 멤버만 친구를 초대할 수 있습니다.")
            return redirect(request.POST.get("next") or request.META.get("HTTP_REFERER") or "dashboard")

        if party.members.count() >= party.max_members:
            messages.error(request, f"파티 정원(최대 {party.max_members}명)이 가득 찼습니다.")
            return redirect(request.POST.get("next") or request.META.get("HTTP_REFERER") or "dashboard")

        target_name = request.POST.get("friend_name", "").strip()
        if not target_name:
            messages.error(request, "초대할 친구의 닉네임 또는 아이디를 입력해 주세요.")
            return redirect(request.POST.get("next") or request.META.get("HTTP_REFERER") or "dashboard")

        target_user = User.objects.filter(
            Q(username__iexact=target_name) | Q(first_name__iexact=target_name)
        ).first()

        if not target_user:
            messages.error(request, f"'{target_name}'에 해당하는 사용자를 찾을 수 없습니다. 닉네임 또는 아이디를 확인해주세요.")
        elif target_user == request.user:
            messages.error(request, "본인은 파티에 초대할 수 없습니다.")
        elif party.members.filter(id=target_user.id).exists():
            target_display = target_user.profile.display_name or target_user.username
            messages.info(request, f"{target_display}님은 이미 '{party.name}' 파티의 멤버입니다.")
        elif PartyInvitation.objects.filter(party=party, invitee=target_user, status="PENDING").exists():
            target_display = target_user.profile.display_name or target_user.username
            messages.info(request, f"{target_display}님에게 이미 초대를 보냈습니다. 수락 대기 중입니다.")
        else:
            PartyInvitation.objects.create(
                party=party,
                inviter=request.user,
                invitee=target_user,
                status="PENDING",
            )
            target_display = target_user.profile.display_name or target_user.username
            messages.success(request, f"'{party.name}' 파티에 {target_display}님을 성공적으로 초대했습니다!")
    return redirect(request.POST.get("next") or request.META.get("HTTP_REFERER") or "dashboard")


@login_required
def poke_user(request, user_id):
    if request.method == "POST":
        target = get_object_or_404(User, pk=user_id)
        if target == request.user:
            messages.error(request, "자신을 콕 찌를 수는 없어요.")
            return redirect(request.POST.get("next") or request.META.get("HTTP_REFERER") or "dashboard")

        # 최근 2분 내 중복 찌르기 방지
        recent_poke = PokeNotification.objects.filter(
            sender=request.user,
            receiver=target,
            created_at__gte=timezone.now() - timedelta(minutes=2),
        ).exists()
        if recent_poke:
            target_display = target.profile.display_name or target.username
            messages.info(request, f"방금 {target_display}님을 콕 찔렀어요! 잠시 후 다시 찔러주세요. 👉")
            return redirect(request.POST.get("next") or request.META.get("HTTP_REFERER") or "dashboard")

        party_id = request.POST.get("party_id")
        party = None
        if party_id:
            party = Party.objects.filter(id=party_id, members=request.user).first()

        message = request.POST.get("poke_message", "").strip() or "얼른 운동하고 내기 점수 올려라! 🔥"
        PokeNotification.objects.create(
            sender=request.user,
            receiver=target,
            party=party,
            message=message,
        )
        target_display = target.profile.display_name or target.username
        messages.success(request, f"👉 {target_display}님을 콕 찔렀습니다! ('{message}')")
    return redirect(request.POST.get("next") or request.META.get("HTTP_REFERER") or "dashboard")


@login_required
def dismiss_poke(request, poke_id):
    if request.method == "POST":
        poke = get_object_or_404(PokeNotification, pk=poke_id, receiver=request.user)
        poke.is_read = True
        poke.save(update_fields=["is_read"])
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"success": True})
    return redirect(request.POST.get("next") or request.META.get("HTTP_REFERER") or "dashboard")


@login_required
def notifications_api(request):
    """실시간 알림(친구 요청, 파티 초대, 콕 찌르기) 스마트 폴링을 위한 경량 JSON API"""
    user = request.user

    # 1. 미확인 콕 찌르기 (최신 5개)
    unread_pokes = PokeNotification.objects.filter(
        receiver=user, is_read=False
    ).select_related("sender__profile", "party")[:5]
    poke_list = [
        {
            "id": poke.id,
            "sender_name": poke.sender.profile.display_name or poke.sender.username,
            "party_name": poke.party.name if poke.party else "",
            "message": poke.message,
            "created_at": poke.created_at.strftime("%m/%d %H:%M"),
            "dismiss_url": reverse("dismiss_poke", args=[poke.id]),
        }
        for poke in unread_pokes
    ]

    # 2. 수락된 파티 초대 알림
    accepted_party_invitations = PartyInvitation.objects.filter(
        inviter=user, status="ACCEPTED", inviter_viewed=False
    ).select_related("invitee__profile", "party")
    accepted_party_list = [
        {
            "id": ainv.id,
            "invitee_name": ainv.invitee.profile.display_name or ainv.invitee.username,
            "party_name": ainv.party.name,
            "dismiss_url": reverse("dismiss_party_notification", args=[ainv.id]),
        }
        for ainv in accepted_party_invitations
    ]

    # 3. 수락된 친구 요청 알림
    accepted_friend_requests = FriendRequest.objects.filter(
        from_user=user, status="ACCEPTED", sender_viewed=False
    ).select_related("to_user__profile")
    accepted_friend_list = [
        {
            "id": acc.id,
            "friend_name": acc.to_user.profile.display_name or acc.to_user.username,
            "friend_username": acc.to_user.username,
            "dismiss_url": reverse("dismiss_friend_notification", args=[acc.id]),
        }
        for acc in accepted_friend_requests
    ]

    # 4. 받은 친구 요청
    pending_friend_requests = FriendRequest.objects.filter(
        to_user=user, status="PENDING"
    ).select_related("from_user__profile")
    pending_friend_list = [
        {
            "id": freq.id,
            "from_name": freq.from_user.profile.display_name or freq.from_user.username,
            "from_username": freq.from_user.username,
            "accept_url": reverse("respond_friend_request", args=[freq.id, "accept"]),
            "reject_url": reverse("respond_friend_request", args=[freq.id, "reject"]),
        }
        for freq in pending_friend_requests
    ]

    # 5. 받은 파티 초대
    pending_party_invitations = PartyInvitation.objects.filter(
        invitee=user, status="PENDING"
    ).select_related("party", "inviter__profile")
    pending_party_list = [
        {
            "id": inv.id,
            "inviter_name": inv.inviter.profile.display_name or inv.inviter.username,
            "party_name": inv.party.name,
            "accept_url": reverse("respond_party_invitation", args=[inv.id, "accept"]),
            "reject_url": reverse("respond_party_invitation", args=[inv.id, "reject"]),
        }
        for inv in pending_party_invitations
    ]

    total_count = (
        len(poke_list)
        + len(accepted_party_list)
        + len(accepted_friend_list)
        + len(pending_friend_list)
        + len(pending_party_list)
    )

    return JsonResponse({
        "total_count": total_count,
        "unread_pokes": poke_list,
        "accepted_party_invitations": accepted_party_list,
        "accepted_friend_requests": accepted_friend_list,
        "pending_friend_requests": pending_friend_list,
        "pending_party_invitations": pending_party_list,
    })


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
        friend = User.objects.filter(
            Q(username__iexact=code) | Q(first_name__iexact=code)
        ).first()
        if not friend:
            messages.error(request, f"'{code}'에 해당하는 친구를 찾지 못했어요. 닉네임 또는 아이디를 확인해 주세요.")
        elif friend == request.user:
            messages.error(request, "본인은 친구로 추가할 수 없어요.")
        elif FriendLink.objects.filter(user=request.user, friend=friend).exists():
            messages.info(request, f"{friend.profile.display_name or friend.username}님과는 이미 친구예요.")
        elif FriendRequest.objects.filter(from_user=request.user, to_user=friend, status="PENDING").exists():
            messages.info(request, f"{friend.profile.display_name or friend.username}님에게 이미 친구 요청을 보냈어요. 상대방의 수락을 기다리는 중입니다.")
        elif FriendRequest.objects.filter(from_user=friend, to_user=request.user, status="PENDING").exists():
            fr = FriendRequest.objects.get(from_user=friend, to_user=request.user, status="PENDING")
            fr.status = "ACCEPTED"
            fr.sender_viewed = False
            fr.save(update_fields=["status", "sender_viewed"])
            FriendLink.objects.get_or_create(user=request.user, friend=friend)
            FriendLink.objects.get_or_create(user=friend, friend=request.user)
            messages.success(request, f"{friend.profile.display_name or friend.username}님의 친구 요청을 수락하여 서로 친구가 되었어요!")
        else:
            FriendRequest.objects.create(from_user=request.user, to_user=friend, status="PENDING")
            messages.success(request, f"{friend.profile.display_name or friend.username}님에게 친구 요청을 보냈습니다! 상대방이 수락하면 친구로 등록됩니다.")
        return redirect("onboarding_group")
    if request.method == "POST" and request.POST.get("action") == "create_room":
        room_name = request.POST.get("room_name", "").strip()[:100]
        challenge_reward = request.POST.get("challenge_reward", "").strip()[:200]
        try:
            challenge_start = date.fromisoformat(request.POST.get("challenge_start", ""))
            challenge_end = date.fromisoformat(request.POST.get("challenge_end", ""))
        except (TypeError, ValueError):
            challenge_start = challenge_end = None

        raw_end_time = request.POST.get("challenge_end_time", "").strip()
        challenge_end_time = None
        if raw_end_time:
            try:
                challenge_end_time = time.fromisoformat(raw_end_time)
            except (ValueError, TypeError):
                challenge_end_time = time(23, 59, 59)
        else:
            challenge_end_time = time(23, 59, 59)

        try:
            target_timer_minutes = max(0, int(request.POST.get("target_timer_minutes", 0) or 0))
        except (ValueError, TypeError):
            target_timer_minutes = 0

        if not room_name or not challenge_start or not challenge_end or challenge_end < challenge_start:
            messages.error(request, "파티 이름과 올바른 내기 시작일·종료일을 입력해 주세요.")
        else:
            friend_ids = set(friends.values_list("id", flat=True))
            invited_ids = {
                int(value) for value in request.POST.getlist("invitees")
                if value.isdigit() and int(value) in friend_ids
            }
            direct_invitee_name = request.POST.get("direct_invitee", "").strip()
            if direct_invitee_name:
                direct_user = User.objects.filter(
                    Q(username__iexact=direct_invitee_name) | Q(first_name__iexact=direct_invitee_name)
                ).exclude(id=request.user.id).first()
                if direct_user:
                    invited_ids.add(direct_user.id)
                else:
                    messages.warning(request, f"입력하신 '{direct_invitee_name}'님을 찾지 못하여 파티 초대 대상에서 제외되었습니다.")
            with transaction.atomic():
                party = Party.objects.create(
                    name=room_name, owner=request.user,
                    challenge_start=challenge_start, challenge_end=challenge_end,
                    challenge_end_time=challenge_end_time,
                    target_timer_minutes=target_timer_minutes,
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
                request.session["active_party_id"] = party.id
            # 1단계(기간·타이머) 완료 후 파티 생성 완료 알림을 띄우지 않고 자연스럽게 다음(미션 설정) 단계로 이동
            return redirect("onboarding_group_quest", party_id=party.id)
    return render(request, "fitness/onboarding_group.html", {
        "friends": friends, "friend_form": FriendForm(),
    })


@login_required
def onboarding_group_quest(request, party_id):
    party = get_object_or_404(Party, pk=party_id, owner=request.user)
    workout_choices = WorkoutRecord.WORKOUT_CHOICES
    if request.method == "POST":
        action = request.POST.get("action", "direct")
        if action in ["ai", "facility"]:
            from .services import generate_party_daily_missions, generate_party_weekly_missions
            generate_party_daily_missions(party)
            generate_party_weekly_missions(party)
            party.workout_type = "러닝"
            party.save(update_fields=["workout_type"])
            profile = request.user.profile
            profile.workout_mode = "GROUP"
            profile.onboarding_completed = True
            profile.save(update_fields=["workout_mode", "onboarding_completed"])
            messages.success(request, f"🎉 '{party.name}' 파티가 생성되었습니다! AI 일일(3개) & 주간(10개) 협동 미션이 시작됩니다.")
            return redirect("dashboard")

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
            # 파티의 대표 운동 종류 업데이트
            party.workout_type = custom_workout_name if workout_type == "기타" else workout_type
            if target_minutes and not party.target_timer_minutes:
                party.target_timer_minutes = target_minutes
            party.save(update_fields=["workout_type", "target_timer_minutes"])

            DailyQuest.objects.create(
                party=party, creator=request.user, title=title,
                workout_type=workout_type, custom_workout_name=custom_workout_name,
                target_minutes=target_minutes,
                period_type="DAILY",
                mission_category="WORKOUT",
                source="DIRECT",
            )
            from .services import generate_party_daily_missions, generate_party_weekly_missions
            generate_party_daily_missions(party)
            generate_party_weekly_missions(party)
            profile = request.user.profile
            profile.workout_mode = "GROUP"
            profile.onboarding_completed = True
            profile.save(update_fields=["workout_mode", "onboarding_completed"])
            messages.success(request, f"🎉 '{party.name}' 파티가 생성되었습니다! (운동 종목: {party.workout_type})")
            return redirect("dashboard")
    return render(request, "fitness/onboarding_group_quest.html", {
        "party": party, "workout_choices": workout_choices,
        "members": party.members.select_related("profile").all(),
    })


@login_required
def region_view(request):
    card = request.user.charactercard
    real_region_users = User.objects.filter(profile__area=request.user.profile.area, profile__rank_participation=True).select_related("profile", "charactercard")[:10]
    region_rows = [{
        "name": u.profile.display_name or u.username,
        "area": u.profile.area,
        "level": u.charactercard.level,
        "total_xp": BadgeAward.objects.filter(user=u).aggregate(total=Sum("points"))["total"] or 0,
    } for u in real_region_users]
    region_rows.sort(key=lambda r: r["total_xp"], reverse=True)
    return render(request, "fitness/region.html", {
        "card": card, "stats": card_stats(request.user),
        "power": battle_power(card_stats(request.user), card.level),
        "region_rows": region_rows,
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
        }),
        "battles": battles,
        "demo_opponents": [],
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


def teunteun_popup_view(request):
    """국민체력100 튼튼머니 실제 브라우저 팝업(window.open) 전용 가벼운 뷰"""
    return render(request, "fitness/teunteun_window_popup.html")
