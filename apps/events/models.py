from django.conf import settings
from django.db import models

from apps.core.models import CreatedAtModel


class AccessEvent(CreatedAtModel):
    class EventType(models.TextChoices):
        ACCESS_CHECK = "access_check", "Access check"
        ACCESS_GRANTED = "access_granted", "Access granted"
        ACCESS_DENIED = "access_denied", "Access denied"
        CONTROLLER_EVENT = "controller_event", "Controller event"
        SYNC_EVENT = "sync_event", "Sync event"

    class Direction(models.TextChoices):
        ENTRY = "entry", "Entry"
        EXIT = "exit", "Exit"
        UNKNOWN = "unknown", "Unknown"

    class Decision(models.TextChoices):
        GRANTED = "granted", "Granted"
        DENIED = "denied", "Denied"
        UNKNOWN = "unknown", "Unknown"

    controller = models.ForeignKey(
        "controllers.Controller",
        on_delete=models.SET_NULL,
        related_name="access_events",
        null=True,
        blank=True,
    )
    access_point = models.ForeignKey(
        "access.AccessPoint",
        on_delete=models.SET_NULL,
        related_name="access_events",
        null=True,
        blank=True,
    )
    person = models.ForeignKey(
        "people.Person",
        on_delete=models.SET_NULL,
        related_name="access_events",
        null=True,
        blank=True,
    )
    wristband = models.ForeignKey(
        "wristbands.Wristband",
        on_delete=models.SET_NULL,
        related_name="access_events",
        null=True,
        blank=True,
    )
    credential_uid = models.CharField(max_length=64, blank=True)
    event_type = models.CharField(max_length=32, choices=EventType.choices, db_index=True)
    direction = models.CharField(
        max_length=16,
        choices=Direction.choices,
        default=Direction.UNKNOWN,
    )
    decision = models.CharField(
        max_length=16,
        choices=Decision.choices,
        default=Decision.UNKNOWN,
        db_index=True,
    )
    reason_code = models.CharField(max_length=64, blank=True)
    message = models.TextField(blank=True)
    occurred_at = models.DateTimeField(null=True, blank=True, db_index=True)
    raw_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["controller", "created_at"], name="accessevent_ctrl_ts_idx"),
            models.Index(fields=["access_point", "created_at"], name="accessevent_point_ts_idx"),
        ]

    def __str__(self) -> str:
        target = self.credential_uid or (self.wristband.uid if self.wristband else "unknown")
        return f"{self.get_decision_display()}: {target}"


class AuditLog(CreatedAtModel):
    class Source(models.TextChoices):
        ADMIN = "admin", "Admin"
        API = "api", "API"
        SYSTEM = "system", "System"
        CONTROLLER = "controller", "Controller"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
        null=True,
        blank=True,
    )
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.SYSTEM, db_index=True)
    action = models.CharField(max_length=64, db_index=True)
    object_type = models.CharField(max_length=64)
    object_id = models.CharField(max_length=64)
    object_repr = models.CharField(max_length=255)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["object_type", "object_id"], name="auditlog_object_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.action} {self.object_type}#{self.object_id}"
