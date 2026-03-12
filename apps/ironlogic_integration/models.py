from django.db import models

from apps.core.models import TimeStampedModel


class WebJsonRequestLog(TimeStampedModel):
    class ProcessingStatus(models.TextChoices):
        PROCESSED = "processed", "Processed"
        ACCESS_DENIED = "access_denied", "Access denied"
        REJECTED = "rejected", "Rejected"
        INVALID_PAYLOAD = "invalid_payload", "Invalid payload"
        UNKNOWN_OPERATION = "unknown_operation", "Unknown operation"
        CONTROLLER_NOT_FOUND = "controller_not_found", "Controller not found"
        CONTROLLER_INACTIVE = "controller_inactive", "Controller inactive"
        ERROR = "error", "Error"

    controller = models.ForeignKey(
        "controllers.Controller",
        on_delete=models.SET_NULL,
        related_name="webjson_request_logs",
        null=True,
        blank=True,
    )
    request_id = models.CharField(max_length=128, blank=True, db_index=True)
    operation = models.CharField(max_length=64, blank=True, db_index=True)
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    processing_status = models.CharField(
        max_length=32,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.PROCESSED,
        db_index=True,
    )
    http_status = models.PositiveSmallIntegerField(default=200)
    token_present = models.BooleanField(default=False)
    request_body = models.TextField(blank=True)
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["operation", "processing_status"], name="webjson_op_status_idx"),
            models.Index(fields=["controller", "created_at"], name="webjson_ctrl_created_idx"),
        ]

    def __str__(self) -> str:
        request_id = self.request_id or "no-request-id"
        operation = self.operation or "unknown"
        return f"{operation} [{self.processing_status}] ({request_id})"

