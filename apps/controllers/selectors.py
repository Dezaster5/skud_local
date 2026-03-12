from __future__ import annotations

from datetime import datetime

from django.db.models import Q
from django.utils import timezone

from apps.controllers.models import Controller, ControllerTask


def get_controller_by_serial_number(serial_number: str) -> Controller | None:
    normalized_serial_number = serial_number.strip().upper()
    if not normalized_serial_number:
        return None

    return Controller.objects.filter(serial_number=normalized_serial_number).first()


def get_pending_controller_tasks(
    controller_id: int,
    *,
    limit: int = 100,
    scheduled_before: datetime | None = None,
) -> list[ControllerTask]:
    effective_moment = _normalize_datetime(scheduled_before)

    queryset = (
        ControllerTask.objects.filter(controller_id=controller_id, status=ControllerTask.Status.PENDING)
        .filter(Q(scheduled_for__isnull=True) | Q(scheduled_for__lte=effective_moment))
        .order_by("priority", "created_at", "id")
    )

    return list(queryset[:limit])


def _normalize_datetime(value: datetime | None) -> datetime:
    if value is None:
        return timezone.now()

    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone())

    return value
