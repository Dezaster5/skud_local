from django.contrib import admin

from apps.fondvision_integration.models import FondvisionRequestLog


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FondvisionRequestLog)
class FondvisionRequestLogAdmin(ReadOnlyAdmin):
    list_display = (
        "created_at",
        "reader",
        "cjihao",
        "cardid",
        "status",
        "controller",
        "wristband",
        "sender_ip",
        "device_time",
    )
    list_filter = ("status",)
    search_fields = (
        "cardid",
        "cjihao",
        "sender_ip",
        "controller__serial_number",
        "reader__name",
        "reader__ip_address",
        "reader__external_id",
        "wristband__uid",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "controller",
        "reader",
        "wristband",
        "access_event",
        "sender_ip",
        "request_path",
        "query_string",
        "request_body",
        "raw_query_params",
        "cardid",
        "mjihao",
        "cjihao",
        "status",
        "device_time_raw",
        "device_time",
    )
