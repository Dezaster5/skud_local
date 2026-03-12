from django.contrib import admin

from apps.events.models import AccessEvent, AuditLog


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AccessEvent)
class AccessEventAdmin(ReadOnlyAdmin):
    list_display = (
        "created_at",
        "event_type",
        "decision",
        "access_point",
        "controller",
        "person",
        "wristband",
        "credential_uid",
        "reason_code",
    )
    list_filter = ("event_type", "decision", "direction", "access_point", "controller")
    search_fields = (
        "credential_uid",
        "reason_code",
        "message",
        "person__last_name",
        "person__first_name",
        "wristband__uid",
        "controller__serial_number",
    )
    readonly_fields = (
        "created_at",
        "controller",
        "access_point",
        "person",
        "wristband",
        "credential_uid",
        "event_type",
        "direction",
        "decision",
        "reason_code",
        "message",
        "occurred_at",
        "raw_payload",
    )


@admin.register(AuditLog)
class AuditLogAdmin(ReadOnlyAdmin):
    list_display = ("created_at", "source", "action", "object_type", "object_id", "actor")
    list_filter = ("source", "action", "object_type")
    search_fields = ("action", "object_type", "object_id", "object_repr", "actor__username")
    readonly_fields = ("created_at", "actor", "source", "action", "object_type", "object_id", "object_repr", "details")

