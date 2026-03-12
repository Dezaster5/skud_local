from django.contrib import admin

from apps.ironlogic_integration.models import WebJsonRequestLog


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WebJsonRequestLog)
class WebJsonRequestLogAdmin(ReadOnlyAdmin):
    list_display = (
        "created_at",
        "operation",
        "processing_status",
        "http_status",
        "controller",
        "source_ip",
        "request_id",
    )
    list_filter = ("operation", "processing_status", "http_status")
    search_fields = ("request_id", "operation", "controller__serial_number", "source_ip", "error_message")
    readonly_fields = (
        "created_at",
        "updated_at",
        "controller",
        "request_id",
        "operation",
        "source_ip",
        "processing_status",
        "http_status",
        "token_present",
        "request_body",
        "request_payload",
        "response_payload",
        "error_message",
    )

