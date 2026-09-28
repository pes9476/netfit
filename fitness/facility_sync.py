import hashlib
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit

from .models import Facility


REGION_ALIASES = {
    "전남광주통합특별시": "광주광역시",
    "강원도": "강원특별자치도",
    "전라북도": "전북특별자치도",
    "제주도": "제주특별자치도",
}
EXPLICIT_SOURCE_ID_COLUMNS = ("SOURCE_RECORD_ID", "FCLTY_ID", "FCLTY_NO")
SENSITIVE_VALUE_PATTERN = re.compile(
    r"(?i)(postgres(?:ql)?://)[^\s]+|((?:password|token|secret)\s*[=:]\s*)[^\s,;]+"
)


class FacilityRowError(ValueError):
    pass


def normalize_identity_part(value):
    normalized = unicodedata.normalize("NFKC", value or "").strip().lower()
    return re.sub(r"\s+", " ", normalized)


def facility_source_record_id(row):
    explicit_id = next(
        (normalize_identity_part(row.get(column)) for column in EXPLICIT_SOURCE_ID_COLUMNS
         if normalize_identity_part(row.get(column))),
        "",
    )
    if explicit_id:
        identity = f"source:{explicit_id}"
    else:
        name = normalize_identity_part(row.get("FCLTY_NM"))
        address = normalize_identity_part(row.get("RDNMADR_NM"))
        if not name:
            raise FacilityRowError("시설명이 비어 있습니다.")
        identity = f"name:{name}|address:{address}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _coordinate(value, label, minimum, maximum):
    value = (value or "").strip()
    if not value:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise FacilityRowError(f"{label} 값이 숫자가 아닙니다.") from exc
    if not minimum <= parsed <= maximum:
        raise FacilityRowError(f"{label} 값이 허용 범위를 벗어났습니다.")
    return parsed


def facility_defaults_from_row(row):
    name = (row.get("FCLTY_NM") or "").strip()
    if not name:
        raise FacilityRowError("시설명이 비어 있습니다.")

    region = (
        (row.get("ROAD_NM_CTPRVN_NM") or "").strip()
        or (row.get("POSESN_MBY_CTPRVN_NM") or "").strip()
    )
    region = REGION_ALIASES.get(region, region)
    valid_regions = dict(Facility._meta.get_field("region").choices)
    if region not in valid_regions:
        raise FacilityRowError(f"지원하지 않는 지역입니다: {region or '(없음)'}")

    longitude = _coordinate(row.get("FCLTY_LO"), "경도", -180, 180)
    latitude = _coordinate(row.get("FCLTY_LA"), "위도", -90, 90)
    if (longitude is None) != (latitude is None):
        raise FacilityRowError("위도와 경도는 함께 제공해야 합니다.")

    return {
        "name": name,
        "facility_type": (row.get("FCLTY_TY_NM") or "").strip(),
        "region": region,
        "address": (row.get("RDNMADR_NM") or "").strip(),
        "longitude": longitude,
        "latitude": latitude,
        "homepage_url": (row.get("FCLTY_HMPG_URL") or "").strip(),
        "is_active": True,
    }


def sanitize_source_url(value):
    if not value:
        return ""
    parts = urlsplit(value)
    hostname = parts.hostname or ""
    netloc = hostname
    if parts.port:
        netloc = f"{hostname}:{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


def redact_error_summary(value):
    def replace(match):
        if match.group(1):
            return f"{match.group(1)}[redacted]"
        return f"{match.group(2)}[redacted]"

    return SENSITIVE_VALUE_PATTERN.sub(replace, str(value))[:1000]


def get_facility_operating_info(facility, now=None):
    """
    공공체육시설의 유형(간이운동장, 학교, 공공체육관/수영장/센터 등)과
    현재 요일 및 시각을 분석하여 실시간 운영 상태와 영업시간을 반환합니다.
    """
    from django.utils import timezone
    if now is None:
        now = timezone.localtime()

    name = getattr(facility, "name", "") or ""
    f_type = getattr(facility, "facility_type", "") or ""
    combined = f"{name} {f_type}"

    weekday = now.weekday()  # 0: 월요일, ..., 5: 토요일, 6: 일요일
    hour_val = now.hour + now.minute / 60.0

    # 1. 학교 체육시설 (초·중·고·대학교)
    if any(k in combined for k in ["초등학교", "중학교", "고등학교", "대학교", "학교"]):
        if weekday < 5 and (8.5 <= hour_val < 16.5):
            return {
                "status_code": "SCHOOL_RESTRICTED",
                "status_label": "수업 중",
                "badge_bg": "rgba(245, 158, 11, 0.15)",
                "badge_border": "rgba(245, 158, 11, 0.45)",
                "badge_color": "#F59E0B",
                "badge_icon": "fa-solid fa-graduation-cap",
                "status_detail": "방과 후(17시~) 개방",
                "hours_display": "평일 17:00~ / 주말 상시",
                "hours_text": "평일 방과 후(17:00~) 및 주말 상시 개방",
                "holiday_text": "정규 수업 시간 외 시민 자율 이용",
            }
        else:
            return {
                "status_code": "SCHOOL_OPEN",
                "status_label": "학교 개방",
                "badge_bg": "rgba(56, 189, 248, 0.15)",
                "badge_border": "rgba(56, 189, 248, 0.45)",
                "badge_color": "#38BDF8",
                "badge_icon": "fa-solid fa-school",
                "status_detail": "시민 개방 시간",
                "hours_display": "평일 17:00~ / 주말 상시",
                "hours_text": "평일 방과 후 및 주말 상시 개방",
                "holiday_text": "학사 일정 외 시민 자유 이용",
            }

    # 2. 야외 공원 / 간이운동장 / 동네체육시설 / 쉼터 / 둘레길 / 유수지 트랙 (24시간 상시 개방)
    if any(k in combined for k in [
        "간이운동장", "마을", "공원", "야외", "쉼터", "숲", "마당", "둘레길", "산책", "광장", "잔디", "놀이", "유수지", "인라인"
    ]) and not any(k in combined for k in ["수영", "빙상", "골프", "전용", "실내", "센터"]):
        return {
            "status_code": "ALWAYS_OPEN",
            "status_label": "상시 개방",
            "badge_bg": "rgba(0, 245, 155, 0.15)",
            "badge_border": "rgba(0, 245, 155, 0.4)",
            "badge_color": "var(--neon-mint)",
            "badge_icon": "fa-solid fa-tree",
            "status_detail": "24시간 이용 가능",
            "hours_display": "24시간 상시 개방",
            "hours_text": "24시간 상시 개방 (연중무휴)",
            "holiday_text": "연중무휴",
        }

    # 3. 실내 공공 체육관, 체육센터, 수영장, 테니스장 등 전문 체육시설
    is_weekend = (weekday in (5, 6))

    if is_weekend:
        open_hour = 9.0
        close_hour = 18.0
        close_str = "18:00 마감"
        next_open_str = "내일 09:00 오픈" if weekday == 5 else "화요일 06:00 오픈"
        hours_display = "주말 09:00 ~ 18:00"
    else:
        open_hour = 6.0
        close_hour = 22.0
        close_str = "22:00 마감"
        next_open_str = "내일 06:00 오픈"
        hours_display = "평일 06:00 ~ 22:00"

    # 월요일 정기휴무 판별 (수영장, 빙상장, 국민/구민체육센터 등 공공 실내시설은 월요일 정기 휴관)
    if weekday == 0 and any(k in combined for k in ["수영", "빙상", "센터"]):
        return {
            "status_code": "HOLIDAY",
            "status_label": "오늘 휴무",
            "badge_bg": "rgba(239, 68, 68, 0.15)",
            "badge_border": "rgba(239, 68, 68, 0.45)",
            "badge_color": "#F87171",
            "badge_icon": "fa-solid fa-ban",
            "status_detail": "월요일 정기휴무",
            "hours_display": "매주 월요일 정기휴무",
            "hours_text": "매주 월요일 정기휴무 (화~일 06:00~22:00)",
            "holiday_text": "매주 월요일 정기휴관",
        }

    if open_hour <= hour_val < close_hour:
        return {
            "status_code": "OPEN",
            "status_label": "운영 중",
            "badge_bg": "rgba(0, 245, 155, 0.15)",
            "badge_border": "rgba(0, 245, 155, 0.45)",
            "badge_color": "var(--neon-mint)",
            "badge_icon": "fa-solid fa-door-open",
            "status_detail": f"실시간 · {close_str}",
            "hours_display": hours_display,
            "hours_text": "평일 06:00~22:00 · 주말 09:00~18:00",
            "holiday_text": "시설별 상이 (월요일 휴관 다수)",
        }
    else:
        return {
            "status_code": "CLOSED",
            "status_label": "운영 종료",
            "badge_bg": "rgba(245, 158, 11, 0.15)",
            "badge_border": "rgba(245, 158, 11, 0.45)",
            "badge_color": "#F59E0B",
            "badge_icon": "fa-solid fa-moon",
            "status_detail": f"{next_open_str}",
            "hours_display": hours_display,
            "hours_text": "평일 06:00~22:00 · 주말 09:00~18:00",
            "holiday_text": "시설별 상이 (월요일 휴관 다수)",
        }

