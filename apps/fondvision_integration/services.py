from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.access.models import AccessPoint
from apps.controllers.models import Controller
from apps.events.models import AccessEvent
from apps.fondvision_integration.models import FondvisionRequestLog
from apps.wristbands.selectors import get_wristband_by_uid


@dataclass(slots=True, frozen=True)
class FondvisionIngressResult:
    response_text: str
    access_event_id: int
    request_log_id: int


class FondvisionIngressService:
    def handle_request(
        self,
        *,
        query_params: Any,
        request_path: str,
        query_string: str,
        request_body: str,
        sender_ip: str | None,
    ) -> FondvisionIngressResult:
        raw_query_params = self._serialize_query_params(query_params)
        cardid = self._normalize_upper_scalar(raw_query_params.get("cardid"))
        cjihao = self._normalize_upper_scalar(raw_query_params.get("cjihao"))
        mjihao = self._normalize_scalar(raw_query_params.get("mjihao"))
        status = self._normalize_scalar(raw_query_params.get("status"))
        device_time_raw = self._normalize_scalar(raw_query_params.get("time"))
        device_time = self._parse_device_time(device_time_raw)

        controller = self._get_or_create_controller(cjihao=cjihao, sender_ip=sender_ip)
        wristband = get_wristband_by_uid(cardid or "") if cardid else None
        access_point = self._get_access_point(controller=controller, mjihao=mjihao)

        access_event = AccessEvent.objects.create(
            controller=controller,
            access_point=access_point,
            person_id=wristband.person_id if wristband else None,
            wristband=wristband,
            credential_uid=cardid or "",
            event_type=AccessEvent.EventType.ACCESS_CHECK,
            direction=AccessEvent.Direction.UNKNOWN,
            decision=AccessEvent.Decision.UNKNOWN,
            reason_code=self._build_reason_code(cardid=cardid, cjihao=cjihao),
            message=self._build_message(status=status, mjihao=mjihao),
            occurred_at=device_time or timezone.now(),
            raw_payload={
                "path": request_path,
                "query_string": query_string,
                "query_params": raw_query_params,
                "sender_ip": sender_ip,
            },
        )

        request_log = FondvisionRequestLog.objects.create(
            controller=controller,
            wristband=wristband,
            access_event=access_event,
            sender_ip=sender_ip,
            request_path=request_path,
            query_string=query_string,
            request_body=request_body,
            raw_query_params=raw_query_params,
            cardid=cardid or "",
            mjihao=mjihao or "",
            cjihao=cjihao or "",
            status=status or "",
            device_time_raw=device_time_raw or "",
            device_time=device_time,
        )

        return FondvisionIngressResult(
            response_text="ok",
            access_event_id=access_event.id,
            request_log_id=request_log.id,
        )

    @staticmethod
    def _serialize_query_params(query_params: Any) -> dict[str, object]:
        if hasattr(query_params, "lists"):
            serialized: dict[str, object] = {}
            for key, values in query_params.lists():
                serialized[key] = values[0] if len(values) == 1 else values
            return serialized

        if isinstance(query_params, dict):
            return dict(query_params)

        return {}

    @staticmethod
    def _normalize_scalar(value: object) -> str | None:
        if value is None:
            return None

        if isinstance(value, list):
            value = value[0] if value else None

        if value is None:
            return None

        normalized = str(value).strip()
        return normalized or None

    def _normalize_upper_scalar(self, value: object) -> str | None:
        normalized = self._normalize_scalar(value)
        if normalized is None:
            return None
        return normalized.upper()

    @staticmethod
    def _parse_device_time(value: str | None) -> datetime | None:
        if not value:
            return None

        try:
            return datetime.fromtimestamp(int(value), tz=UTC)
        except (TypeError, ValueError, OSError):
            pass

        parsed_value = parse_datetime(value)
        if parsed_value is None:
            return None

        if timezone.is_naive(parsed_value):
            return timezone.make_aware(parsed_value, timezone.get_current_timezone())

        return parsed_value

    @staticmethod
    def _build_reason_code(*, cardid: str | None, cjihao: str | None) -> str:
        if cardid and cjihao:
            return "fondvision_mcardsea"
        return "fondvision_mcardsea_incomplete"

    @staticmethod
    def _build_message(*, status: str | None, mjihao: str | None) -> str:
        parts = ["Fondvision ER80 request received."]
        if status:
            parts.append(f"status={status}")
        if mjihao:
            parts.append(f"reader={mjihao}")
        return " ".join(parts)

    @staticmethod
    def _get_access_point(*, controller: Controller | None, mjihao: str | None) -> AccessPoint | None:
        if controller is None or not mjihao:
            return None

        try:
            device_port = int(mjihao)
        except (TypeError, ValueError):
            return None

        return (
            AccessPoint.objects.filter(controller=controller, device_port=device_port)
            .order_by("id")
            .first()
        )

    @staticmethod
    def _get_or_create_controller(*, cjihao: str | None, sender_ip: str | None) -> Controller | None:
        if not cjihao:
            return None

        controller, _ = Controller.objects.get_or_create(
            serial_number=cjihao,
            defaults={
                "name": f"Fondvision {cjihao}",
                "controller_type": Controller.ControllerType.GENERIC_WEB_JSON,
                "status": Controller.Status.ACTIVE,
                "ip_address": sender_ip,
                "description": "Auto-created from legacy Fondvision ER80 /qa/mcardsea.php requests.",
            },
        )

        updated_fields: list[str] = ["last_seen_at"]
        controller.last_seen_at = timezone.now()

        if sender_ip and controller.ip_address != sender_ip:
            controller.ip_address = sender_ip
            updated_fields.append("ip_address")

        if controller.status == Controller.Status.OFFLINE:
            controller.status = Controller.Status.ACTIVE
            updated_fields.append("status")

        controller.save(update_fields=updated_fields + ["updated_at"])
        return controller
