from __future__ import annotations

from datetime import datetime

from django.utils import timezone

from apps.access.models import AccessPoint
from apps.access.services import AccessDecision
from apps.controllers.models import Controller
from apps.events.models import AccessEvent


class EventLoggingService:
    def log_access_decision(
        self,
        *,
        decision: AccessDecision,
        access_point: AccessPoint,
        credential_uid: str,
        controller: Controller | None = None,
        occurred_at: datetime | None = None,
        direction: str = AccessEvent.Direction.UNKNOWN,
        raw_payload: dict | None = None,
    ) -> AccessEvent:
        effective_time = self._normalize_datetime(occurred_at)
        normalized_uid = credential_uid.strip().upper()

        event_type = (
            AccessEvent.EventType.ACCESS_GRANTED
            if decision.granted
            else AccessEvent.EventType.ACCESS_DENIED
        )
        event_decision = (
            AccessEvent.Decision.GRANTED
            if decision.granted
            else AccessEvent.Decision.DENIED
        )

        return AccessEvent.objects.create(
            controller_id=controller.id if controller else access_point.controller_id,
            access_point_id=access_point.id,
            person_id=decision.person_id,
            wristband_id=decision.wristband_id,
            credential_uid=normalized_uid,
            event_type=event_type,
            direction=direction,
            decision=event_decision,
            reason_code=decision.reason_code,
            message=decision.reason_message,
            occurred_at=effective_time,
            raw_payload=raw_payload or {},
        )

    def log_controller_event(
        self,
        *,
        controller: Controller,
        message: str,
        access_point: AccessPoint | None = None,
        credential_uid: str = "",
        occurred_at: datetime | None = None,
        direction: str = AccessEvent.Direction.UNKNOWN,
        reason_code: str = "",
        raw_payload: dict | None = None,
    ) -> AccessEvent:
        effective_time = self._normalize_datetime(occurred_at)

        return AccessEvent.objects.create(
            controller_id=controller.id,
            access_point_id=access_point.id if access_point else None,
            credential_uid=credential_uid.strip().upper(),
            event_type=AccessEvent.EventType.CONTROLLER_EVENT,
            direction=direction,
            decision=AccessEvent.Decision.UNKNOWN,
            reason_code=reason_code,
            message=message,
            occurred_at=effective_time,
            raw_payload=raw_payload or {},
        )

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime:
        if value is None:
            return timezone.now()

        if timezone.is_naive(value):
            return timezone.make_aware(value, timezone.get_current_timezone())

        return value
