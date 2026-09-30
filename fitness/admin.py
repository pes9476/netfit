from django.contrib import admin
from django.db.models import Count, Q
from .models import BadgeAward, BodyMeasurement, CardBattle, CharacterCard, DataSyncRun, Facility, FriendLink, OutfitPurchase, Party, Profile, WorkoutRecord

admin.site.register([Profile, CharacterCard, WorkoutRecord, BadgeAward, OutfitPurchase, Facility, Party, CardBattle, BodyMeasurement, FriendLink])


@admin.register(DataSyncRun)
class DataSyncRunAdmin(admin.ModelAdmin):
    change_list_template = "admin/fitness/datasyncrun/change_list.html"
    list_display = ("started_at", "source_name", "status", "source_count",
                    "created_count", "updated_count", "skipped_count", "failed_count")
    list_filter = ("status", "source_name")
    date_hierarchy = "started_at"
    ordering = ("-started_at", "-pk")
    readonly_fields = tuple(field.name for field in DataSyncRun._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        # Keep the dashboard under the same model permission as the admin list.
        if not self.has_view_or_change_permission(request):
            return super().changelist_view(request, extra_context)
        runs = self.get_queryset(request)
        recent = list(runs.order_by("-started_at", "-pk")[:20])
        latest_success = runs.filter(status=DataSyncRun.STATUS_SUCCESS).order_by("-started_at", "-pk").first()
        bars = []
        if latest_success:
            for label, field, color in (
                ("신규 생성", "created_count", "#2563eb"),
                ("기존 레코드 반영", "updated_count", "#7c3aed"),
                ("삭제 표시 제외", "skipped_count", "#64748b"),
                ("행 검증 실패", "failed_count", "#dc2626"),
            ):
                count = getattr(latest_success, field)
                bars.append({"label": label, "count": count, "color": color,
                             "max": max(latest_success.source_count, count, 1)})
        context = dict(extra_context or {})
        context.update({
            "facility_stats": Facility.objects.aggregate(
                total=Count("pk"), active=Count("pk", filter=Q(is_active=True)),
                inactive=Count("pk", filter=Q(is_active=False)),
                located=Count("pk", filter=Q(is_active=True, latitude__isnull=False, longitude__isnull=False)),
            ),
            "latest_run": recent[0] if recent else None,
            "latest_success": latest_success,
            "sync_bars": bars,
            "recent_runs": recent,
            "chart_max": max([r.source_count for r in recent] + [1]),
        })
        return super().changelist_view(request, context)
