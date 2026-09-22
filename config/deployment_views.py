from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import connection, DatabaseError
from django.http import FileResponse, Http404, JsonResponse
from django.views.decorators.http import require_safe


@require_safe
def healthz(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


@login_required
@require_safe
def serve_media(request, path):
    """Serve images only from MEDIA_ROOT (the Railway persistent volume)."""
    root = Path(settings.MEDIA_ROOT).resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise Http404("미디어 파일을 찾을 수 없습니다.")
    image_types = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".gif": "image/gif", ".webp": "image/webp", ".avif": "image/avif",
        ".bmp": "image/bmp", ".tif": "image/tiff", ".tiff": "image/tiff",
    }
    content_type = image_types.get(target.suffix.lower())
    if not content_type:
        raise Http404("지원하지 않는 이미지 형식입니다.")
    response = FileResponse(target.open("rb"), content_type=content_type)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
