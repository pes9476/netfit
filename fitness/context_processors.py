from django.db import models
from django.utils import timezone

from .models import BadgeAward, DailyQuest, PersonalDailyQuest


def quest_menu(request):
    if not request.user.is_authenticated:
        return {}

    personal = list(PersonalDailyQuest.objects.filter(user=request.user, is_active=True)[:5])
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
            "detail": f"개인 · {quest.workout_label} {quest.target_minutes}분",
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
    return {
        "header_quests": entries,
        "header_quest_pending_count": sum(not entry["completed"] for entry in entries),
    }
