from datetime import datetime, time

from django.core.cache import cache
from django.db import models
from django.utils import timezone

from .models import BadgeAward, DailyQuest, FriendRequest, PartyInvitation, PersonalDailyQuest


def quest_menu(request):
    if not request.user.is_authenticated:
        return {}

    cache_key = f"user_header_summary_{request.user.id}"
    if request.method != "GET":
        cache.delete(cache_key)
    else:
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result

    personal = list(PersonalDailyQuest.objects.filter(user=request.user, is_active=True, period_type="DAILY")[:3])
    group = list(
        DailyQuest.objects.filter(party__members=request.user, is_active=True)
        .filter(models.Q(party__challenge_end__isnull=True) | models.Q(party__challenge_end__gte=timezone.localdate()))
        .select_related("party")
        .distinct()[:5]
    )
    completed_personal = set(
        BadgeAward.objects.filter(user=request.user, personal_quest__in=personal)
        .values_list("personal_quest_id", flat=True)
    )
    completed_group = set(
        BadgeAward.objects.filter(user=request.user, daily_quest__in=group)
        .values_list("daily_quest_id", flat=True)
    )
    entries = [
        {
            "title": quest.title,
            "detail": f"일일 · {quest.workout_label}" + (f" {quest.target_minutes}분" if quest.target_minutes else ""),
            "completed": quest.id in completed_personal,
        }
        for quest in personal
    ]
    entries.extend(
        {
            "title": quest.title,
            "detail": f"{quest.party.name} · {quest.workout_label} {quest.target_minutes}분",
            "completed": quest.id in completed_group,
        }
        for quest in group
    )

    # 🔔 친구 요청 및 수락 알림 카운트
    pending_friend_count = FriendRequest.objects.filter(to_user=request.user, status="PENDING").count()
    accepted_friend_count = FriendRequest.objects.filter(from_user=request.user, status="ACCEPTED", sender_viewed=False).count()
    header_friend_alert_count = pending_friend_count + accepted_friend_count

    # 🔔 파티 초대 알림 카운트
    pending_party_invitation_count = PartyInvitation.objects.filter(invitee=request.user, status="PENDING").count()

    # 👥 지난 내기 기록은 보존하되, 종료된 파티는 그룹원 메뉴에서 제외한다.
    now = timezone.now()
    today = timezone.localdate(now)
    party_candidates = (
        request.user.parties
        .filter(models.Q(challenge_end__isnull=True) | models.Q(challenge_end__gte=today))
        .prefetch_related("members__profile")
    )
    header_user_parties = []
    for party in party_candidates:
        if party.challenge_end is None:
            header_user_parties.append(party)
            continue
        end_time = party.challenge_end_time or time(23, 59, 59)
        deadline = timezone.make_aware(
            datetime.combine(party.challenge_end, end_time),
            timezone.get_current_timezone(),
        )
        if deadline >= now:
            header_user_parties.append(party)

    data = {
        "header_quests": entries,
        "header_quest_pending_count": sum(not entry["completed"] for entry in entries),
        "pending_friend_count": pending_friend_count,
        "accepted_friend_count": accepted_friend_count,
        "header_friend_alert_count": header_friend_alert_count,
        "pending_party_invitation_count": pending_party_invitation_count,
        "header_user_parties": header_user_parties,
    }
    cache.set(cache_key, data, timeout=10)
    return data
