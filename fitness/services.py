import numpy as np
import datetime
import email.utils
import time
import urllib.request
import xml.etree.ElementTree as ET
import requests
from django.db.models import Sum, Count, Q
from django.utils import timezone
from .models import AttendanceRecord, BadgeAward, DailyQuest, Facility, Party, PersonalDailyQuest, WorkoutRecord

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
    "전남광주통합특별시": (35.1595, 126.8526), "대전광역시": (36.3504, 127.3845),
    "울산광역시": (35.5384, 129.3114), "세종특별자치시": (36.4800, 127.2890),
    "경기도": (37.2750, 127.0094), "강원특별자치도": (37.8854, 127.7298),
    "충청북도": (36.6357, 127.4912), "충청남도": (36.6588, 126.6728),
    "전북특별자치도": (35.8242, 127.1480),
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


# ==============================================================================
# 🎯 미션 시스템 서비스 (일일 미션 3개 & 주간 미션 10개, 출석 및 주간 누적)
# ==============================================================================

def get_current_week_bounds(target_date=None):
    """지정된 날짜(기본값: 오늘)의 이번 주 월요일(시작)과 일요일(종료) 날짜를 반환합니다."""
    if target_date is None:
        target_date = timezone.localdate()
    week_start = target_date - datetime.timedelta(days=target_date.weekday())
    week_end = week_start + datetime.timedelta(days=6)
    return week_start, week_end


# 1) 솔로 일일 미션 요일별 / 테마별 로테이션 풀
SOLO_DAILY_WORKOUT_POOLS = {
    "SENIOR": [
        ("월요 관절 친화 활력 산책 20분", "관절에 무리 없는 편안한 산책으로 체력을 유지하세요.", "걷기", 20, 30),
        ("화요 척추 건강 보행 운동 20분", "바른 자세를 유지하며 보폭을 넓혀 걸어보세요.", "걷기", 20, 30),
        ("수요 전신 스트레칭 & 체조 20분", "온몸의 근육을 부드럽게 이완하고 유연성을 기르세요.", "기타", 20, 30),
        ("목요 허리 안심 가벼운 걷기 20분", "기분 좋은 속도로 허리와 하체 힘을 키워보세요.", "걷기", 20, 30),
        ("금요 웰빙 밸런스 체조 20분", "신체 균형 감각을 높이는 실버 웰빙 체조를 실천하세요.", "기타", 20, 30),
        ("토요 주말 힐링 파크 산책 25분", "신선한 공기를 마시며 자연 속에서 편안하게 걸어보세요.", "걷기", 25, 30),
        ("일요 활력 충전 릴랙스 워킹 20분", "가벼운 호흡과 함께 산뜻하게 한 주를 마무리하세요.", "걷기", 20, 30),
    ],
    "DIET": [
        ("월요 체지방 버닝 인터벌 러닝 30분", "빠른 지방 연소를 위한 활력 넘치는 유산소 러닝!", "러닝", 30, 50),
        ("화요 하체 파워 타바타 버닝 25분", "칼로리 소모를 극대화하는 하체 인터벌 서킷!", "헬스", 25, 50),
        ("수요 스피드 유산소 페이스 런 30분", "심박수를 올려 체지방을 가속 소모하는 러닝 세션!", "러닝", 30, 50),
        ("목요 전신 칼로리 컷 트레이닝 30분", "다양한 유산소와 맨몸 운동으로 땀방울을 흘려보세요.", "기타", 30, 50),
        ("불금 한계 돌파 인터벌 러닝 35분", "강력한 유산소 자극으로 지방을 남김없이 태우세요!", "러닝", 35, 50),
        ("토요 주말 야외 롱디스턴스 런 40분", "맑은 공기를 가르며 주말 야외 유산소를 만끽하세요.", "러닝", 40, 50),
        ("일요 디톡스 리커버리 조깅 30분", "가벼운 조깅으로 노폐물을 배출하고 컨디션을 되찾으세요.", "러닝", 30, 50),
    ],
    "STRENGTH": [
        ("월요 상·하체 밸런스 근력 운동 30분", "주요 근육군을 자극하는 집중 근력 트레이닝을 실천하세요.", "헬스", 30, 50),
        ("화요 하체 파워 스쿼트 & 런지 30분", "탄탄한 하체와 둔근을 단련하는 하체 데이!", "헬스", 30, 50),
        ("수요 상체 덤벨 & 푸시업 트레이닝 30분", "가슴, 어깨, 삼두 근육을 자극하는 상체 집중 루틴.", "헬스", 30, 50),
        ("목요 등·코어 풀업 & 플랭크 30분", "등 근육과 중심 코어를 단단하게 잡는 스트렝스 세션.", "헬스", 30, 50),
        ("불금 전신 슈퍼세트 파워 웨이트 35분", "쉬지 않고 전신을 자극하는 불금 고강도 근력 운동!", "헬스", 35, 50),
        ("토요 주말 파워풀 프리웨이트 40분", "충분한 휴식과 함께 최고 중량에 도전하는 주말 세션.", "헬스", 40, 50),
        ("일요 전신 밸런스 홈 스트렝스 30분", "한 주를 정리하며 전신의 균형을 맞추는 근력 운동.", "헬스", 30, 50),
    ],
    "HEALTH": [
        ("월요 활력 충전 유산소 러닝 30분", "하루를 상쾌하게 깨우는 활력 러닝으로 에너지를 충전하세요.", "러닝", 30, 50),
        ("화요 코어 복근 & 전신 순환 운동 25분", "코어를 탄탄하게 잡고 혈액순환을 촉진하는 데일리 운동.", "기타", 25, 40),
        ("수요 리프레시 힐링 조깅 30분", "스트레스를 날려버리는 상쾌한 중간 점검 조깅!", "러닝", 30, 50),
        ("목요 전신 밸런스 인터벌 30분", "심폐 지구력과 유연성을 동시에 길러주는 복합 세션.", "기타", 30, 50),
        ("불금 칼로리 버닝 런 35분", "주말을 앞두고 활기찬 에너지로 달리는 러닝 세션.", "러닝", 35, 50),
        ("토요 주말 아웃도어 조깅 40분", "기분 좋은 페이스로 야외 러닝 트랙을 달려보세요.", "러닝", 40, 50),
        ("일요 컨디셔닝 회복 런 25분", "가벼운 호흡으로 다음 주를 준비하는 릴랙스 조깅.", "러닝", 25, 40),
    ],
}

SOLO_DAILY_NO_FACILITY_THEMES = [
    ("전신 코어 스트레칭 및 요가 20분", "몸의 긴장을 풀고 유연성과 코어 근육을 단련하세요.", "요가", 20, 30),
    ("하체 피로 회복 폼롤러 스트레칭 20분", "종아리와 허벅지 근육을 이완시켜 피로를 해소하세요.", "요가", 20, 30),
    ("상체 라인 교정 덤벨 트레이닝 25분", "어깨와 등 라인을 바르게 세우는 교정 운동입니다.", "헬스", 25, 40),
    ("맨몸 칼리스데닉스 턱걸이 & 푸시업 25분", "기구 없이 맨몸으로 탄탄한 근력을 기르세요.", "헬스", 25, 40),
    ("심폐 지구력 강화 제자리 달리기 & 점핑잭 20분", "간단한 동작으로 심폐 지구력을 효과적으로 향상시키세요.", "러닝", 20, 30),
    ("자세 교정 필라테스 루틴 25분", "신체 밸런스와 자세 교정을 위한 집중 필라테스 루틴.", "요가", 25, 40),
    ("힐링 슬로우 스트레칭 & 명상 20분", "호흡을 가다듬고 몸과 마음의 긴장을 부드럽게 풀어내세요.", "기타", 20, 30),
]

# 2) 파티 일일 미션 요일별 / 테마별 로테이션 풀 (출석 제외)
PARTY_DAILY_CARDIO_POOLS = [
    ("파티 월요 스타트 협동 러닝 30분", "새로운 한 주를 여는 파티원들과의 30분 유산소 러닝 세션!", "러닝", 30, 50),
    ("파티 화요 인터벌 페이스 런 30분", "서로의 페이스를 맞춰 달리며 심폐 지구력을 키워보세요.", "러닝", 30, 50),
    ("파티 수요 활력 유산소 챌린지 35분", "한 주의 중간을 시원하게 달리는 35분 파티 러닝 세션!", "러닝", 35, 50),
    ("파티 목요 지구력 러닝 30분", "지치지 않는 파티의 에너지를 보여주는 30분 유산소 달리기.", "러닝", 30, 50),
    ("파티 불금 하이퍼 버닝 런 35분", "불타는 금요일! 파티원들과 뜨거운 땀방울을 함께 흘려보세요.", "러닝", 35, 50),
    ("파티 주말 롱코스 트레킹 & 러닝 40분", "주말 야외에서 파티원들과 함께 즐기는 여유롭고 긴 러닝!", "러닝", 40, 50),
    ("파티 일요 리커버리 조깅 25분", "한 주를 기분 좋게 마무리하는 편안한 파티 조깅 세션.", "러닝", 25, 40),
]

PARTY_DAILY_STRENGTH_POOLS = [
    ("파티원과 함께 상체 집중 웨이트 30분", "상체 근육을 함께 단련하며 동기부여를 얻어보세요.", "헬스", 30, 50),
    ("파티원과 함께 하체 스쿼트 챌린지 30분", "탄탄한 하체를 위해 파티원들과 스쿼트 세션을 완수하세요.", "헬스", 30, 50),
    ("파티원과 함께 전신 코어 트레이닝 30분", "흔들리지 않는 코어를 위해 플랭크와 복근 운동을 함께하세요.", "헬스", 30, 50),
    ("파티원과 함께 고강도 서킷 트레이닝 35분", "빠른 순환 서킷으로 근력과 심폐 기능을 동시에 자극하세요.", "헬스", 35, 50),
    ("파티원과 함께 파워 덤벨 & 바벨 운동 30분", "불금의 에너지를 근력 운동에 쏟아부어 한계에 도전하세요.", "헬스", 30, 50),
    ("파티원과 함께 스포츠/클라이밍 세션 40분", "다양한 실내외 스포츠 종목으로 활력 넘치게 땀을 흘려보세요.", "기타", 40, 50),
    ("파티원과 함께 전신 스트레칭 & 모빌리티 25분", "다음 주를 대비해 온몸의 관절과 근육을 유연하게 풀어주세요.", "요가", 25, 40),
]

PARTY_DAILY_NO_FACILITY_THEMES = [
    ("파티 맨몸 타바타 챌린지 25분", "파티원들과 박자에 맞춰 25분 타바타 세션을 클리어하세요.", "헬스", 25, 40),
    ("파티 코어 플랭크 & 크런치 릴레이 20분", "파티원 전원이 참여하는 20분 릴레이 코어 운동!", "헬스", 20, 30),
    ("파티 100회 버피 챌린지 세션 25분", "다 함께 호흡을 맞추며 버피 챌린지를 완수해보세요.", "기타", 25, 40),
    ("파티 유산소 스텝박스 트레이닝 25분", "리듬감 넘치는 스텝 운동으로 하체와 심폐를 단련하세요.", "기타", 25, 40),
    ("파티 밸런스 요가 릴랙스 25분", "차분하게 호흡을 모아 파티원들과 밸런스를 맞춰보세요.", "요가", 25, 40),
    ("파티 스피드 셔틀런 릴레이 30분", "빠른 방향 전환과 스프린트로 순발력을 길러보세요.", "러닝", 30, 50),
    ("파티 전신 파워 버닝 루틴 30분", "일요일 마무리! 전신을 깨우는 파티 합동 루틴을 완수하세요.", "기타", 30, 50),
]

# 2-1) 파티 목표 운동 종목별 일일 메인 미션 템플릿 풀 (매일 요일별 로테이션)
WORKOUT_PARTY_DAILY_TEMPLATES = {
    "러닝": [
        ("파티 월요 스타트 협동 러닝 30분", "새로운 한 주를 여는 파티원들과의 30분 유산소 러닝 세션!", 30, 50),
        ("파티 화요 인터벌 페이스 러닝 30분", "서로의 페이스를 맞춰 달리며 심폐 지구력을 키워보세요.", 30, 50),
        ("파티 수요 활력 유산소 러닝 35분", "한 주의 중간을 시원하게 달리는 35분 파티 러닝 세션!", 35, 50),
        ("파티 목요 지구력 지속 러닝 30분", "지치지 않는 파티의 에너지를 보여주는 30분 유산소 달리기.", 30, 50),
        ("파티 불금 하이퍼 버닝 러닝 35분", "불타는 금요일! 파티원들과 뜨거운 땀방울을 함께 흘려보세요.", 35, 50),
        ("파티 주말 롱코스 트레킹 & 러닝 40분", "주말 야외에서 파티원들과 함께 즐기는 여유롭고 긴 러닝!", 40, 50),
        ("파티 일요 리커버리 러닝 25분", "한 주를 기분 좋게 마무리하는 편안한 파티 러닝 세션.", 25, 40),
    ],
    "헬스": [
        ("파티 월요 가슴 & 삼두 협동 웨이트 30분", "새로운 한 주! 상체 근육을 함께 단련하며 동기부여를 얻어보세요.", 30, 50),
        ("파티 화요 등 & 이두 풀 데이 30분", "파티원들과 함께 당기는 근육을 집중 자극해보세요.", 30, 50),
        ("파티 수요 하체 스쿼트 챌린지 35분", "탄탄한 하체를 위해 파티원들과 스쿼트 세션을 완수하세요.", 35, 50),
        ("파티 목요 어깨 숄더 프레스 집중 30분", "어깨 볼륨과 상체 밸런스를 잡는 파티 웨이트 세션.", 30, 50),
        ("파티 불금 전신 파워 서킷 버닝 35분", "불금의 에너지를 전신 서킷 웨이트에 쏟아부어 한계에 도전하세요.", 35, 50),
        ("파티 주말 코어 & 기능성 트레이닝 40분", "주말 동안 파티원들과 흔들림 없는 코어와 근력을 다져보세요.", 40, 50),
        ("파티 일요 스트레칭 & 모빌리티 25분", "한 주 동안 지친 관절과 근육을 유연하게 풀어주는 회복 세션.", 25, 40),
    ],
    "수영": [
        ("파티 자유형 폼 & 페이스 협동 수영 30분", "파티원들과 일정한 페이스로 시원하게 물살을 갈라보세요.", 30, 50),
        ("파티 평영 & 배영 밸런스 수영 30분", "다양한 영법을 조화롭게 구사하며 전신을 자극해보세요.", 30, 50),
        ("파티 수요 인터벌 랩 수영 챌린지 35분", "정해진 랩 타임을 목표로 심폐 능력을 강화하는 수영 세션.", 35, 50),
        ("파티 목요 지구력 롱디스턴스 수영 30분", "쉬지 않고 꾸준히 나아가는 파티 롱디스턴스 수영.", 30, 50),
        ("파티 불금 하이퍼 스피드 수영 35분", "불타는 금요일! 강력한 발차기와 스트로크로 스피드를 올려보세요.", 35, 50),
        ("파티 주말 롱코스 수영 트레이닝 40분", "주말 물속에서 파티원들과 함께 즐기는 장거리 수영 훈련.", 40, 50),
        ("파티 일요 리커버리 이지 수영 25분", "피로를 부드럽게 씻어내는 편안한 리커버리 수영 세션.", 25, 40),
    ],
    "자전거": [
        ("파티 로드 라이딩 페이스 유지 30분", "파티원들과 일정한 케이던스로 페달을 밟아보세요.", 30, 50),
        ("파티 케이던스 인터벌 라이딩 30분", "회전수를 올리는 인터벌 페달링으로 심폐 지구력을 키워보세요.", 30, 50),
        ("파티 수요 파워 페달링 힐클라임 35분", "오르막길 저항을 이겨내며 하체 파워를 폭발시키는 세션.", 35, 50),
        ("파티 목요 지구력 크루징 라이딩 30분", "바람을 가르며 파티원들과 함께 달리는 30분 지속 라이딩.", 30, 50),
        ("파티 불금 하이스피드 스프린트 35분", "불금! 순간 가속과 스프린트로 최고 속도에 도전해보세요.", 35, 50),
        ("파티 주말 장거리 투어 라이딩 40분", "주말 야외 코스를 파티원들과 함께 탐방하는 롱 라이딩 세션.", 40, 50),
        ("파티 일요 리커버리 이지 스핀 25분", "가벼운 기어비로 다리의 젖산을 풀어주는 회복 라이딩.", 25, 40),
    ],
    "축구": [
        ("파티 풋살/축구 패스 앤 무브 30분", "파티원들과 호흡을 맞추며 패스 앤 무브를 실천하세요.", 30, 50),
        ("파티 슛 & 볼 컨트롤 실전 훈련 30분", "정확한 킥과 부드러운 터치로 경기 감각을 끌어올려보세요.", 30, 50),
        ("파티 수요 축구 미니게임 챌린지 35분", "파티원들과 박진감 넘치는 미니게임 세션을 소화하세요.", 35, 50),
        ("파티 목요 공간 침투 & 스프린트 30분", "빠른 방향 전환과 스프린트로 순발력을 강화해보세요.", 30, 50),
        ("파티 불금 하이퍼 풋살 매치 35분", "불금의 열기를 풋살 코트에 쏟아붓는 뜨거운 축구 세션.", 35, 50),
        ("파티 주말 정규 축구 매치 40분", "주말 넓은 그라운드에서 파티원들과 마음껏 달려보세요.", 40, 50),
        ("파티 일요 축구 전술 & 회복 25분", "가벼운 패스 게임과 스트레칭으로 한 주를 마무리하세요.", 25, 40),
    ],
    "농구": [
        ("파티 슛팅 폼 & 3점슛 릴레이 30분", "파티원들과 정확한 슛 릴레이에 도전하세요.", 30, 50),
        ("파티 드리블 돌파 & 레이업 30분", "화려한 드리블과 림 어택으로 공격 기술을 가다듬어보세요.", 30, 50),
        ("파티 수요 3on3 하프코트 경기 35분", "파티원들과 합을 맞춰 치열한 3대3 농구 경기를 치르세요.", 35, 50),
        ("파티 목요 속공 트랜지션 러닝 30분", "빠른 공수 전환과 코트 스프린트로 심폐 지구력을 높여보세요.", 30, 50),
        ("파티 불금 풀코트 픽업게임 35분", "불타는 금요일! 올코트에서 열정적으로 뛰어보세요.", 35, 50),
        ("파티 주말 농구 토너먼트 세션 40분", "주말 코트에서 파티원들과 함께 실력을 뽐내는 롱 게임 세션.", 40, 50),
        ("파티 일요 자유투 집중 & 쿨다운 25분", "집중력을 모으는 자유투 연습과 피로 회복 세션.", 25, 40),
    ],
    "배드민턴": [
        ("파티 클리어 & 스매시 랠리 30분", "시원한 하이클리어와 스매시로 스트레스를 날리세요.", 30, 50),
        ("파티 헤어핀 & 드롭 정밀 훈련 30분", "네트 앞 섬세한 컨트롤과 수비 리시브를 훈련하세요.", 30, 50),
        ("파티 수요 복식 랠리 챌린지 35분", "파티원과 호흡을 맞추며 긴 랠리를 이어가는 복식 게임.", 35, 50),
        ("파티 목요 스텝 & 풋워크 인터벌 30분", "코트를 빈틈없이 누비는 셔틀런 풋워크 세션.", 30, 50),
        ("파티 불금 복식 리그전 35분", "불금! 파티원들과 함께하는 박진감 넘치는 배드민턴 매치.", 35, 50),
        ("파티 주말 토너먼트 복식전 40분", "주말 코트에서 펼쳐지는 파티원들의 진검승부 세션.", 40, 50),
        ("파티 일요 릴랙스 랠리 & 쿨다운 25분", "가벼운 셔틀콕 랠리와 손목·어깨 스트레칭 세션.", 25, 40),
    ],
    "테니스": [
        ("파티 스트로크 랠리 집중 훈련 30분", "포핸드와 백핸드 스트로크의 깊이를 높여보세요.", 30, 50),
        ("파티 발리 & 네트 플레이 30분", "빠른 반사신경과 전위 발리 공격을 연습하세요.", 30, 50),
        ("파티 수요 복식 타이브레이크 35분", "파티원과 함께하는 손에 땀을 쥐는 복식 매치 세션.", 35, 50),
        ("파티 목요 사이드 스텝 & 서브 30분", "강력한 서브 에이스와 민첩한 사이드 스텝을 단련하세요.", 30, 50),
        ("파티 불금 테니스 풀 매치 35분", "불타는 금요일! 코트에서 열정을 불태우는 테니스 경기.", 35, 50),
        ("파티 주말 정규 세트 매치 40분", "주말 파티원들과 제대로 된 세트 스코어 경기에 도전하세요.", 40, 50),
        ("파티 일요 이지 랠리 & 리커버리 25분", "기분 좋은 랠리와 관절 케어로 한 주를 정돈하세요.", 25, 40),
    ],
    "요가": [
        ("파티 수리야 나마스카라 태양예배 30분", "태양예배 시퀀스로 온몸의 에너지를 깨워보세요.", 30, 50),
        ("파티 밸런스 & 아사나 집중 30분", "흔들리지 않는 집중력으로 균형 감각을 단련하세요.", 30, 50),
        ("파티 수요 빈야사 플로우 세션 35분", "호흡과 동작이 하나가 되는 부드러운 빈야사 플로우.", 35, 50),
        ("파티 목요 하타 요가 호흡 수련 30분", "깊은 호흡과 함께 아사나를 오래 유지하며 내면을 다져보세요.", 30, 50),
        ("파티 불금 힐링 인요가 35분", "불금! 한 주 동안 쌓인 피로를 깊은 스트레칭으로 씻어내세요.", 35, 50),
        ("파티 주말 전신 코어 요가 40분", "주말 매트 위에서 코어 힘과 유연성을 동시에 강화하세요.", 40, 50),
        ("파티 일요 명상 & 릴랙세이션 25분", "차분한 명상과 이완으로 새로운 한 주를 준비하는 힐링 세션.", 25, 40),
    ],
    "등산": [
        ("파티 둘레길 협동 트레킹 30분", "파티원들과 숲길을 걸으며 피톤치드를 마셔보세요.", 30, 50),
        ("파티 언덕 경사로 페이스 훈련 30분", "오르막 경사를 오르며 하체와 심폐 지구력을 키워보세요.", 30, 50),
        ("파티 수요 등산로 파워 보행 35분", "힘찬 걸음걸이로 산길을 오르는 35분 트레킹 세션.", 35, 50),
        ("파티 목요 하체 지구력 등산 트레이닝 30분", "계단과 바윗길을 넘나들며 튼튼한 하체를 만드세요.", 30, 50),
        ("파티 불금 나이트 트레킹 35분", "불금 저녁! 시원한 바람을 맞으며 걷는 야간 트레킹.", 35, 50),
        ("파티 주말 정상 정복 등산 세션 40분", "주말 명산을 찾아 파티원들과 정상 목표에 도전하세요.", 40, 50),
        ("파티 일요 힐링 피톤치드 산책 25분", "산림욕과 가벼운 산책으로 몸과 마음을 정화하세요.", 25, 40),
    ],
}

# 2-2) 파티 목표 운동 종목별 일일 강화/인터벌 2번째 미션 템플릿 풀
WORKOUT_PARTY_SECONDARY_TEMPLATES = {
    "러닝": [
        ("파티원과 함께 심폐 강화 인터벌 러닝 30분", "심박수를 올리는 인터벌 구간 러닝으로 지구력을 극대화하세요.", 30, 50),
        ("파티원과 함께 케이던스 맞춤 러닝 30분", "파티원들과 보폭과 발구름을 일치시키며 가볍게 달려보세요.", 30, 50),
        ("파티원과 함께 템포 러닝 챌린지 30분", "목표 페이스를 유지하며 집중력 있게 달리는 러닝 세션.", 30, 50),
        ("파티원과 함께 릴레이 지속주 러닝 30분", "파티원들과 교대로 선두를 맡아 30분 동안 지속해서 달려보세요.", 30, 50),
        ("파티원과 함께 고강도 언덕 스프린트 러닝 35분", "오르막 인터벌로 폭발적인 심폐와 하체 파워를 기르세요.", 35, 50),
        ("파티원과 함께 주말 그룹 LSD 러닝 40분", "주말을 맞아 여유 있는 페이스로 긴 거리를 달려보세요.", 40, 50),
        ("파티원과 함께 쿨다운 리커버리 러닝 25분", "편안한 조깅으로 뭉친 다리 근육을 풀어주는 회복 세션.", 25, 40),
    ],
    "헬스": [
        ("파티원과 함께 고강도 슈퍼세트 웨이트 30분", "휴식 시간을 줄이고 타겟 근육을 집중 공략하세요.", 30, 50),
        ("파티원과 함께 덤벨 & 바벨 스트렝스 30분", "정확한 궤적과 자극으로 근육의 볼륨을 채워보세요.", 30, 50),
        ("파티원과 함께 전신 서킷 트레이닝 30분", "다양한 동작을 쉼 없이 순환하며 칼로리를 소모하세요.", 30, 50),
        ("파티원과 함께 타바타 인터벌 웨이트 30분", "20초 운동 10초 휴식의 타바타 리듬으로 한계에 도전하세요.", 30, 50),
        ("파티원과 함께 불타는 근력 한계돌파 35분", "불금의 에너지를 쏟아 마지막 세트까지 완수하세요.", 35, 50),
        ("파티원과 함께 주말 중량 리프팅 세션 40분", "충분한 웜업 후 고중량 리프팅을 안전하게 수행하세요.", 40, 50),
        ("파티원과 함께 저강도 관절 회복 스트레칭 25분", "폼롤러와 스트레칭으로 관절의 가동 범위를 넓혀주세요.", 25, 40),
    ],
    "수영": [
        ("파티원과 함께 수영 킥판 발차기 & 코어 강화 30분", "강력한 하체 발차기로 추진력을 높이는 훈련.", 30, 50),
        ("파티원과 함께 수영 영법 자세 교정 세션 30분", "스트로크와 호흡 타이밍을 세밀하게 점검해보세요.", 30, 50),
        ("파티원과 함께 50m 스프린트 인터벌 수영 30분", "짧은 거리를 전력 질주하며 순발력을 단련하세요.", 30, 50),
        ("파티원과 함께 수영 턴 & 잠영 테크닉 훈련 30분", "플립턴과 돌핀킥으로 벽을 차고 나가는 기술 연습.", 30, 50),
        ("파티원과 함께 젖산 내성 수영 세션 35분", "지치지 않는 체력을 만드는 고강도 랩 훈련.", 35, 50),
        ("파티원과 함께 주말 지구력 랩 챌린지 수영 40분", "장거리 랩을 쉬지 않고 도는 주말 수영 세션.", 40, 50),
        ("파티원과 함께 물속 스트레칭 & 회복 수영 25분", "물속 저항을 활용해 부드럽게 근육을 이완하세요.", 25, 40),
    ],
    "자전거": [
        ("파티원과 함께 고속 스프린트 인터벌 30분", "순간적인 가속으로 최고 속도를 경험해보세요.", 30, 50),
        ("파티원과 함께 인터벌 기어비 훈련 30분", "고단과 저단 기어를 넘나들며 페달링 스킬을 단련하세요.", 30, 50),
        ("파티원과 함께 그룹 팩 라이딩 30분", "앞뒤 라이더의 간격을 유지하며 바람 저항을 줄여보세요.", 30, 50),
        ("파티원과 함께 파워존 유지 지속 라이딩 30분", "목표 파워 출력을 일정하게 유지하는 세션.", 30, 50),
        ("파티원과 함께 불금 파워 버닝 인터벌 35분", "불타는 인터벌로 허벅지와 심폐를 동시에 자극하세요.", 35, 50),
        ("파티원과 함께 주말 롱 라이딩 투어 40분", "멋진 코스를 파티원들과 함께 완주하는 세션.", 40, 50),
        ("파티원과 함께 쿨다운 회복 라이딩 25분", "가벼운 회전수로 젖산을 분해하는 힐링 라이딩.", 25, 40),
    ],
    "축구": [
        ("파티원과 함께 순발력 코디네이션 훈련 30분", "민첩성과 풋워크를 향상하는 스텝 훈련.", 30, 50),
        ("파티원과 함께 볼 컨트롤 & 퍼스트 터치 30분", "날아오는 볼을 안정적으로 소유하는 기술 연마.", 30, 50),
        ("파티원과 함께 크로스 & 슈팅 세션 30분", "측면 크로스와 정확한 임팩트로 골망을 흔드세요.", 30, 50),
        ("파티원과 함께 전술 압박 스프린트 30분", "수비 인터벌과 압박 타이밍을 맞추는 세션.", 30, 50),
        ("파티원과 함께 불타는 축구 체력 버닝 35분", "경기 후반에도 지치지 않는 강철 체력 훈련.", 35, 50),
        ("파티원과 함께 주말 실전 전술 세션 40분", "팀원들과 유기적인 패스 워크를 완성해보세요.", 40, 50),
        ("파티원과 함께 경기 후 회복 스트레칭 25분", "햄스트링과 종아리 근육을 풀어주는 마무리 세션.", 25, 40),
    ],
    "농구": [
        ("파티원과 함께 2대2 픽앤롤 연습 30분", "스크린 플레이와 패스 타이밍을 맞춰보세요.", 30, 50),
        ("파티원과 함께 수비 풋워크 & 슬라이드 30분", "낮은 자세로 상대를 마크하는 수비 훈련.", 30, 50),
        ("파티원과 함께 점프력 & 리바운드 세션 30분", "보드 장악력을 높이는 박스아웃 훈련.", 30, 50),
        ("파티원과 함께 인터벌 속공 스프린트 30분", "코트를 가로지르는 맹렬한 역습 달리기.", 30, 50),
        ("파티원과 함께 고강도 농구 서킷 35분", "드리블과 점프를 엮은 고강도 서킷 루틴.", 35, 50),
        ("파티원과 함께 주말 슛팅 챌린지 40분", "포지션별 슛 성공률을 끌어올리는 연습.", 40, 50),
        ("파티원과 함께 가벼운 릴랙스 슛 & 회복 25분", "정적인 슛팅과 관절 이완 세션.", 25, 40),
    ],
    "배드민턴": [
        ("파티원과 함께 전위 푸시 & 수비 리시브 30분", "빠른 네트 플레이와 안정적인 수비 훈련.", 30, 50),
        ("파티원과 함께 좌우 코트 셔틀런 30분", "코트 구석구석을 커버하는 민첩성 훈련.", 30, 50),
        ("파티원과 함께 롱 랠리 지구력 세션 30분", "미스 없이 셔틀콕을 주고받는 집중력 훈련.", 30, 50),
        ("파티원과 함께 인터벌 스매시 훈련 30분", "강력한 다운포스로 스매시 결정력을 높이세요.", 30, 50),
        ("파티원과 함께 하이퍼 버닝 랠리 35분", "땀방울이 쏟아지는 불금 랠리 매치.", 35, 50),
        ("파티원과 함께 주말 복식 랭킹전 40분", "팀워크와 전략으로 승리를 쟁취하세요.", 40, 50),
        ("파티원과 함께 손목 & 어깨 회복 스트레칭 25분", "라켓 운동 피로를 날리는 유연성 세션.", 25, 40),
    ],
    "테니스": [
        ("파티원과 함께 탑스핀 & 슬라이스 30분", "구질 변화로 상대를 흔드는 테크닉 훈련.", 30, 50),
        ("파티원과 함께 베이스라인 딥 랠리 30분", "깊숙한 스트로크로 코트를 지배하세요.", 30, 50),
        ("파티원과 함께 서브 앤 발리 전략 30분", "서브 후 빠른 전진 공격을 실전처럼 연습하세요.", 30, 50),
        ("파티원과 함께 인터벌 코트 스프린트 30분", "공을 쫓아 전력 질주하는 풋워크 훈련.", 30, 50),
        ("파티원과 함께 고강도 랠리 버닝 35분", "강한 템포로 랠리를 이어가는 심폐 세션.", 35, 50),
        ("파티원과 함께 주말 랭킹전 매치 40분", "파티원들의 실력을 겨루는 주말 게임.", 40, 50),
        ("파티원과 함께 관절 케어 스트레칭 25분", "어깨, 팔꿈치, 무릎을 부드럽게 풀어주세요.", 25, 40),
    ],
    "요가": [
        ("파티원과 함께 골반 & 햄스트링 스트레칭 30분", "하체의 굳은 근육을 길고 시원하게 늘려보세요.", 30, 50),
        ("파티원과 함께 척추 기립근 밸런스 교정 30분", "바른 자세를 유지하며 코어를 단련하세요.", 30, 50),
        ("파티원과 함께 파워 요가 근력 세션 30분", "유연성과 근력을 동시에 잡는 파워 아사나.", 30, 50),
        ("파티원과 함께 흉추 가동성 열기 30분", "답답한 가슴과 어깨를 활짝 여는 흉추 스트레칭.", 30, 50),
        ("파티원과 함께 딥 스트레칭 버닝 35분", "호흡을 길게 내쉬며 더 깊은 동작으로 나아가세요.", 35, 50),
        ("파티원과 함께 주말 코어 밸런스 플로우 40분", "매트 위에서 조화로운 전신 균형을 완성하세요.", 40, 50),
        ("파티원과 함께 전신 이완 회복 요가 25분", "심신의 안정을 돕는 포근한 힐링 루틴.", 25, 40),
    ],
    "등산": [
        ("파티원과 함께 계단 오르기 파워 트레이닝 30분", "하체 근력과 심폐를 빠르게 깨우는 계단 세션.", 30, 50),
        ("파티원과 함께 심폐 인터벌 오르막 보행 30분", "호흡을 가다듬으며 가파른 경사를 극복하세요.", 30, 50),
        ("파티원과 함께 하체 밸런스 & 코어 보행 30분", "바위나 불규칙한 지형에서 중심을 잡는 훈련.", 30, 50),
        ("파티원과 함께 등산 스틱 테크닉 세션 30분", "스틱을 활용해 관절 부하를 줄이며 걷는 법.", 30, 50),
        ("파티원과 함께 고강도 릿지 인터벌 35분", "지속적인 오르막 걸음으로 체력을 끌어올리세요.", 35, 50),
        ("파티원과 함께 주말 롱 트레킹 40분", "자연의 정취를 만끽하며 완주하는 장거리 코스.", 40, 50),
        ("파티원과 함께 무릎 & 발목 스트레칭 25분", "하산 후 관절과 근육을 달래는 쿨다운 루틴.", 25, 40),
    ],
}


# 3) 솔로 주간 미션 4개 시즌 로테이션 풀 (1번 출석 누적 고정 + 9개 AI 미션 매주 변경)
SOLO_WEEKLY_SEASON_POOLS = [
    # Cycle 0: [지구력 & 마일리지 시즌]
    [
        {"title": "주간 누적 운동 시간 120분 달성하기", "description": "이번 주 총 120분 이상 땀 흘리고 건강을 채워보세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 1, "target_minutes": 120, "reward_points": 100},
        {"title": "이번 주 3일 이상 운동 기록 남기기", "description": "하루 한 번 꾸준하게 주 3일 이상 운동을 실천하세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 3, "target_minutes": 0, "reward_points": 60},
        {"title": "[{facility_name}] 방문 및 운동하기", "description": "{user_area} 공공 체육시설에서 멋진 운동 인증을 남겨보세요!", "category": "FACILITY", "workout_type": "기타", "target_count": 1, "target_minutes": 0, "reward_points": 70, "use_facility": True},
        {"title": "일일 미션 총 5회 이상 달성하기", "description": "매일 제공되는 일일 미션을 이번 주 총 5회 클리어하세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 5, "target_minutes": 0, "reward_points": 80},
        {"title": "주간 누적 러닝/산책 8km 달성하기", "description": "러닝이나 산책으로 이번 주 누적 8km를 완주해보세요.", "category": "CUMULATIVE", "workout_type": "러닝", "target_count": 8, "target_minutes": 0, "reward_points": 80},
        {"title": "서로 다른 운동 2종목 이상 즐기기", "description": "유산소, 웨이트, 수영 등 다양한 종목을 즐겨보세요.", "category": "WORKOUT", "workout_type": "기타", "target_count": 2, "target_minutes": 0, "reward_points": 60},
        {"title": "40분 이상 집중 트레이닝 1회 완료하기", "description": "한 번의 운동에서 40분 이상 집중하여 땀을 흘려보세요.", "category": "WORKOUT", "workout_type": "기타", "target_count": 1, "target_minutes": 40, "reward_points": 70},
        {"title": "주간 누적 1,000 kcal 이상 소모하기", "description": "이번 주 운동으로 1,000 kcal 이상을 시원하게 태워보세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 1000, "target_minutes": 0, "reward_points": 80},
        {"title": "친구와 함께 운동하거나 배틀 참여하기", "description": "파티원과 함께 운동하거나 카드 배틀에 도전하세요!", "category": "WORKOUT", "workout_type": "기타", "target_count": 1, "target_minutes": 0, "reward_points": 70},
    ],
    # Cycle 1: [파워 & 스피드 부스팅 시즌]
    [
        {"title": "주간 누적 운동 시간 140분 돌파하기", "description": "파워 넘치는 한 주! 주간 누적 140분 운동 목표를 달성하세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 1, "target_minutes": 140, "reward_points": 110},
        {"title": "이번 주 4일 이상 꾸준히 운동하기", "description": "주 4일 이상 성실하게 기록을 남기고 루틴을 형성하세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 4, "target_minutes": 0, "reward_points": 70},
        {"title": "[{facility_name}] 방문 및 파워 트레이닝하기", "description": "{user_area} 공공 체육시설에서 고강도 트레이닝에 도전하세요!", "category": "FACILITY", "workout_type": "기타", "target_count": 1, "target_minutes": 0, "reward_points": 70, "use_facility": True},
        {"title": "일일 미션 총 6회 이상 클리어하기", "description": "매일 주어지는 미션을 6회 이상 성공하여 성장 포인트를 모으세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 6, "target_minutes": 0, "reward_points": 85},
        {"title": "주간 누적 러닝/산책 10km 달성하기", "description": "속도와 거리를 올려 이번 주 10km 완주를 기록하세요.", "category": "CUMULATIVE", "workout_type": "러닝", "target_count": 10, "target_minutes": 0, "reward_points": 90},
        {"title": "웨이트 또는 러닝 포함 3종목 운동하기", "description": "서로 다른 3가지 종목을 경험하며 전신 근력을 자극하세요.", "category": "WORKOUT", "workout_type": "기타", "target_count": 3, "target_minutes": 0, "reward_points": 70},
        {"title": "45분 이상 연속 트레이닝 1회 달성하기", "description": "지치지 않는 열정으로 45분 연속 운동 세션을 완주하세요.", "category": "WORKOUT", "workout_type": "기타", "target_count": 1, "target_minutes": 45, "reward_points": 80},
        {"title": "주간 누적 1,200 kcal 이상 버닝하기", "description": "고강도 세션으로 이번 주 1,200 kcal 이상을 빠르게 소모하세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 1200, "target_minutes": 0, "reward_points": 90},
        {"title": "카드 배틀 1회 승리 또는 참여하기", "description": "라이벌과의 치열한 카드 배틀에서 실력을 겨뤄보세요!", "category": "WORKOUT", "workout_type": "기타", "target_count": 1, "target_minutes": 0, "reward_points": 70},
    ],
    # Cycle 2: [체지방 버닝 & 챌린지 시즌]
    [
        {"title": "주간 누적 운동 시간 150분 달성하기", "description": "한계에 도전하는 주간! 총 150분 이상 강력하게 운동하세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 1, "target_minutes": 150, "reward_points": 120},
        {"title": "주중 3일 & 주말 1일 총 4일 운동하기", "description": "평일과 주말 모두 땀 흘리며 주 4일 운동을 완성하세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 4, "target_minutes": 0, "reward_points": 70},
        {"title": "[{facility_name}] 방문 및 전신 운동하기", "description": "{user_area} 체육시설에서 전신 근육을 깨우는 인증을 남겨보세요!", "category": "FACILITY", "workout_type": "기타", "target_count": 1, "target_minutes": 0, "reward_points": 70, "use_facility": True},
        {"title": "일일 미션 총 7회 이상 올클리어 도전하기", "description": "이번 주 일일 미션을 7회 이상 완수하여 미션 마스터가 되어보세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 7, "target_minutes": 0, "reward_points": 90},
        {"title": "주간 누적 러닝/산책 12km 질주하기", "description": "강력한 유산소 러닝으로 이번 주 누적 12km를 돌파하세요.", "category": "CUMULATIVE", "workout_type": "러닝", "target_count": 12, "target_minutes": 0, "reward_points": 95},
        {"title": "서로 다른 운동 2종목 이상 고강도 실천하기", "description": "강도를 한 단계 올려 2종목 이상의 운동을 완벽 소화하세요.", "category": "WORKOUT", "workout_type": "기타", "target_count": 2, "target_minutes": 0, "reward_points": 70},
        {"title": "50분 이상 롱세션 트레이닝 1회 완료하기", "description": "50분 동안 집중력을 잃지 않고 롱 트레이닝 세션을 끝마치세요.", "category": "WORKOUT", "workout_type": "기타", "target_count": 1, "target_minutes": 50, "reward_points": 85},
        {"title": "주간 누적 1,500 kcal 강력 버닝하기", "description": "놀라운 활동량으로 1,500 kcal를 태우고 가벼운 몸을 만드세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 1500, "target_minutes": 0, "reward_points": 100},
        {"title": "친구와 파티 운동 또는 친선 배틀 2회 도전하기", "description": "친구들과 함께하거나 배틀에 2회 도전해 에너지를 나누세요!", "category": "WORKOUT", "workout_type": "기타", "target_count": 2, "target_minutes": 0, "reward_points": 80},
    ],
    # Cycle 3: [밸런스 & 웰니스 리프레시 시즌]
    [
        {"title": "주간 누적 운동 시간 100분 산뜻하게 채우기", "description": "무리하지 않고 편안한 페이스로 100분 운동을 채워보세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 1, "target_minutes": 100, "reward_points": 90},
        {"title": "이번 주 3일 이상 가뿐하게 운동하기", "description": "몸에 활력을 불어넣는 산뜻한 주 3일 운동을 실천하세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 3, "target_minutes": 0, "reward_points": 60},
        {"title": "[{facility_name}] 주변 힐링 코스 산책하기", "description": "{user_area} 체육시설 주변 산책로를 걸으며 힐링을 누려보세요.", "category": "FACILITY", "workout_type": "기타", "target_count": 1, "target_minutes": 0, "reward_points": 65, "use_facility": True},
        {"title": "일일 미션 총 4회 이상 가뿐히 달성하기", "description": "스트레스 없이 데일리 미션을 4회 이상 가뿐하게 클리어하세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 4, "target_minutes": 0, "reward_points": 70},
        {"title": "주간 누적 걷기/러닝 7km 달성하기", "description": "여유로운 걸음과 가벼운 러닝으로 7km를 완주해보세요.", "category": "CUMULATIVE", "workout_type": "러닝", "target_count": 7, "target_minutes": 0, "reward_points": 70},
        {"title": "스트레칭·요가 포함 서로 다른 2종목 실천하기", "description": "유연성과 근력을 동시에 챙기는 2종목 복합 트레이닝.", "category": "WORKOUT", "workout_type": "기타", "target_count": 2, "target_minutes": 0, "reward_points": 60},
        {"title": "35분 이상 리프레시 트레이닝 완료하기", "description": "몸의 피로를 풀어주는 35분 리프레시 운동 세션입니다.", "category": "WORKOUT", "workout_type": "기타", "target_count": 1, "target_minutes": 35, "reward_points": 65},
        {"title": "주간 누적 800 kcal 이상 기분 좋게 소모하기", "description": "기분 좋은 땀방울과 함께 800 kcal 소모를 달성하세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 800, "target_minutes": 0, "reward_points": 70},
        {"title": "배틀 아레나 참여 또는 파티원 응원하기", "description": "배틀에 참여하거나 친구들에게 응원의 에너지를 전하세요.", "category": "WORKOUT", "workout_type": "기타", "target_count": 1, "target_minutes": 0, "reward_points": 65},
    ],
]

# 4) 파티 주간 미션 4개 시즌 로테이션 풀 (10개 미션 매주 변경, 출석 제외)
PARTY_WEEKLY_SEASON_POOLS = [
    # Cycle 0: [파티 단합 & 마일리지 시즌]
    [
        {"title": "파티 합산 주간 누적 운동 300분 돌파하기", "description": "이번 주 파티원들의 총 운동 시간을 합산하여 300분 이상을 달성하세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 1, "target_minutes": 300, "reward_points": 100},
        {"title": "파티원들과 주 3일 이상 함께 운동하기", "description": "파티원들이 이번 주 3일 이상 꾸준히 운동에 참여해보세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 3, "target_minutes": 0, "reward_points": 60},
        {"title": "[{facility_name}] 파티 공공체육시설 방문 및 운동 인증하기", "description": "{owner_area}의 체육시설에서 파티원들과 함께 운동하고 인증을 남겨보세요!", "category": "FACILITY", "workout_type": "기타", "target_count": 1, "target_minutes": 0, "reward_points": 70, "use_facility": True},
        {"title": "파티원 일일 미션 총 5회 이상 클리어 달성하기", "description": "파티원들이 일일 미션을 합산 5회 이상 성공하여 협동심을 뽐내보세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 5, "target_minutes": 0, "reward_points": 80},
        {"title": "파티 합산 누적 러닝/산책 거리 20km 완주하기", "description": "파티원들이 달린 거리와 걸은 거리를 합산해 20km 완주에 도전하세요!", "category": "CUMULATIVE", "workout_type": "러닝", "target_count": 20, "target_minutes": 0, "reward_points": 80},
        {"title": "파티원들과 서로 다른 3종목 이상 운동 즐기기", "description": "러닝, 헬스, 수영, 자전거 등 파티원들이 3종목 이상의 다양한 운동을 즐겨보세요.", "category": "WORKOUT", "workout_type": "기타", "target_count": 3, "target_minutes": 0, "reward_points": 60},
        {"title": "파티 고강도 40분 집중 세션 완료하기", "description": "파티원과 함께 40분 이상 연속으로 집중 운동을 완수하세요.", "category": "WORKOUT", "workout_type": "기타", "target_count": 1, "target_minutes": 40, "reward_points": 70},
        {"title": "파티 합산 2,500 kcal 이상 칼로리 버닝하기", "description": "이번 주 파티원들의 소모 칼로리를 모아 2,500 kcal 이상을 불태워보세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 2500, "target_minutes": 0, "reward_points": 80},
        {"title": "파티원 간 친선 카드 배틀 1회 참여하기", "description": "파티원과 흥미진진한 카드 배틀을 펼치며 체력을 겨뤄보세요!", "category": "WORKOUT", "workout_type": "기타", "target_count": 1, "target_minutes": 0, "reward_points": 70},
        {"title": "주말 파티 스페셜 인터벌 트레이닝 45분", "description": "주말을 맞아 파티원들과 함께 45분 이상 알찬 인터벌 운동을 즐겨보세요.", "category": "WORKOUT", "workout_type": "러닝", "target_count": 1, "target_minutes": 45, "reward_points": 80},
    ],
    # Cycle 1: [파티 파워 & 인터벌 시즌]
    [
        {"title": "파티 합산 주간 누적 운동 350분 정복하기", "description": "파티원들의 뜨거운 열정으로 이번 주 총합 350분 운동을 돌파하세요!", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 1, "target_minutes": 350, "reward_points": 110},
        {"title": "파티원들과 주 4일 이상 열정 운동하기", "description": "파티원들이 주 4일 이상 적극적으로 운동에 참여해 팀워크를 다져보세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 4, "target_minutes": 0, "reward_points": 70},
        {"title": "[{facility_name}] 파티 시설 합동 근력 트레이닝 1회 인증하기", "description": "{owner_area} 공공 체육시설에서 파티 합동 근력 세션을 인증하세요.", "category": "FACILITY", "workout_type": "기타", "target_count": 1, "target_minutes": 0, "reward_points": 70, "use_facility": True},
        {"title": "파티원 일일 미션 총 7회 이상 클리어하기", "description": "팀원들의 일일 미션 클리어 횟수를 합산해 7회 이상을 달성하세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 7, "target_minutes": 0, "reward_points": 85},
        {"title": "파티 합산 누적 러닝/산책 거리 25km 돌파하기", "description": "파티원들의 누적 이동 거리를 합산하여 25km를 시원하게 돌파하세요!", "category": "CUMULATIVE", "workout_type": "러닝", "target_count": 25, "target_minutes": 0, "reward_points": 90},
        {"title": "파티원 전원 각자 다른 3종목 이상 도전하기", "description": "파티원들이 각자 개성 있는 운동으로 3종목 이상을 함께 기록해보세요.", "category": "WORKOUT", "workout_type": "기타", "target_count": 3, "target_minutes": 0, "reward_points": 70},
        {"title": "파티원 고강도 50분 집중 트레이닝 달성하기", "description": "한 번의 운동에서 50분 이상 집중하여 땀 흘린 기록을 달성하세요.", "category": "WORKOUT", "workout_type": "기타", "target_count": 1, "target_minutes": 50, "reward_points": 80},
        {"title": "파티 합산 3,000 kcal 대폭발 버닝하기", "description": "파티원들의 에너지를 모아 주간 3,000 kcal 칼로리 소모를 이뤄내세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 3000, "target_minutes": 0, "reward_points": 90},
        {"title": "파티원 간 카드 배틀 2회 대결 펼치기", "description": "파티원끼리 2회 이상의 박진감 넘치는 카드 배틀을 치러보세요!", "category": "WORKOUT", "workout_type": "기타", "target_count": 2, "target_minutes": 0, "reward_points": 80},
        {"title": "파티 주말 버닝 유산소 세션 50분", "description": "주말 동안 파티원들과 함께 50분 이상 파워 유산소를 완료하세요.", "category": "WORKOUT", "workout_type": "러닝", "target_count": 1, "target_minutes": 50, "reward_points": 85},
    ],
    # Cycle 2: [파티 한계돌파 & 슈퍼 챌린지 시즌]
    [
        {"title": "파티 합산 주간 누적 운동 400분 마스터하기", "description": "최고의 팀워크를 증명하는 400분 누적 운동 시간 대기록에 도전하세요!", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 1, "target_minutes": 400, "reward_points": 120},
        {"title": "파티원 주 4일 이상 완벽 출석 운동하기", "description": "파티원들이 주 4일 이상 꾸준히 참여하여 운동 습관을 다져보세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 4, "target_minutes": 0, "reward_points": 80},
        {"title": "[{facility_name}] 파티 랜드마크 시설 완주 인증하기", "description": "{owner_area} 체육시설에서 함께 땀 흘리고 완주 인증을 남겨보세요!", "category": "FACILITY", "workout_type": "기타", "target_count": 1, "target_minutes": 0, "reward_points": 75, "use_facility": True},
        {"title": "파티원 일일 미션 총 8회 이상 올클리어 합산 달성하기", "description": "파티원들이 매일 최선을 다해 일일 미션 총 8회를 클리어하세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 8, "target_minutes": 0, "reward_points": 95},
        {"title": "파티 합산 누적 러닝 거리 30km 대장정 달성하기", "description": "파티원들의 러닝과 걷기를 모아 30km 대장정을 달성해보세요!", "category": "CUMULATIVE", "workout_type": "러닝", "target_count": 30, "target_minutes": 0, "reward_points": 100},
        {"title": "파티원들과 다양한 종목 4가지 이상 섭렵하기", "description": "4가지 이상의 다채로운 운동 종목을 파티원들과 골고루 경험하세요.", "category": "WORKOUT", "workout_type": "기타", "target_count": 4, "target_minutes": 0, "reward_points": 80},
        {"title": "파티원 45분 이상 파워 세션 1회 클리어하기", "description": "파티원 중 한 명 이상이 45분 고강도 세션을 멋지게 성공하세요.", "category": "WORKOUT", "workout_type": "기타", "target_count": 1, "target_minutes": 45, "reward_points": 80},
        {"title": "파티 합산 3,500 kcal 슈퍼 히트 버닝하기", "description": "불꽃 같은 열정으로 파티 합산 3,500 kcal 소모 목표를 돌파하세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 3500, "target_minutes": 0, "reward_points": 100},
        {"title": "파티 친선 카드 배틀 1회 완료하기", "description": "친선 배틀을 통해 파티원들의 성장한 전투력을 확인해보세요!", "category": "WORKOUT", "workout_type": "기타", "target_count": 1, "target_minutes": 0, "reward_points": 70},
        {"title": "파티 주말 릴레이 장거리 트레이닝 60분", "description": "주말 파티원들과 60분 연속 장거리 릴레이 운동을 완수하세요.", "category": "WORKOUT", "workout_type": "러닝", "target_count": 1, "target_minutes": 60, "reward_points": 90},
    ],
    # Cycle 3: [파티 웰니스 & 밸런스 회복 시즌]
    [
        {"title": "파티 합산 주간 누적 운동 250분 산뜻하게 채우기", "description": "부담 없이 파티원들과 편안하게 250분 누적 운동을 즐겨보세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 1, "target_minutes": 250, "reward_points": 90},
        {"title": "파티원들과 주 3일 이상 가뿐하게 운동하기", "description": "활기찬 일상을 위해 파티원들과 주 3일 이상 운동을 지속하세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 3, "target_minutes": 0, "reward_points": 60},
        {"title": "[{facility_name}] 파티 힐링 시설 방문 및 워킹 1회 인증하기", "description": "{owner_area} 체육시설에서 가벼운 힐링 워킹을 함께 즐겨보세요.", "category": "FACILITY", "workout_type": "기타", "target_count": 1, "target_minutes": 0, "reward_points": 65, "use_facility": True},
        {"title": "파티원 일일 미션 총 4회 이상 즐겁게 클리어하기", "description": "가벼운 마음으로 파티원 일일 미션 총 4회를 성공해보세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 4, "target_minutes": 0, "reward_points": 70},
        {"title": "파티 합산 누적 걷기/러닝 거리 15km 완주하기", "description": "산뜻한 발걸음으로 파티 합산 15km 거리를 가뿐히 채워보세요.", "category": "CUMULATIVE", "workout_type": "러닝", "target_count": 15, "target_minutes": 0, "reward_points": 75},
        {"title": "유산소와 힐링 운동 포함 2종목 이상 즐기기", "description": "다양한 매력의 2종목 운동으로 몸의 밸런스를 바로잡으세요.", "category": "WORKOUT", "workout_type": "기타", "target_count": 2, "target_minutes": 0, "reward_points": 60},
        {"title": "파티원 35분 이상 리프레시 협동 세션 완수하기", "description": "파티원과 함께 35분 리프레시 운동 세션을 기분 좋게 완수하세요.", "category": "WORKOUT", "workout_type": "기타", "target_count": 1, "target_minutes": 35, "reward_points": 65},
        {"title": "파티 합산 2,000 kcal 산뜻하게 소모하기", "description": "이번 주 파티원들과 2,000 kcal 소모를 가뿐하게 달성하세요.", "category": "CUMULATIVE", "workout_type": "기타", "target_count": 2000, "target_minutes": 0, "reward_points": 75},
        {"title": "파티원 간 즐거운 친선 배틀 1회 참여하기", "description": "재미있는 친선 카드 배틀로 팀원들과 유쾌한 시간을 보내세요.", "category": "WORKOUT", "workout_type": "기타", "target_count": 1, "target_minutes": 0, "reward_points": 65},
        {"title": "파티 주말 힐링 아웃도어 트레이닝 40분", "description": "주말 자연 속에서 파티원들과 함께하는 40분 힐링 운동!", "category": "WORKOUT", "workout_type": "러닝", "target_count": 1, "target_minutes": 40, "reward_points": 70},
    ],
]


def generate_daily_missions(user, today=None):
    """
    일일 미션 3개 생성:
    1. 출석 미션 (1개): 오늘의 NetFit 출석 체크 (고정)
    2. AI 맞춤 미션 1 (1개): 사용자 프로필 및 요일에 따라 매일 변경되는 맞춤 운동
    3. AI 맞춤 미션 2 (1개): 사용자 지역의 공공체육시설 연계 또는 데일리 테마 운동 (매일 변경)
    """
    if today is None:
        today = timezone.localdate()

    existing = list(PersonalDailyQuest.objects.filter(
        user=user, period_type="DAILY", quest_date=today, is_active=True
    ))
    if len(existing) >= 3:
        return existing[:3]

    existing_titles = {q.title for q in existing}
    created_missions = list(existing)

    profile = getattr(user, "profile", None)
    user_age = getattr(profile, "age", 25) or 25
    user_area = getattr(profile, "area", "서울특별시") or "서울특별시"
    workout_goal = getattr(profile, "workout_goal", "HEALTH")
    weekday = today.weekday()
    day_seed = today.year * 1000 + today.timetuple().tm_yday

    # 1. 출석 미션 (1개) - 고정
    att_title = "오늘의 NetFit 출석 체크"
    if not any(q.mission_category == "ATTENDANCE" for q in created_missions):
        m1 = PersonalDailyQuest.objects.create(
            user=user,
            title=att_title,
            description="매일 출석 도장을 찍고 30점을 획득하세요!",
            workout_type="기타",
            custom_workout_name="출석 체크",
            target_minutes=0,
            period_type="DAILY",
            mission_category="ATTENDANCE",
            target_count=1,
            reward_points=30,
            source="SYSTEM",
            quest_date=today,
            is_active=True,
        )
        created_missions.append(m1)
        existing_titles.add(att_title)

    # 2. AI 맞춤 미션 1 (요일 및 목표별 매일 변경되는 맞춤 운동 1개)
    if len(created_missions) < 2:
        pool_key = "SENIOR" if user_age >= 60 else (workout_goal if workout_goal in SOLO_DAILY_WORKOUT_POOLS else "HEALTH")
        pool = SOLO_DAILY_WORKOUT_POOLS.get(pool_key, SOLO_DAILY_WORKOUT_POOLS["HEALTH"])
        m2_title, m2_desc, m2_type, m2_mins, m2_pts = pool[weekday % len(pool)]

        if m2_title not in existing_titles:
            m2 = PersonalDailyQuest.objects.create(
                user=user,
                title=m2_title,
                description=m2_desc,
                workout_type=m2_type,
                target_minutes=m2_mins,
                period_type="DAILY",
                mission_category="WORKOUT",
                target_count=1,
                reward_points=m2_pts,
                source="AI",
                quest_date=today,
                is_active=True,
            )
            created_missions.append(m2)
            existing_titles.add(m2_title)

    # 3. AI 맞춤 미션 2 (주변 시설 연계 또는 데일리 테마 운동 - 매일 변경)
    if len(created_missions) < 3:
        facilities = list(Facility.objects.filter(region=user_area, is_active=True))
        if facilities:
            nearby_facility = facilities[day_seed % len(facilities)]
            fac_actions = [
                (f"[{nearby_facility.name}] 방문 또는 주변 산책 25분", f"{user_area}의 추천 공공 체육시설에서 활기차게 운동해보세요!", "걷기", 25, 40),
                (f"[{nearby_facility.name}] 체육시설 이용 및 러닝 30분", f"{user_area} 추천 시설에서 상쾌한 유산소 러닝을 즐겨보세요.", "러닝", 30, 50),
                (f"[{nearby_facility.name}] 체육시설 근력 트레이닝 30분", f"{user_area} 추천 시설에서 탄탄한 근력 운동을 실천하세요.", "헬스", 30, 50),
            ]
            m3_title, m3_desc, m3_type, m3_mins, m3_pts = fac_actions[day_seed % len(fac_actions)]
            m3_cat = "FACILITY"
            m3_fac = nearby_facility
        else:
            m3_title, m3_desc, m3_type, m3_mins, m3_pts = SOLO_DAILY_NO_FACILITY_THEMES[weekday % len(SOLO_DAILY_NO_FACILITY_THEMES)]
            m3_cat = "WORKOUT"
            m3_fac = None

        if m3_title not in existing_titles:
            m3 = PersonalDailyQuest.objects.create(
                user=user,
                title=m3_title,
                description=m3_desc,
                workout_type=m3_type,
                target_minutes=m3_mins,
                period_type="DAILY",
                mission_category=m3_cat,
                target_count=1,
                facility=m3_fac,
                reward_points=m3_pts,
                source="AI",
                quest_date=today,
                is_active=True,
            )
            created_missions.append(m3)
            existing_titles.add(m3_title)

    return created_missions[:3]


def generate_weekly_missions(user, week_start=None):
    """
    주간 미션 10개 생성 (매주 변경):
    1. 출석 누적 미션 (1개): 이번 주 3일 이상 출석 달성하기 (고정)
    2~10. AI 주간 미션 9개: 주차(ISO Week % 4) 시즌 로테이션에 따라 매주 변경
    """
    if week_start is None:
        week_start, _ = get_current_week_bounds()

    existing = list(PersonalDailyQuest.objects.filter(
        user=user, period_type="WEEKLY", week_start=week_start, is_active=True
    ))
    if len(existing) >= 10:
        return existing[:10]

    existing_titles = {q.title for q in existing}
    created_missions = list(existing)

    profile = getattr(user, "profile", None)
    user_area = getattr(profile, "area", "서울특별시") or "서울특별시"
    facilities = list(Facility.objects.filter(region=user_area, is_active=True))

    week_num = week_start.isocalendar()[1]
    cycle = week_num % len(SOLO_WEEKLY_SEASON_POOLS)
    nearby_facility = facilities[week_num % len(facilities)] if facilities else None
    facility_name = nearby_facility.name if nearby_facility else "지역 공공체육시설"

    # 1. 출석 누적 미션 (고정)
    att_title = "이번 주 3일 이상 출석 달성하기"
    if not any(q.mission_category == "ATTENDANCE" for q in created_missions):
        m1 = PersonalDailyQuest.objects.create(
            user=user,
            title=att_title,
            description="매일 출석체크하여 이번 주 3회 출석을 달성해보세요!",
            workout_type="기타",
            target_count=3,
            target_minutes=0,
            reward_points=50,
            source="SYSTEM",
            period_type="WEEKLY",
            mission_category="ATTENDANCE",
            week_start=week_start,
            quest_date=week_start,
            is_active=True,
        )
        created_missions.append(m1)
        existing_titles.add(att_title)

    # 2~10. AI 주간 9개 미션 (시즌 로테이션)
    pool = SOLO_WEEKLY_SEASON_POOLS[cycle]
    for item in pool:
        if len(created_missions) >= 10:
            break
        raw_title = item["title"]
        title = raw_title.replace("{facility_name}", facility_name)
        desc = item["description"].replace("{user_area}", user_area)

        if title in existing_titles:
            continue

        wq = PersonalDailyQuest.objects.create(
            user=user,
            title=title,
            description=desc,
            workout_type=item["workout_type"],
            target_minutes=item["target_minutes"],
            period_type="WEEKLY",
            mission_category=item["category"],
            target_count=item["target_count"],
            facility=nearby_facility if item.get("use_facility") else None,
            week_start=week_start,
            reward_points=item["reward_points"],
            source="AI",
            quest_date=week_start,
            is_active=True,
        )
        created_missions.append(wq)
        existing_titles.add(title)

    return created_missions[:10]


def check_in_daily_attendance(user):
    """
    사용자의 오늘 일일 출석 체크를 수행합니다.
    1. AttendanceRecord 생성 (오늘 첫 출석)
    2. 오늘의 일일 출석 미션 완료 처리 및 30점 배지 지급
    3. 이번 주 주간 출석 누적 미션 진행도(+1) 갱신
    """
    today = timezone.localdate()
    week_start, week_end = get_current_week_bounds(today)

    record, is_first_today = AttendanceRecord.objects.get_or_create(user=user, date=today)

    # 오늘의 일일 출석 퀘스트 찾기
    daily_att = PersonalDailyQuest.objects.filter(
        user=user, period_type="DAILY", mission_category="ATTENDANCE", quest_date=today, is_active=True
    ).first()

    if daily_att:
        award, created = BadgeAward.objects.get_or_create(
            user=user, personal_quest=daily_att,
            defaults={"badge_type": BadgeAward.BRONZE, "points": daily_att.reward_points or 30, "source": "DAILY_QUEST"}
        )
        if created:
            # 최근 운동 기록에도 자동 등록
            rec = WorkoutRecord.objects.create(
                user=user,
                workout_type="기타",
                custom_workout_name="출석 체크 완료",
                minutes=10,
                location="NetFit 데일리 출석",
            )
            award.workout_record = rec
            award.save(update_fields=["workout_record"])

    # 이번 주 출석 횟수 계산 및 주간 출석 미션 누적
    weekly_att_count = AttendanceRecord.objects.filter(
        user=user, date__range=(week_start, week_end)
    ).count()

    weekly_att = PersonalDailyQuest.objects.filter(
        user=user, period_type="WEEKLY", mission_category="ATTENDANCE", week_start=week_start, is_active=True
    ).first()

    if weekly_att:
        weekly_att.current_progress = weekly_att_count
        weekly_att.save(update_fields=["current_progress"])

    return is_first_today, weekly_att_count


def sync_mission_progress(user):
    """
    사용자의 오늘 운동 기록 및 이번 주 운동/출석 기록을 바탕으로
    일일 미션(3개)과 주간 미션(10개)의 진행률과 상태를 계산하여 반환합니다.
    """
    today = timezone.localdate()
    week_start, week_end = get_current_week_bounds(today)

    daily_missions = sorted(
        generate_daily_missions(user, today),
        key=lambda q: (0 if q.mission_category == "ATTENDANCE" else 1, q.created_at or timezone.now())
    )
    weekly_missions = sorted(
        generate_weekly_missions(user, week_start),
        key=lambda q: (0 if q.mission_category == "ATTENDANCE" else 1, q.created_at or timezone.now())
    )

    today_records = list(WorkoutRecord.objects.filter(user=user, created_at__date=today))
    week_records = list(WorkoutRecord.objects.filter(user=user, created_at__date__range=(week_start, week_end)))
    week_attendances = AttendanceRecord.objects.filter(user=user, date__range=(week_start, week_end)).count()
    today_attended = AttendanceRecord.objects.filter(user=user, date=today).exists()

    all_mission_ids = [m.id for m in daily_missions + weekly_missions]
    badge_map = {
        award.personal_quest_id: award
        for award in BadgeAward.objects.filter(user=user, personal_quest_id__in=all_mission_ids)
    }

    # 1. 일일 미션 동기화 (3개)
    for q in daily_missions:
        is_done = q.id in badge_map
        q.is_completed = is_done
        q.badge_award = badge_map.get(q.id)

        if q.mission_category == "ATTENDANCE":
            done_val = 1 if today_attended else 0
            target_val = 1
            q.done_label = "출석 완료" if (is_done or today_attended) else "미출석"
            q.progress_percent = 100 if (is_done or today_attended) else 0
            q.done_value = done_val
            q.target_value = target_val
        else:
            done_mins = sum(r.minutes for r in today_records if r.workout_type == q.workout_type or q.workout_type == "기타")
            q.done_value = min(done_mins, q.target_minutes) if q.target_minutes else done_mins
            q.target_value = q.target_minutes
            q.remaining_minutes = max(0, q.target_minutes - done_mins) if q.target_minutes else 0
            q.progress_percent = 100 if is_done else (min(100, int((done_mins / q.target_minutes * 100))) if q.target_minutes else 0)
            q.done_label = f"{q.done_value}/{q.target_minutes}분"

    # 2. 주간 미션 동기화 (10개)
    week_total_minutes = sum(r.minutes for r in week_records)
    week_distinct_days = len({r.created_at.date() for r in week_records})
    week_total_dist = sum(float(r.distance_km) for r in week_records)
    week_distinct_types = len({r.workout_type for r in week_records if r.workout_type})
    week_intense_count = sum(1 for r in week_records if r.minutes >= 40)
    week_total_cals = sum(r.calories_burned for r in week_records)
    week_facility_count = sum(1 for r in week_records if any(term in (r.location or "") for term in ["체육", "센터", "공원", "경기장", "시설", "방문"]))
    week_daily_clears = BadgeAward.objects.filter(
        user=user, personal_quest__period_type="DAILY", awarded_at__date__range=(week_start, week_end)
    ).count()
    week_social_count = sum(1 for r in week_records if r.with_party)

    for q in weekly_missions:
        is_done = q.id in badge_map
        q.is_completed = is_done
        q.badge_award = badge_map.get(q.id)

        t = q.title.lower()
        if q.mission_category == "ATTENDANCE":
            target = q.target_count or 3
            q.done_value = week_attendances
            q.target_value = target
            q.done_label = f"{week_attendances}/{target}일"
            q.progress_percent = 100 if is_done else min(100, int((week_attendances / target * 100)))
        elif "km" in t:
            dist = round(week_total_dist, 1)
            target = q.target_count or 8
            q.done_value = dist
            q.target_value = target
            q.done_label = f"{dist}/{target}km"
            q.progress_percent = 100 if is_done else min(100, int((dist / target * 100)))
        elif "kcal" in t or "칼로리" in t:
            target = q.target_count or 1000
            q.done_value = week_total_cals
            q.target_value = target
            q.done_label = f"{week_total_cals}/{target}kcal"
            q.progress_percent = 100 if is_done else min(100, int((week_total_cals / target * 100)))
        elif "종목" in t:
            target = q.target_count or 2
            q.done_value = week_distinct_types
            q.target_value = target
            q.done_label = f"{week_distinct_types}/{target}종목"
            q.progress_percent = 100 if is_done else min(100, int((week_distinct_types / target * 100)))
        elif "일 이상" in t or "일간" in t or "일 운동" in t:
            target = q.target_count or 3
            q.done_value = week_distinct_days
            q.target_value = target
            q.done_label = f"{week_distinct_days}/{target}일"
            q.progress_percent = 100 if is_done else min(100, int((week_distinct_days / target * 100)))
        elif "일일 미션" in t or "클리어" in t:
            target = q.target_count or 5
            q.done_value = week_daily_clears
            q.target_value = target
            q.done_label = f"{week_daily_clears}/{target}회"
            q.progress_percent = 100 if is_done else min(100, int((week_daily_clears / target * 100)))
        elif q.mission_category == "FACILITY" or "체육시설" in t or "방문" in t or "코스 산책" in t:
            q.done_value = 1 if (week_facility_count > 0 or is_done) else 0
            q.target_value = 1
            q.done_label = f"{q.done_value}/1회"
            q.progress_percent = 100 if (week_facility_count > 0 or is_done) else 0
        elif ("집중" in t or "연속" in t or "롱세션" in t or "리프레시" in t) and q.target_minutes:
            target_min = q.target_minutes or 40
            intense_count = sum(1 for r in week_records if r.minutes >= target_min)
            q.done_value = 1 if (intense_count > 0 or is_done) else 0
            q.target_value = 1
            q.done_label = f"{q.done_value}/1회"
            q.progress_percent = 100 if (intense_count > 0 or is_done) else 0
        elif q.mission_category == "CUMULATIVE" and q.target_minutes > 0:
            target = q.target_minutes
            q.done_value = week_total_minutes
            q.target_value = target
            q.done_label = f"{week_total_minutes}/{target}분"
            q.progress_percent = 100 if is_done else min(100, int((week_total_minutes / target * 100)))
        elif "배틀" in t or "친구" in t or "소셜" in t or "파티" in t:
            target = q.target_count or 1
            q.done_value = min(week_social_count, target) if not is_done else target
            q.target_value = target
            q.done_label = f"{q.done_value}/{target}회"
            q.progress_percent = 100 if is_done else min(100, int((week_social_count / target * 100)))
        else:
            q.done_value = 0
            q.target_value = 1
            q.done_label = "0/1"
            q.progress_percent = 100 if is_done else 0

    return {
        "daily_missions": daily_missions,
        "weekly_missions": weekly_missions,
        "today_attended": today_attended,
        "week_attendances": week_attendances,
    }


def generate_party_daily_missions(party, today=None):
    """
    파티 일일 미션 3개 생성 (출석 미션 제외, 매일 변경):
    파티의 운동 종목(party.workout_type)에 100% 맞춤 생성됩니다.
    1. AI 파티 협동 메인 유산소/스포츠 세션 (30분)
    2. AI 파티 협동 강화/인터벌 세션 (30분)
    3. AI 파티 공공체육시설 연계 또는 데일리 챌린지 (25~30분)
    """
    if today is None:
        today = timezone.localdate()

    p_workout = (party.workout_type or "러닝").strip()
    existing = list(DailyQuest.objects.filter(
        party=party, period_type="DAILY", quest_date=today, is_active=True
    ))

    # 기존 미션이 다른 운동 종목으로 생성되어 있다면 파티 종목에 맞게 업데이트
    for q in existing:
        if p_workout and q.workout_type != p_workout and p_workout != "기타":
            q.workout_type = p_workout
            if "러닝" in q.title and p_workout != "러닝":
                q.title = q.title.replace("러닝", p_workout)
            elif "웨이트" in q.title and p_workout != "헬스":
                q.title = q.title.replace("웨이트", p_workout)
            elif "농구" in q.title and p_workout != "농구":
                q.title = q.title.replace("농구", p_workout)
            q.save(update_fields=["workout_type", "title"])

    # 사용자가 직접 입력한 퀘스트(DIRECT)가 존재할 경우:
    # AI 퀘스트를 자동 생성하지 않고 사용자가 만든 직접입력 퀘스트만 단독 반환
    direct_missions = [q for q in existing if q.source == "DIRECT"]
    if direct_missions:
        # 이전에 자동 생성된 AI 퀘스트가 섞여 있다면 정리하여 순수 직접입력 미션만 유지
        DailyQuest.objects.filter(
            party=party, period_type="DAILY", quest_date=today, source="AI"
        ).delete()
        return direct_missions

    if len(existing) >= 3:
        return existing

    created_missions = list(existing)
    existing_titles = {q.title for q in existing}

    owner = party.owner
    owner_profile = getattr(owner, "profile", None) if owner else None
    owner_area = getattr(owner_profile, "area", "서울특별시") or "서울특별시"
    facilities = list(Facility.objects.filter(region=owner_area, is_active=True))

    weekday = today.weekday()
    day_seed = today.year * 1000 + today.timetuple().tm_yday

    # 1. 파티 협동 메인 미션 (파티 운동 종목 맞춤)
    templates = WORKOUT_PARTY_DAILY_TEMPLATES.get(p_workout)
    if templates:
        c_title, c_desc, c_mins, c_pts = templates[weekday % len(templates)]
    else:
        c_title = f"파티 협동 {p_workout} 30분"
        c_desc = f"새로운 한 주를 여는 파티원들과의 30분 {p_workout} 협동 세션!"
        c_mins, c_pts = 30, 50

    if len(created_missions) < 1 and c_title not in existing_titles:
        q1 = DailyQuest.objects.create(
            party=party,
            creator=party.owner,
            title=c_title,
            description=c_desc,
            workout_type=p_workout,
            target_minutes=c_mins,
            period_type="DAILY",
            mission_category="WORKOUT",
            target_count=1,
            reward_points=c_pts,
            source="AI",
            quest_date=today,
            is_active=True,
        )
        created_missions.append(q1)
        existing_titles.add(c_title)

    # 2. 파티 협동 강화/테크닉 세션 (파티 운동 종목 맞춤)
    strength_templates = WORKOUT_PARTY_SECONDARY_TEMPLATES.get(p_workout)
    if strength_templates:
        s_title, s_desc, s_mins, s_pts = strength_templates[weekday % len(strength_templates)]
    else:
        s_title = f"파티원과 함께 {p_workout} 인터벌 & 체력 강화 30분"
        s_desc = f"파티원들과 함께 {p_workout} 세션을 집중 완수해보세요."
        s_mins, s_pts = 30, 50

    if len(created_missions) < 2 and s_title not in existing_titles:
        q2 = DailyQuest.objects.create(
            party=party,
            creator=party.owner,
            title=s_title,
            description=s_desc,
            workout_type=p_workout,
            target_minutes=s_mins,
            period_type="DAILY",
            mission_category="WORKOUT",
            target_count=1,
            reward_points=s_pts,
            source="AI",
            quest_date=today,
            is_active=True,
        )
        created_missions.append(q2)
        existing_titles.add(s_title)

    # 3. 파티 체육시설 연계 또는 데일리 챌린지 (매일 변경, 파티 운동 종목 맞춤)
    if len(created_missions) < 3:
        if facilities:
            nearby_facility = facilities[day_seed % len(facilities)]
            f_title = f"[{nearby_facility.name}] 파티 체육시설 현장 인증 및 {p_workout} 30분"
            f_desc = f"{owner_area} 체육시설에서 파티원들과 함께 {p_workout}을 즐기며 인증해보세요."
            f_mins = 30
            f_pts = 50
            f_cat = "FACILITY"
            f_fac = nearby_facility
            f_cname = f"체육시설 파티 {p_workout}"
        else:
            f_title = f"파티 {p_workout} 데일리 챌린지 25분"
            f_desc = f"파티원 전원이 힘을 모아 25분 {p_workout} 루틴을 완수하세요."
            f_mins = 25
            f_pts = 40
            f_cat = "WORKOUT"
            f_fac = None
            f_cname = ""

        if f_title not in existing_titles:
            q3 = DailyQuest.objects.create(
                party=party,
                creator=party.owner,
                title=f_title,
                description=f_desc,
                workout_type=p_workout,
                custom_workout_name=f_cname,
                target_minutes=f_mins,
                period_type="DAILY",
                mission_category=f_cat,
                target_count=1,
                facility=f_fac,
                reward_points=f_pts,
                source="AI",
                quest_date=today,
                is_active=True,
            )
            created_missions.append(q3)
            existing_titles.add(f_title)

    return created_missions


def generate_party_weekly_missions(party, week_start=None):
    """
    파티 주간 미션 10개 생성 (출석 누적 제외, 매주 변경):
    - 파티의 운동 종목(party.workout_type)을 반영하여 매주 10개 파티 협동/합산 미션이 생성됩니다.
    """
    if week_start is None:
        week_start, _ = get_current_week_bounds()

    p_workout = (party.workout_type or "러닝").strip()
    existing = list(DailyQuest.objects.filter(
        party=party, period_type="WEEKLY", week_start=week_start, is_active=True
    ))

    # 기존 주간 미션 중 종목 업데이트가 필요한 항목 동기화
    for q in existing:
        if p_workout and q.workout_type not in ["기타", p_workout] and p_workout != "기타":
            q.workout_type = p_workout
            if "러닝" in q.title and p_workout != "러닝":
                q.title = q.title.replace("러닝", p_workout)
            q.save(update_fields=["workout_type", "title"])

    if len(existing) >= 10:
        return existing[:10]

    created_missions = list(existing)
    existing_titles = {q.title for q in existing}

    owner = party.owner
    owner_profile = getattr(owner, "profile", None) if owner else None
    owner_area = getattr(owner_profile, "area", "서울특별시") or "서울특별시"
    facilities = list(Facility.objects.filter(region=owner_area, is_active=True))

    week_num = week_start.isocalendar()[1]
    cycle = week_num % len(PARTY_WEEKLY_SEASON_POOLS)
    nearby_facility = facilities[week_num % len(facilities)] if facilities else None
    facility_name = nearby_facility.name if nearby_facility else "우리 지역 공공체육시설"

    pool = PARTY_WEEKLY_SEASON_POOLS[cycle]
    for item in pool:
        if len(created_missions) >= 10:
            break
        title = item["title"].replace("{facility_name}", facility_name)
        desc = item["description"].replace("{owner_area}", owner_area)
        w_type = item["workout_type"]

        if p_workout and p_workout != "기타":
            if w_type != "기타":
                w_type = p_workout
            if p_workout != "러닝":
                title = title.replace("러닝/산책 거리 20km 완주하기", f"{p_workout} 150분 완주하기")
                title = title.replace("러닝/산책 거리 25km 돌파하기", f"{p_workout} 180분 돌파하기")
                title = title.replace("러닝", p_workout)
                desc = desc.replace("러닝", p_workout)

        if title in existing_titles:
            continue

        wq = DailyQuest.objects.create(
            party=party,
            creator=party.owner,
            title=title,
            description=desc,
            workout_type=w_type,
            target_minutes=item["target_minutes"],
            period_type="WEEKLY",
            mission_category=item["category"],
            target_count=item["target_count"],
            facility=nearby_facility if item.get("use_facility") else None,
            week_start=week_start,
            reward_points=item["reward_points"],
            source="AI",
            quest_date=week_start,
            is_active=True,
        )
        created_missions.append(wq)
        existing_titles.add(title)

    return created_missions[:10]


def sync_party_mission_progress(party, current_user):
    """
    파티원 전원의 오늘 및 이번 주 운동 데이터를 집계하여
    파티 일일 미션(3개)과 파티 주간 미션(10개)의 진행률, 달성 현황 및 파티원 실시간 모니터링을 동기화합니다.
    파티원들의 실시간 순위(rank)와 챌린지 점수(score)도 함께 계산하여 바인딩합니다.
    """
    today = timezone.localdate()
    week_start, week_end = get_current_week_bounds(today)

    party_daily_missions = generate_party_daily_missions(party, today)
    party_weekly_missions = generate_party_weekly_missions(party, week_start)

    members = list(party.members.all().select_related("profile", "charactercard"))
    member_ids = [m.id for m in members]

    # 오늘 및 이번 주 파티원 운동 기록
    party_today_records = list(WorkoutRecord.objects.filter(user_id__in=member_ids, created_at__date=today))
    party_week_records = list(WorkoutRecord.objects.filter(user_id__in=member_ids, created_at__date__range=(week_start, week_end)))

    # 파티 배지 내기 스코어 및 순위 집계
    if party.challenge_start and party.challenge_end:
        points_map = dict(
            BadgeAward.objects.filter(
                user__in=members,
                awarded_at__date__range=(party.challenge_start, party.challenge_end),
            )
            .values("user_id")
            .annotate(total=Sum("points"))
            .values_list("user_id", "total")
        )
    else:
        points_map = dict(
            BadgeAward.objects.filter(user__in=members)
            .values("user_id")
            .annotate(total=Sum("points"))
            .values_list("user_id", "total")
        )

    # 점수 내림차순 정렬
    member_points_list = []
    for m in members:
        pts = points_map.get(m.id, 0) or 0
        member_points_list.append((m, pts))
    member_points_list.sort(key=lambda x: x[1], reverse=True)

    member_rank_map = {}
    for idx, (m, pts) in enumerate(member_points_list, start=1):
        member_rank_map[m.id] = (idx, pts)

    # 파티 주간 합산 지표
    party_week_total_minutes = sum(r.minutes for r in party_week_records)
    party_week_distinct_days = len({r.created_at.date() for r in party_week_records})
    party_week_total_dist = sum(float(r.distance_km) for r in party_week_records)
    party_week_distinct_types = len({r.workout_type for r in party_week_records if r.workout_type})
    party_week_intense_count = sum(1 for r in party_week_records if r.minutes >= 40)
    party_week_total_cals = sum(r.calories_burned for r in party_week_records)
    party_facility_count = sum(1 for r in party_week_records if any(term in (r.location or "") for term in ["체육", "센터", "공원", "경기장", "시설", "방문"]))
    party_week_daily_clears = BadgeAward.objects.filter(
        user_id__in=member_ids, daily_quest__period_type="DAILY", awarded_at__date__range=(week_start, week_end)
    ).count()
    party_social_count = sum(1 for r in party_week_records if r.with_party)

    all_party_quest_ids = [q.id for q in party_daily_missions + party_weekly_missions]
    all_awards = list(BadgeAward.objects.filter(daily_quest_id__in=all_party_quest_ids))
    award_map = {}
    for award in all_awards:
        award_map[(award.daily_quest_id, award.user_id)] = award

    # 1. 파티 일일 미션 (3개)
    for q in party_daily_missions:
        is_done = (q.id, current_user.id) in award_map
        q.is_completed = is_done
        q.badge_award = award_map.get((q.id, current_user.id))

        done_mins = sum(r.minutes for r in party_today_records if r.workout_type == q.workout_type or q.workout_type == "기타")
        q.done_value = min(done_mins, q.target_minutes) if q.target_minutes else done_mins
        q.target_value = q.target_minutes
        q.remaining_minutes = max(0, q.target_minutes - done_mins) if q.target_minutes else 0
        q.progress_percent = 100 if is_done else (min(100, int((done_mins / q.target_minutes * 100))) if q.target_minutes else 0)
        q.done_label = f"{q.done_value}/{q.target_minutes}분"

        # 파티원 실시간 모니터링 (순위 및 점수 포함, 1위부터 순위순 정렬)
        members_status = []
        for m, pts in member_points_list:
            m_done = (q.id, m.id) in award_map
            rank, score = member_rank_map[m.id]
            members_status.append({
                "user": m,
                "name": m.profile.display_name or m.username,
                "level": getattr(getattr(m, "charactercard", None), "level", 1),
                "is_done": m_done,
                "is_me": (m.id == current_user.id),
                "rank": rank,
                "score": score,
            })
        q.members_monitoring = members_status

    # 2. 파티 주간 미션 (10개)
    for q in party_weekly_missions:
        is_done = (q.id, current_user.id) in award_map
        q.is_completed = is_done
        q.badge_award = award_map.get((q.id, current_user.id))

        t = q.title.lower()
        if "km" in t:
            dist = round(party_week_total_dist, 1)
            target = q.target_count or 20
            q.done_value = dist
            q.target_value = target
            q.done_label = f"{dist}/{target}km"
            q.progress_percent = 100 if is_done else min(100, int((dist / target * 100)))
        elif "kcal" in t or "칼로리" in t:
            target = q.target_count or 2500
            q.done_value = party_week_total_cals
            q.target_value = target
            q.done_label = f"{party_week_total_cals}/{target}kcal"
            q.progress_percent = 100 if is_done else min(100, int((party_week_total_cals / target * 100)))
        elif "종목" in t:
            target = q.target_count or 3
            q.done_value = party_week_distinct_types
            q.target_value = target
            q.done_label = f"{party_week_distinct_types}/{target}종목"
            q.progress_percent = 100 if is_done else min(100, int((party_week_distinct_types / target * 100)))
        elif "일 이상" in t or "일간" in t or "일 운동" in t or ("일" in t and "함께" in t):
            target = q.target_count or 3
            q.done_value = party_week_distinct_days
            q.target_value = target
            q.done_label = f"{party_week_distinct_days}/{target}일"
            q.progress_percent = 100 if is_done else min(100, int((party_week_distinct_days / target * 100)))
        elif "클리어" in t or "일일 미션" in t:
            target = q.target_count or 5
            q.done_value = party_week_daily_clears
            q.target_value = target
            q.done_label = f"{party_week_daily_clears}/{target}회"
            q.progress_percent = 100 if is_done else min(100, int((party_week_daily_clears / target * 100)))
        elif q.mission_category == "FACILITY" or "체육시설" in t or "시설" in t:
            q.done_value = 1 if (party_facility_count > 0 or is_done) else 0
            q.target_value = 1
            q.done_label = f"{q.done_value}/1회"
            q.progress_percent = 100 if (party_facility_count > 0 or is_done) else 0
        elif "주말" in t and q.target_minutes:
            weekend_mins = sum(r.minutes for r in party_week_records if r.created_at.weekday() in [5, 6])
            q.done_value = 1 if (weekend_mins >= q.target_minutes or is_done) else 0
            q.target_value = 1
            q.done_label = f"{q.done_value}/1회"
            q.progress_percent = 100 if (weekend_mins >= q.target_minutes or is_done) else 0
        elif ("집중" in t or "세션" in t or "인터벌" in t or "트레이닝" in t) and q.target_minutes and q.mission_category == "WORKOUT":
            intense_count = sum(1 for r in party_week_records if r.minutes >= q.target_minutes)
            q.done_value = 1 if (intense_count > 0 or is_done) else 0
            q.target_value = 1
            q.done_label = f"{q.done_value}/1회"
            q.progress_percent = 100 if (intense_count > 0 or is_done) else 0
        elif q.mission_category == "CUMULATIVE" and q.target_minutes > 0:
            target = q.target_minutes
            q.done_value = party_week_total_minutes
            q.target_value = target
            q.done_label = f"{party_week_total_minutes}/{target}분"
            q.progress_percent = 100 if is_done else min(100, int((party_week_total_minutes / target * 100)))
        elif "배틀" in t:
            target = q.target_count or 1
            q.done_value = min(party_social_count, target) if not is_done else target
            q.target_value = target
            q.done_label = f"{q.done_value}/{target}회"
            q.progress_percent = 100 if is_done else min(100, int((party_social_count / target * 100)))
        else:
            q.done_value = 0
            q.target_value = 1
            q.done_label = "0/1"
            q.progress_percent = 100 if is_done else 0

        # 파티원 실시간 모니터링 (순위 및 점수 포함, 1위부터 순위순 정렬)
        members_status = []
        for m, pts in member_points_list:
            m_done = (q.id, m.id) in award_map
            rank, score = member_rank_map[m.id]
            members_status.append({
                "user": m,
                "name": m.profile.display_name or m.username,
                "level": getattr(getattr(m, "charactercard", None), "level", 1),
                "is_done": m_done,
                "is_me": (m.id == current_user.id),
                "rank": rank,
                "score": score,
            })
        q.members_monitoring = members_status

    return {
        "daily_missions": party_daily_missions,
        "weekly_missions": party_weekly_missions,
    }


def search_facilities_for_fitbot(region=None, query=None, request=None):
    """Fitbot 백곰 시설 검색용 서비스 함수.
    is_active=True인 시설 중 region 및 query 조건에 맞는 시설 최대 5개를 반환합니다."""
    from .models import Facility
    from django.db.models import Q

    qs = Facility.objects.filter(is_active=True)
    if region and region != "전체":
        qs = qs.filter(region=region)
    if query:
        query_text = query.strip()
        if query_text:
            qs = qs.filter(
                Q(name__icontains=query_text)
                | Q(address__icontains=query_text)
                | Q(facility_type__icontains=query_text)
            )

    results = []
    for fac in qs[:5]:
        results.append({
            "name": fac.name,
            "address": fac.address or fac.region or "",
            "url": fac.naver_map_url or fac.homepage_url or "",
        })
    return results



