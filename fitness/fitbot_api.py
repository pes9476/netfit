"""NETFIT Fitbot Django views. Wire these views in the project's urls.py."""
import json
import logging

import requests

from django.conf import settings
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils.module_loading import import_string
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from .services import search_facilities_for_fitbot

logger = logging.getLogger(__name__)
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
ROLES = {
    "coach": "당신은 NETFIT의 친근한 백호 운동 코치입니다. 운동 목표와 기본 동작을 도와주세요. 질병 진단이나 치료를 단정하지 마세요.",
    "facility": "당신은 NETFIT의 포동 시설 안내자입니다. 제공된 검색 결과에 있는 시설만 안내하고, 없는 시설이나 주소를 만들어내지 마세요.",
    "meal": "당신은 NETFIT의 토리 식단 도우미입니다. 실천 가능한 식사 아이디어를 제안하세요. 의학적 식이요법을 처방하지 마세요.",
    "court": "당신은 NETFIT 변명재판소의 아콩 판사입니다. 가벼운 유머로 변명을 들어주고 오늘 할 수 있는 작은 행동을 제안하세요. 사용자를 비난하지 마세요.",
}
DEFAULT_REGIONS = ["서울특별시", "경기도", "인천광역시", "부산광역시", "대구광역시", "대전광역시", "광주광역시", "울산광역시", "세종특별자치시", "강원특별자치도", "충청북도", "충청남도", "전북특별자치도", "전라남도", "경상북도", "경상남도", "제주특별자치도"]


def _get_facility_search():
    search = getattr(settings, "FITBOT_FACILITY_SEARCH", None)
    if not search:
        return search_facilities_for_fitbot
    if isinstance(search, str):
        try:
            return import_string(search)
        except Exception:
            logger.exception("Failed to import FITBOT_FACILITY_SEARCH")
            return None
    if callable(search):
        return search
    return None


def _auth_error(request):
    # Set FITBOT_REQUIRE_LOGIN=False only if anonymous use is intentional.
    if getattr(settings, "FITBOT_REQUIRE_LOGIN", True) and not request.user.is_authenticated:
        return JsonResponse({"error": "로그인 후 이용해 주세요."}, status=403)
    return None


@require_GET
def bootstrap(request):
    if error := _auth_error(request):
        return error
    regions = list(getattr(settings, "FITBOT_REGIONS", DEFAULT_REGIONS))
    return JsonResponse({"csrf_token": get_token(request), "regions": regions,
                         "region": regions[0] if regions else ""})


@csrf_protect
@require_POST
def chat(request):
    if error := _auth_error(request):
        return error
    if len(request.body) > 12000:
        return JsonResponse({"error": "질문이 너무 깁니다."}, status=413)
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "요청 형식이 올바르지 않습니다."}, status=400)
    if not isinstance(data, dict):
        return JsonResponse({"error": "요청 형식이 올바르지 않습니다."}, status=400)
    role, message = data.get("role"), data.get("message")
    if role not in ROLES or not isinstance(message, str) or not 1 <= len(message.strip()) <= 800:
        return JsonResponse({"error": "질문 또는 캐릭터를 확인해 주세요."}, status=400)

    context = ""
    facilities = []
    if role == "facility":
        regions = list(getattr(settings, "FITBOT_REGIONS", DEFAULT_REGIONS))
        region, query = data.get("region"), data.get("query", "")
        if region not in regions or not isinstance(query, str) or len(query) > 60:
            return JsonResponse({"error": "검색 조건을 확인해 주세요."}, status=400)
        search = _get_facility_search()
        if not callable(search):
            return JsonResponse({"error": "시설 검색 연결이 아직 완료되지 않았습니다."}, status=503)
        try:
            found = search(region=region, query=query.strip(), request=request)
            facilities = [
                {"name": str(item["name"])[:100], "address": str(item["address"])[:200],
                 "url": str(item.get("url") or "")[:500]}
                for item in list(found)[:5]
            ]
        except Exception:
            logger.exception("Fitbot facility search failed")
            return JsonResponse({"error": "시설 검색에 실패했습니다. 잠시 후 다시 시도해 주세요."}, status=503)
        if not facilities:
            return JsonResponse({"reply": "해당 조건으로 등록된 시설을 찾지 못했어요. 다른 지역이나 검색어로 다시 찾아볼까요?", "facilities": []})
        context = "\nNETFIT 데이터베이스에서 확인된 시설:\n" + "\n".join(
            f"- {x['name']} / {x['address']}" for x in facilities
        )

    system_prompt = ROLES[role] + " 항상 자연스러운 한국어로, 4문장 이내로 답하세요." + context
    contents = []
    history = data.get("history", [])
    if isinstance(history, list):
        for item in history[-8:]:
            if isinstance(item, dict) and item.get("role") in ("user", "model") and isinstance(item.get("text"), str):
                contents.append({"role": item["role"], "parts": [{"text": item["text"][:800]}]})
    contents.append({"role": "user", "parts": [{"text": message.strip()}]})

    try:
        key = getattr(settings, "GEMINI_API_KEY", "")
        if not key:
            logger.error("GEMINI_API_KEY is not configured")
            return JsonResponse({"error": "AI 연결 설정이 필요합니다."}, status=503)
        model = getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")
        response = requests.post(
            GEMINI_API_URL.format(model=model),
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
            json={
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": contents,
                "generationConfig": {"maxOutputTokens": 800},
            },
            timeout=20,
        )
        if response.status_code == 429:
            return JsonResponse({"error": "무료 이용 한도에 도달했어요. 잠시 후 다시 시도해 주세요."}, status=429)
        response.raise_for_status()
        result = response.json()
        candidates = result.get("candidates") or []
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        reply = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
        if not reply:
            raise ValueError("Empty model response")
    except (requests.RequestException, ValueError, KeyError, IndexError):
        logger.exception("Fitbot AI request failed")
        return JsonResponse({"error": "답변 연결에 실패했어요. 잠시 후 다시 시도해 주세요."}, status=503)
    return JsonResponse({"reply": reply[:3000], "facilities": facilities})
