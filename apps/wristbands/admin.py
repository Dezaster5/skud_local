from django.contrib import admin

from apps.wristbands.models import Wristband


@admin.register(Wristband)
class WristbandAdmin(admin.ModelAdmin):
    list_display = ("uid", "person", "status", "presence_state", "expires_at", "last_seen_at", "updated_at")
    list_filter = ("status", "presence_state")
    search_fields = ("uid", "person__last_name", "person__first_name", "person__middle_name")
    readonly_fields = ("created_at", "updated_at", "last_seen_at")
