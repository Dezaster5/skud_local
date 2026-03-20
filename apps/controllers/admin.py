from django.contrib import admin

from apps.access.models import AccessPoint
from apps.controllers.models import Controller, ControllerTask, Reader


class AccessPointInline(admin.TabularInline):
    model = AccessPoint
    extra = 0
    fields = ("code", "name", "direction", "status", "device_port")
    show_change_link = True


class ReaderInline(admin.TabularInline):
    model = Reader
    extra = 0
    fields = ("name", "ip_address", "external_id", "device_number", "direction", "status")
    show_change_link = True


@admin.register(Controller)
class ControllerAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "serial_number",
        "controller_type",
        "status",
        "ip_address",
        "firmware_version",
        "connection_firmware_version",
        "active_state",
        "mode_state",
        "last_seen_at",
        "updated_at",
    )
    list_filter = ("controller_type", "status")
    search_fields = (
        "name",
        "serial_number",
        "ip_address",
        "firmware_version",
        "connection_firmware_version",
        "last_auth_hash",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "last_seen_at",
        "firmware_version",
        "connection_firmware_version",
        "active_state",
        "mode_state",
        "last_auth_hash",
    )
    inlines = (AccessPointInline, ReaderInline)


@admin.register(Reader)
class ReaderAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "controller",
        "ip_address",
        "external_id",
        "device_number",
        "direction",
        "status",
        "updated_at",
    )
    list_filter = ("direction", "status", "controller__controller_type")
    search_fields = ("name", "ip_address", "external_id", "controller__name", "controller__serial_number")
    readonly_fields = ("created_at", "updated_at")


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
