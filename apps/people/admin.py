from django.contrib import admin

from apps.people.models import Person
from apps.wristbands.models import Wristband


class WristbandInline(admin.TabularInline):
    model = Wristband
    extra = 0
    fields = ("uid", "status", "issued_at", "expires_at", "last_seen_at")
    readonly_fields = ("last_seen_at",)
    show_change_link = True


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = (
        "last_name",
        "first_name",
        "middle_name",
        "person_type",
        "status",
        "valid_until",
        "updated_at",
    )
    list_filter = ("person_type", "status")
    search_fields = ("last_name", "first_name", "middle_name", "email", "phone")
    readonly_fields = ("created_at", "updated_at")
    inlines = (WristbandInline,)

