import secrets
import time
import uuid
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.db import IntegrityError, transaction
from django.shortcuts import redirect
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_variables
from django.views.decorators.http import require_GET

from .models import KakaoAccount, needs_kakao_nickname


def fail(request, message):
    messages.error(request, message)
    return redirect("login")


@never_cache
@require_GET
def kakao_login(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if not settings.KAKAO_REST_API_KEY:
        return fail(request, "카카오 로그인 준비 중입니다. 일반 로그인을 이용해 주세요.")
    state = secrets.token_urlsafe(32)
    request.session["kakao_oauth"] = {
        "state": state, "created": time.time(),
        "redirect_uri": settings.KAKAO_REDIRECT_URI,
    }
    return redirect("https://kauth.kakao.com/oauth/authorize?" + urlencode({
        "client_id": settings.KAKAO_REST_API_KEY,
        "redirect_uri": settings.KAKAO_REDIRECT_URI,
        "response_type": "code", "state": state,
    }))


@never_cache
@require_GET
@sensitive_variables("payload", "token", "response", "data")
def kakao_callback(request):
    pending = request.session.pop("kakao_oauth", None)
    state = request.GET.get("state", "")
    if (not pending or not state
            or not secrets.compare_digest(pending["state"], state)
            or not 0 <= time.time() - pending["created"] <= 600):
        return fail(request, "로그인 요청이 만료되었거나 올바르지 않습니다. 다시 시도해 주세요.")
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.GET.get("error") or not request.GET.get("code"):
        return fail(request, "카카오 로그인이 취소되었습니다. 다시 시도해 주세요.")
    payload = {
        "grant_type": "authorization_code",
        "client_id": settings.KAKAO_REST_API_KEY,
        "redirect_uri": pending["redirect_uri"],
        "code": request.GET["code"],
    }
    if settings.KAKAO_CLIENT_SECRET:
        payload["client_secret"] = settings.KAKAO_CLIENT_SECRET
    try:
        response = requests.post("https://kauth.kakao.com/oauth/token", data=payload, timeout=10)
        response.raise_for_status()
        token = response.json()["access_token"]
        if not isinstance(token, str) or not token:
            raise ValueError("Missing token")
        response = requests.get(
            "https://kapi.kakao.com/v2/user/me",
            headers={"Authorization": f"Bearer {token}"}, timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        kakao_id = data["id"]
        if type(kakao_id) is not int or kakao_id <= 0:
            raise ValueError("Invalid user ID")
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return fail(request, "카카오 로그인에 실패했습니다. 잠시 후 다시 시도해 주세요.")

    account = KakaoAccount.objects.select_related("user").filter(kakao_id=str(kakao_id)).first()
    if account is None:
        try:
            with transaction.atomic():
                user = get_user_model().objects.create_user(
                    username="kakao_" + uuid.uuid4().hex, password=None,
                )
                account = KakaoAccount.objects.create(user=user, kakao_id=str(kakao_id))
        except IntegrityError:
            account = KakaoAccount.objects.select_related("user").filter(kakao_id=str(kakao_id)).first()
            if account is None:
                return fail(request, "계정을 생성하지 못했습니다. 다시 시도해 주세요.")
    if not account.user.is_active:
        return fail(request, "이용이 중지된 계정입니다.")
    login(request, account.user, backend="django.contrib.auth.backends.ModelBackend")
    if needs_kakao_nickname(account.user):
        messages.info(request, "사용할 닉네임을 정해 주세요. 프로필에서 언제든 변경할 수 있어요.")
        return redirect("profile")
    return redirect("dashboard")
