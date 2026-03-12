from django.db import models

from apps.core.models import TimeStampedModel


class Controller(TimeStampedModel):
    class ControllerType(models.TextChoices):
        IRONLOGIC_Z5R_WEB_BT = "ironlogic_z5r_web_bt", "IronLogic Z-5R Web BT"
        GENERIC_WEB_JSON = "generic_web_json", "Generic Web-JSON"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        OFFLINE = "offline", "Offline"
        MAINTENANCE = "maintenance", "Maintenance"
        DISABLED = "disabled", "Disabled"

    name = models.CharField(max_length=128)
    serial_number = models.CharField(max_length=64, unique=True)
    controller_type = models.CharField(
        max_length=64,
        choices=ControllerType.choices,
        default=ControllerType.IRONLOGIC_Z5R_WEB_BT,
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    firmware_version = models.CharField(max_length=64, blank=True)
    description = models.TextField(blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name", "serial_number"]

    def save(self, *args, **kwargs):
        self.serial_number = self.serial_number.strip().upper()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name} ({self.serial_number})"


class ControllerTask(TimeStampedModel):
    class TaskType(models.TextChoices):
        SET_ACTIVE = "set_active", "Set active"
        OPEN_DOOR = "open_door", "Open door"
        ADD_WRISTBANDS = "add_wristbands", "Add wristbands"
        DEL_WRISTBANDS = "del_wristbands", "Delete wristbands"
        CLEAR_CARDS = "clear_cards", "Clear cards"
        SET_MODE = "set_mode", "Set mode"
        SET_TIMEZONE = "set_timezone", "Set timezone"
        READ_CARDS = "read_cards", "Read cards"
        SYNC_WRISTBANDS = "sync_wristbands", "Sync wristbands"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    controller = models.ForeignKey(
        Controller,
        on_delete=models.PROTECT,
        related_name="tasks",
    )
    task_type = models.CharField(max_length=32, choices=TaskType.choices)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    payload = models.JSONField(default=dict, blank=True)
    priority = models.PositiveSmallIntegerField(
        default=100,
        db_index=True,
        help_text="Lower value means higher execution priority.",
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    error_message = models.TextField(blank=True)
    scheduled_for = models.DateTimeField(null=True, blank=True, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["priority", "created_at", "id"]
        indexes = [
            models.Index(
                fields=["controller", "status", "scheduled_for"],
                name="ctrltask_pickup_idx",
            ),
            models.Index(
                fields=["controller", "status", "priority"],
                name="ctrltask_priority_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.controller.serial_number}: {self.task_type} [{self.status}]"
