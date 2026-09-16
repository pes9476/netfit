import numpy as np
import datetime
import email.utils
import time
import urllib.request
import xml.etree.ElementTree as ET
from .models import WorkoutRecord

_news_cache = {"expires": 0, "items": []}


def get_sports_news(limit=6):
    """Google News 스포츠 RSS를 읽고 10분간 메모리에 보관한다."""
    now = time.time()
    if _news_cache["items"] and _news_cache["expires"] > now:
        return _news_cache["items"][:limit]
    url = "https://news.google.com/rss/headlines/section/topic/SPORTS?hl=ko&gl=KR&ceid=KR:ko"
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "NETFIT/1.0"})
        with urllib.request.urlopen(request, timeout=4) as response:
            root = ET.fromstring(response.read())
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        items = []
        for node in root.findall(".//channel/item")[:limit]:
            raw_title = (node.findtext("title") or "").strip()
            headline, source = raw_title, "스포츠 뉴스"
            if " - " in raw_title:
                headline, source = [part.strip() for part in raw_title.rsplit(" - ", 1)]
            published = node.findtext("pubDate") or ""
            time_label = "최신"
            if published:
                try:
                    seconds = max(0, (now_utc - email.utils.parsedate_to_datetime(published)).total_seconds())
                    time_label = f"{int(seconds // 60)}분 전" if seconds < 3600 else f"{int(seconds // 3600)}시간 전" if seconds < 86400 else f"{int(seconds // 86400)}일 전"
                except (TypeError, ValueError):
                    pass
            items.append({"title": headline, "source": source, "time": time_label, "url": node.findtext("link") or "#"})
        if items:
            _news_cache.update({"expires": now + 600, "items": items})
        return items
    except Exception:
        return []

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
