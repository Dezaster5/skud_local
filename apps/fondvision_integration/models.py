from django.db import models

from apps.core.models import TimeStampedModel


class FondvisionRequestLog(TimeStampedModel):
    controller = models.ForeignKey(
        "controllers.Controller",
        on_delete=models.SET_NULL,
        related_name="fondvision_request_logs",
        null=True,
        blank=True,
    )
    reader = models.ForeignKey(
        "controllers.Reader",
        on_delete=models.SET_NULL,
        related_name="fondvision_request_logs",
        null=True,
        blank=True,
    )
    wristband = models.ForeignKey(
        "wristbands.Wristband",
        on_delete=models.SET_NULL,
        related_name="fondvision_request_logs",
        null=True,
        blank=True,
    )
    access_event = models.ForeignKey(
        "events.AccessEvent",
        on_delete=models.SET_NULL,
        related_name="fondvision_request_logs",
        null=True,
        blank=True,
    )
    sender_ip = models.GenericIPAddressField(null=True, blank=True)
    request_path = models.CharField(max_length=255)
    query_string = models.TextField(blank=True)
    request_body = models.TextField(blank=True)
    raw_query_params = models.JSONField(default=dict, blank=True)
    cardid = models.CharField(max_length=64, blank=True, db_index=True)
    mjihao = models.CharField(max_length=32, blank=True)
    cjihao = models.CharField(max_length=64, blank=True, db_index=True)
    status = models.CharField(max_length=32, blank=True)
    device_time_raw = models.CharField(max_length=64, blank=True)
    device_time = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["controller", "created_at"], name="fondvision_ctrl_ts_idx"),
            models.Index(fields=["reader", "created_at"], name="fondvision_reader_ts_idx"),
            models.Index(fields=["cjihao", "created_at"], name="fondvision_cjihao_ts_idx"),
        ]

    def __str__(self) -> str:
        identifier = self.cardid or "unknown-card"
        device = self.reader.name if self.reader else (self.cjihao or "unknown-device")
        return f"{device} -> {identifier}"
