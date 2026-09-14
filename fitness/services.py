import numpy as np
from .models import WorkoutRecord

def calculate_workout_xp(minutes, distance_km, with_party):
    # NumPy로 운동 수치를 배열 연산하여 XP를 계산합니다.
    values = np.array([30, 50 if minutes >= 30 else 0, min(50, round(float(distance_km) * 10)), 50 if with_party else 0])
    return int(values.sum())

def add_xp(card, gained_xp):
    card.xp += gained_xp
    while card.xp >= card.next_level_xp:
        card.xp -= card.next_level_xp
        card.level += 1
    card.frame = card.card_tier
    card.save()

def card_stats(user):
    records = WorkoutRecord.objects.filter(user=user)
    level = user.charactercard.level
    minutes = np.array([r.minutes for r in records], dtype=float)
    distances = np.array([float(r.distance_km) for r in records], dtype=float)
    party_count = sum(r.with_party for r in records)
    total_minutes = minutes.sum() if len(minutes) else 0
    total_distance = distances.sum() if len(distances) else 0
    return {
        "speed": int(np.clip(total_distance * 3 + 30 + level * 2, 0, 99)),
        "stamina": int(np.clip(total_minutes / 8 + 25 + level * 2, 0, 99)),
        "motivation": int(np.clip(len(records) * 4 + party_count * 6 + 25 + level * 3, 0, 99)),
    }

def battle_power(stats, level):
    weights = np.array([0.40, 0.35, 0.25])
    values = np.array([stats["speed"], stats["stamina"], stats["motivation"]])
    return int(np.dot(values, weights) + level * 5)


def total_card_xp(card):
    """레벨업에 사용된 경험치와 현재 경험치를 합친 랭킹용 누적치입니다."""
    spent_xp = sum(300 + step * 100 for step in range(max(card.level - 1, 0)))
    return spent_xp + card.xp
