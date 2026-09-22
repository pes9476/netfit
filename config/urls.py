from django.contrib import admin
from django.urls import include, path, re_path
from .deployment_views import healthz, serve_media


urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("", include("fitness.urls")),
    re_path(r"^media/(?P<path>.*)$", serve_media),
]

