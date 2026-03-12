from django.contrib import admin

from apps.access.models import AccessPoint
from apps.controllers.models import Controller, ControllerTask


class AccessPointInline(admin.TabularInline):
    model = AccessPoint
    extra = 0
    fields = ("code", "name", "direction", "status", "device_port")
    show_change_link = True


@admin.register(Controller)
class ControllerAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "serial_number",
        "controller_type",
        "status",
        "ip_address",
        "last_seen_at",
        "updated_at",
    )
    list_filter = ("controller_type", "status")
    search_fields = ("name", "serial_number", "ip_address", "firmware_version")
    readonly_fields = ("created_at", "updated_at", "last_seen_at")
    inlines = (AccessPointInline,)


@admin.register(ControllerTask)
class ControllerTaskAdmin(admin.ModelAdmin):
    list_display = (
        "controller",
        "task_type",
        "status",
        "priority",
        "scheduled_for",
        "sent_at",
        "completed_at",
        "created_at",
    )
    list_filter = ("task_type", "status")
    search_fields = ("controller__name", "controller__serial_number", "error_message")
    readonly_fields = ("created_at", "updated_at", "sent_at", "completed_at")

