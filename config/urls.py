import os
from django.conf import settings
from django.contrib import admin
from django.http import Http404
from django.urls import include, path, re_path
from django.views.static import serve


def serve_media_with_fallback(request, path, **kwargs):
    """미디어 파일 서빙: MEDIA_ROOT 우선 탐색 후, 기존 업로드 경로(BASE_DIR) 및 미러 디렉토리까지 자동 폴백."""
    target = os.path.join(str(settings.MEDIA_ROOT), path)
    if os.path.exists(target):
        return serve(request, path, document_root=settings.MEDIA_ROOT)

    base_target = os.path.join(str(settings.BASE_DIR), path)
    if os.path.exists(base_target):
        return serve(request, path, document_root=settings.BASE_DIR)

    alt_dirs = [
        os.path.join(str(settings.BASE_DIR), "..", "netfit", "media"),
        os.path.join(str(settings.BASE_DIR), "..", "netfit"),
        os.path.join(str(settings.BASE_DIR), "..", "netfit-main", "media"),
        os.path.join(str(settings.BASE_DIR), "..", "netfit-main"),
    ]
    for alt in alt_dirs:
        alt_file = os.path.join(alt, path)
        if os.path.exists(alt_file):
            return serve(request, path, document_root=alt)

    raise Http404("미디어 파일을 찾을 수 없습니다.")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("fitness.urls")),
    re_path(r"^media/(?P<path>.*)$", serve_media_with_fallback),
]

