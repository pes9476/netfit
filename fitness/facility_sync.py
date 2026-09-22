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
