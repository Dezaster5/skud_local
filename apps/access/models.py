from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimeStampedModel


class AccessPoint(TimeStampedModel):
    class Direction(models.TextChoices):
        ENTRY = "entry", "Entry"
        EXIT = "exit", "Exit"
        BIDIRECTIONAL = "bidirectional", "Bidirectional"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        MAINTENANCE = "maintenance", "Maintenance"

    code = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=128)
    controller = models.ForeignKey(
        "controllers.Controller",
        on_delete=models.PROTECT,
        related_name="access_points",
    )
    direction = models.CharField(
        max_length=32,
        choices=Direction.choices,
        default=Direction.ENTRY,
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    device_port = models.PositiveSmallIntegerField(default=1)
    reader_ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        unique=True,
        help_text="IP address of the physical Fondvision/ER80 reader tied to this access point.",
    )
    location = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name", "id"]
        indexes = [
            models.Index(fields=["controller", "status"], name="accesspoint_ctrl_stat_idx"),
        ]

    def save(self, *args, **kwargs):
        self.code = self.code.strip().lower()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class TimeZoneRule(TimeStampedModel):
    name = models.CharField(max_length=128, unique=True)
    description = models.TextField(blank=True)
    timezone_name = models.CharField(max_length=64, default=settings.TIME_ZONE)
    weekdays = models.JSONField(
        default=list,
        help_text="ISO weekday numbers 1-7. Overnight windows are allowed via start_time > end_time.",
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["name"]

    def clean(self) -> None:
        super().clean()
        if self.start_time == self.end_time:
            raise ValidationError("start_time and end_time must define a non-zero time window.")

        if not isinstance(self.weekdays, list) or not self.weekdays:
            raise ValidationError("weekdays must contain at least one ISO weekday number.")

        invalid_days = [day for day in self.weekdays if type(day) is not int or day < 1 or day > 7]
        if invalid_days:
            raise ValidationError("weekdays must contain integer values between 1 and 7.")

    def __str__(self) -> str:
        return self.name


class AccessPolicy(TimeStampedModel):
    class Effect(models.TextChoices):
        ALLOW = "allow", "Allow"
        DENY = "deny", "Deny"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    # Row-based policy keeps the hot path queryable without extra group/template joins.
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    person = models.ForeignKey(
        "people.Person",
        on_delete=models.CASCADE,
        related_name="access_policies",
    )
    access_point = models.ForeignKey(
        AccessPoint,
        on_delete=models.CASCADE,
        related_name="access_policies",
    )
    timezone_rule = models.ForeignKey(
        TimeZoneRule,
        on_delete=models.PROTECT,
        related_name="access_policies",
        null=True,
        blank=True,
        help_text="Leave empty for 24/7 access. This is the current simple model for unrestricted access.",
    )
    effect = models.CharField(
        max_length=16,
        choices=Effect.choices,
        default=Effect.ALLOW,
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    priority = models.PositiveSmallIntegerField(
        default=100,
        db_index=True,
        help_text="Lower value means higher policy priority.",
    )
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["priority", "id"]
        indexes = [
            models.Index(
                fields=["person", "access_point", "status"],
                name="policy_person_point_idx",
            ),
            models.Index(
                fields=["access_point", "status", "priority"],
                name="policy_point_status_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            raise ValidationError("valid_until must be greater than or equal to valid_from.")

    def __str__(self) -> str:
        return f"{self.person} -> {self.access_point} ({self.effect})"
