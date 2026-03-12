from django.db import models

from apps.core.models import TimeStampedModel


class Wristband(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        BLOCKED = "blocked", "Blocked"
        LOST = "lost", "Lost"
        RETIRED = "retired", "Retired"

    uid = models.CharField(max_length=64, unique=True)
    person = models.ForeignKey(
        "people.Person",
        on_delete=models.SET_NULL,
        related_name="wristbands",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    issued_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["uid"]
        indexes = [
            models.Index(fields=["status", "expires_at"], name="wristband_status_exp_idx"),
        ]

    def save(self, *args, **kwargs):
        self.uid = self.uid.strip().upper()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.uid
