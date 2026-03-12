from django.contrib import admin

from apps.access.models import AccessPoint, AccessPolicy, TimeZoneRule


@admin.register(AccessPoint)
class AccessPointAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "controller", "direction", "status", "device_port", "updated_at")
    list_filter = ("direction", "status", "controller")
    search_fields = ("code", "name", "location", "controller__name", "controller__serial_number")
    readonly_fields = ("created_at", "updated_at")


@admin.register(TimeZoneRule)
class TimeZoneRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "timezone_name", "weekdays", "start_time", "end_time", "is_active", "updated_at")
    list_filter = ("is_active", "timezone_name")
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "updated_at")


@admin.register(AccessPolicy)
class AccessPolicyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "person",
        "access_point",
        "effect",
        "status",
        "priority",
        "valid_until",
        "updated_at",
    )
    list_filter = ("effect", "status", "access_point", "timezone_rule")
    search_fields = (
        "name",
        "person__last_name",
        "person__first_name",
        "access_point__name",
        "access_point__code",
    )
    readonly_fields = ("created_at", "updated_at")

