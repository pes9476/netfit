import numpy as np
import datetime
import email.utils
import time
import urllib.request
import xml.etree.ElementTree as ET
import requests
from .models import WorkoutRecord

_news_cache = {
    "expires": 0,
    "last_fetched": 0,
    "items": [],
    "current_batch": 0,
}


def get_sports_news(limit=6, refresh=False, page=None):
    """Google News 스포츠 RSS를 읽고 최대 36건을 캐싱하며,
    새로고침 또는 페이지 요청 시 다음 뉴스 묶음을 제공합니다."""
    now = time.time()
    should_fetch_rss = (
        not _news_cache["items"]
        or now > _news_cache["expires"]
        or (refresh and (now - _news_cache["last_fetched"]) > 45)
    )

    if should_fetch_rss:
        url = "https://news.google.com/rss/headlines/section/topic/SPORTS?hl=ko&gl=KR&ceid=KR:ko"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "NETFIT/1.0"})
            with urllib.request.urlopen(req, timeout=4) as response:
                root = ET.fromstring(response.read())
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            fetched_items = []
            for node in root.findall(".//channel/item")[:36]:
                raw_title = (node.findtext("title") or "").strip()
                headline, source = raw_title, "스포츠 뉴스"
                if " - " in raw_title:
                    headline, source = [part.strip() for part in raw_title.rsplit(" - ", 1)]
                published = node.findtext("pubDate") or ""
                time_label = "최신"
                if published:
                    try:
                        seconds = max(0, (now_utc - email.utils.parsedate_to_datetime(published)).total_seconds())
                        time_label = (
                            f"{int(seconds // 60)}분 전"
                            if seconds < 3600
                            else f"{int(seconds // 3600)}시간 전"
                            if seconds < 86400
                            else f"{int(seconds // 86400)}일 전"
                        )
                    except (TypeError, ValueError):
                        pass
                fetched_items.append({
                    "title": headline,
                    "source": source,
                    "time": time_label,
                    "url": node.findtext("link") or "#",
                })
            if fetched_items:
                _news_cache["items"] = fetched_items
                _news_cache["last_fetched"] = now
                _news_cache["expires"] = now + 600
        except Exception:
            pass

    items = _news_cache["items"]
    if not items:
        return []

    total_items = len(items)
    total_pages = max(1, (total_items + limit - 1) // limit)

    if page is not None:
        target_page = page % total_pages
    elif refresh:
        _news_cache["current_batch"] = (_news_cache["current_batch"] + 1) % total_pages
        target_page = _news_cache["current_batch"]
    else:
        target_page = 0

    start = target_page * limit
    batch = items[start : start + limit]
    if len(batch) < limit and total_items >= limit:
        batch += items[: limit - len(batch)]
    return batch

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


# 1. 17개 시/도 기본 좌표 (GPS 미수신 시 Fallback)
REGION_COORDINATES = {
    "서울특별시": (37.5665, 126.9780), "부산광역시": (35.1796, 129.0756),
    "대구광역시": (35.8714, 128.6014), "인천광역시": (37.4563, 126.7052),
    "광주광역시": (35.1595, 126.8526), "대전광역시": (36.3504, 127.3845),
    "울산광역시": (35.5384, 129.3114), "세종특별자치시": (36.4800, 127.2890),
    "경기도": (37.2750, 127.0094), "강원특별자치도": (37.8854, 127.7298),
    "충청북도": (36.6357, 127.4912), "충청남도": (36.6588, 126.6728),
    "전북특별자치도": (35.8242, 127.1480), "전라남도": (34.8161, 126.4629),
    "경상북도": (36.5760, 128.5056), "경상남도": (35.2383, 128.6925),
    "제주특별자치도": (33.4996, 126.5312),
}

# 2. WMO 기상 코드 분석
def interpret_weather_code(code, temp=20):
    if code == 0:
        cond, icon, color = "맑음", "fa-sun", "#F59E0B"
        msg = "쾌청한 맑은 날씨! 야외 러닝과 라이딩하기에 최적입니다."
    elif code in [1, 2]:
        cond, icon, color = "구름 조금", "fa-cloud-sun", "#38BDF8"
        msg = "선선하고 쾌적한 날씨, 야외 인터벌 트레이닝을 추천합니다!"
    elif code == 3:
        cond, icon, color = "흐림", "fa-cloud", "#94A3B8"
        msg = "햇빛 걱정 없이 시원하게 유산소 운동하기에 좋습니다."
    elif code in [45, 48]:
        cond, icon, color = "안개", "fa-smog", "#94A3B8"
        msg = "시야가 다소 흐리니 안전에 유의하여 가볍게 조깅하세요."
    elif code in [51, 53, 55, 61, 63, 65, 80, 81, 82]:
        cond, icon, color = "비/소나기", "fa-cloud-showers-heavy", "#60A5FA"
        msg = "비가 오니 실내 체육관 근력 운동이나 수영을 추천합니다."
    elif code in [71, 73, 75, 77, 85, 86]:
        cond, icon, color = "눈", "fa-snowflake", "#E0F2FE"
        msg = "눈이 오니 미끄럼에 유의하시고 실내 홈트를 즐겨보세요."
    elif code in [95, 96, 99]:
        cond, icon, color = "뇌우", "fa-bolt", "#F43F5E"
        msg = "낙뢰 위험이 있으니 야외 운동을 피하고 실내 휴식을 권장합니다."
    else:
        cond, icon, color = "보통", "fa-cloud-sun", "#00F59B"
        msg = "오늘도 활기차게 운동하고 체력을 길러보세요!"

    if temp >= 30:
        msg = "기온이 높으니 충분한 수분을 섭취하며 무리하지 마세요."
    elif temp <= 0:
        msg = "영하의 기온입니다. 부상 방지를 위해 충분한 웜업 후 운동하세요."
    return cond, icon, color, msg

# 3. 실시간 GPS 좌표 -> 실제 한국 동네명 역지오코딩 (가산동, 부평동 등)
def reverse_geocode_korean(lat, lon):
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&accept-language=ko"
        r = requests.get(url, headers={"User-Agent": "NetFitApp/1.0"}, timeout=2.2)
        if r.status_code == 200:
            addr = r.json().get("address", {})
            city = addr.get("city") or addr.get("province") or addr.get("state") or ""
            city = city.replace("특별시", "").replace("광역시", "").replace("특별자치시", "").replace("특별자치도", "")
            borough = addr.get("borough") or addr.get("district") or addr.get("suburb") or ""
            quarter = addr.get("quarter") or addr.get("neighbourhood") or addr.get("village") or ""
            parts = [p for p in [city, borough, quarter] if p and p != borough]
            if len(parts) >= 2:
                return " ".join(parts)
            elif len(parts) == 1:
                return parts[0]
    except Exception:
        pass

    try:
        url = f"https://api.bigdatacloud.net/data/reverse-geocode-client?latitude={lat}&longitude={lon}&localityLanguage=ko"
        r = requests.get(url, timeout=2.0)
        if r.status_code == 200:
            d = r.json()
            city = d.get("principalSubdivision", "").replace("특별시", "").replace("광역시", "").replace("특별자치시", "").replace("특별자치도", "")
            locality = d.get("locality", "")
            parts = [p for p in [city, locality] if p]
            if parts:
                return " ".join(parts)
    except Exception:
        pass

    return "내 위치 (실시간 GPS)"

# 4. 실시간 날씨 데이터 수집 함수 (Open-Meteo 무료 API)
def get_weather_data(lat=37.5665, lon=126.9780, location_name="서울특별시", is_gps=False):
    if is_gps or location_name in ["실시간 GPS 위치", "내 위치", "실시간 GPS"]:
        real_location = reverse_geocode_korean(lat, lon)
        if real_location:
            location_name = real_location

    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&timezone=auto"
    try:
        r = requests.get(url, timeout=3.5).json()
        current = r.get("current_weather", {})
        temp = current.get("temperature", 20.0)
        wind = current.get("windspeed", 2.0)
        code = current.get("weathercode", 0)
        condition, icon, color, msg = interpret_weather_code(code, temp)

        return {
            "temperature": round(float(temp), 1),
            "windspeed": round(float(wind), 1),
            "weather_code": code,
            "condition": condition,
            "icon": icon,
            "color": color,
            "message": msg,
            "location_name": location_name,
            "is_gps": is_gps,
            "lat": float(lat), "lon": float(lon),
        }
    except Exception:
        return {
            "temperature": 21.0, "windspeed": 2.5, "weather_code": 0,
            "condition": "맑음", "icon": "fa-cloud-sun", "color": "#38BDF8",
            "message": "오늘도 활기차게 운동을 시작해보세요!",
            "location_name": location_name, "is_gps": is_gps,
            "lat": float(lat), "lon": float(lon),
        }

