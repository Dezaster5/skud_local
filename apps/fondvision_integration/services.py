from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime
from ipaddress import ip_address
from typing import Any

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from apps.controllers.models import Controller, Reader
from apps.controllers.services import ControllerTaskService
from apps.events.models import AccessEvent
from apps.fondvision_integration.models import FondvisionRequestLog
from apps.wristbands.models import Wristband
from apps.wristbands.selectors import get_wristband_by_uid


@dataclass(slots=True, frozen=True)
class FondvisionIngressResult:
    response_text: str
    access_event_id: int
    request_log_id: int


@dataclass(slots=True, frozen=True)
class CardIdResolution:
    raw_cardid: str | None
    effective_cardid: str | None
    decoded_cardid: str | None = None
    invalid_qr: bool = False


class FondvisionIngressService:
    def __init__(
        self,
        *,
        task_service: ControllerTaskService | None = None,
    ) -> None:
        self.task_service = task_service or ControllerTaskService()

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
        card_resolution = self._resolve_cardid(raw_query_params.get("cardid"))
        cardid = self._normalize_upper_scalar(card_resolution.effective_cardid)
        cjihao = self._normalize_upper_scalar(raw_query_params.get("cjihao"))
        mjihao = self._normalize_scalar(raw_query_params.get("mjihao"))
        status = self._normalize_scalar(raw_query_params.get("status"))
        device_time_raw = self._normalize_scalar(raw_query_params.get("time"))
        device_time = self._parse_device_time(device_time_raw)
        reported_reader_ip = self._normalize_ip(raw_query_params.get("ip"))

        reader = self._resolve_reader(
            cjihao=cjihao,
            mjihao=mjihao,
            sender_ip=sender_ip,
            reported_reader_ip=reported_reader_ip,
        )
        controller = reader.controller if reader else None
        wristband = get_wristband_by_uid(cardid or "") if cardid else None

        raw_payload = {
            "path": request_path,
            "query_string": query_string,
            "query_params": raw_query_params,
            "sender_ip": sender_ip,
            "reported_reader_ip": reported_reader_ip,
            "reader_id": reader.id if reader else None,
            "reader_name": reader.name if reader else "",
            "reader_ip": reader.ip_address if reader else "",
            "raw_cardid": card_resolution.raw_cardid or "",
            "decoded_cardid": card_resolution.decoded_cardid or "",
            "invalid_qr": card_resolution.invalid_qr,
        }
        occurred_at = device_time or timezone.now()
        access_event = self._ingest_access_event(
            reader=reader,
            controller=controller,
            wristband=wristband,
            cardid=cardid,
            raw_cardid=card_resolution.raw_cardid,
            invalid_qr=card_resolution.invalid_qr,
            occurred_at=occurred_at,
            raw_payload=raw_payload,
            status=status,
        )

        request_log = FondvisionRequestLog.objects.create(
            controller=controller,
            reader=reader,
            wristband=wristband,
            access_event=access_event,
            sender_ip=sender_ip,
            request_path=request_path,
            query_string=query_string,
            request_body=request_body,
            raw_query_params=raw_query_params,
            cardid=cardid or card_resolution.raw_cardid or "",
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

    def _ingest_access_event(
        self,
        *,
        reader: Reader | None,
        controller: Controller | None,
        wristband: Wristband | None,
        cardid: str | None,
        raw_cardid: str | None,
        invalid_qr: bool,
        occurred_at: datetime,
        raw_payload: dict[str, object],
        status: str | None,
    ) -> AccessEvent:
        if reader is None:
            return self._create_event(
                controller=controller,
                wristband=wristband,
                credential_uid=cardid or "",
                event_type=AccessEvent.EventType.ACCESS_DENIED,
                decision=AccessEvent.Decision.DENIED,
                direction=AccessEvent.Direction.UNKNOWN,
                reason_code="fondvision_reader_not_configured",
                message="Fondvision request received from an unknown reader.",
                occurred_at=occurred_at,
                raw_payload=raw_payload,
            )

        if invalid_qr:
            return self._create_event(
                controller=controller,
                wristband=None,
                credential_uid=raw_cardid or "",
                event_type=AccessEvent.EventType.ACCESS_DENIED,
                decision=AccessEvent.Decision.DENIED,
                direction=self._get_event_direction(reader),
                reason_code="invalid_qr_code",
                message="QR code is invalid, scan another wristband.",
                occurred_at=occurred_at,
                raw_payload=raw_payload,
            )

        if not cardid or wristband is None:
            return self._create_event(
                controller=controller,
                wristband=None,
                credential_uid=cardid or raw_cardid or "",
                event_type=AccessEvent.EventType.ACCESS_DENIED,
                decision=AccessEvent.Decision.DENIED,
                direction=self._get_event_direction(reader),
                reason_code="wristband_not_found",
                message="Card ID was not found in the local SKUD database.",
                occurred_at=occurred_at,
                raw_payload=raw_payload,
            )

        wristband_denial = self._get_wristband_denial(wristband=wristband, occurred_at=occurred_at)
        if wristband_denial is not None:
            reason_code, message = wristband_denial
            return self._create_event(
                controller=controller,
                wristband=wristband,
                credential_uid=cardid,
                event_type=AccessEvent.EventType.ACCESS_DENIED,
                decision=AccessEvent.Decision.DENIED,
                direction=self._get_event_direction(reader),
                reason_code=reason_code,
                message=message,
                occurred_at=occurred_at,
                raw_payload=raw_payload,
            )

        controller_task = self.task_service.enqueue_open_door(
            controller=controller,
            direction=self._get_controller_direction(reader),
            requested_by="fondvision",
            source="fondvision_qr_scan",
            reader_id=reader.id,
            reader_name=reader.name,
            wristband_id=wristband.id,
            credential_uid=cardid,
            raw_cardid=raw_cardid or "",
        )
        self._update_wristband_state(
            wristband=wristband,
            reader=reader,
            occurred_at=occurred_at,
        )
        return self._create_event(
            controller=controller,
            wristband=wristband,
            credential_uid=cardid,
            event_type=AccessEvent.EventType.ACCESS_GRANTED,
            decision=AccessEvent.Decision.GRANTED,
            direction=self._get_event_direction(reader),
            reason_code="access_granted",
            message="Fondvision access granted. Open door task queued.",
            occurred_at=occurred_at,
            raw_payload={
                **raw_payload,
                "status": status,
                "controller_task_id": controller_task.id,
                "controller_task_status": controller_task.status,
                "controller_task_payload": controller_task.payload,
            },
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

    def _resolve_cardid(self, value: object) -> CardIdResolution:
        raw_cardid = self._normalize_scalar(value)
        if not raw_cardid:
            return CardIdResolution(raw_cardid=None, effective_cardid=None)

        decoded_cardid = self._decrypt_qr20(raw_cardid)
        if decoded_cardid is None:
            return CardIdResolution(
                raw_cardid=raw_cardid,
                effective_cardid=raw_cardid,
            )

        normalized_decoded_cardid = decoded_cardid.strip()
        if self._is_valid_decrypted_qr(normalized_decoded_cardid):
            return CardIdResolution(
                raw_cardid=raw_cardid,
                effective_cardid=normalized_decoded_cardid,
                decoded_cardid=normalized_decoded_cardid,
            )

        return CardIdResolution(
            raw_cardid=raw_cardid,
            effective_cardid=None,
            decoded_cardid=normalized_decoded_cardid,
            invalid_qr=True,
        )

    @staticmethod
    def _normalize_ip(value: object) -> str | None:
        normalized = FondvisionIngressService._normalize_scalar(value)
        if not normalized:
            return None

        try:
            ip_address(normalized)
            return normalized
        except ValueError:
            return None

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
    def _is_probably_encrypted_qr(value: str) -> bool:
        if len(value) != 20:
            return False

        allowed_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        return all(char in allowed_chars for char in value)

    def _decrypt_qr20(self, value: str) -> str | None:
        if not self._is_probably_encrypted_qr(value):
            return None

        try:
            padded_value = value + "=" * ((4 - len(value) % 4) % 4)
            ciphertext = base64.urlsafe_b64decode(padded_value.encode("ascii"))
            key = hashlib.sha256(settings.FONDVISION_QR_PASSWORD.encode("utf-8")).digest()
            nonce = hashlib.sha256(f"{settings.FONDVISION_QR_PASSWORD}|nonce".encode("utf-8")).digest()[:16]
            cipher = Cipher(algorithms.AES(key), modes.CTR(nonce))
            decryptor = cipher.decryptor()
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            decoded_value = plaintext.decode("utf-8")
            return decoded_value.rstrip("\x00")
        except Exception:
            return None

    def _is_valid_decrypted_qr(self, value: str) -> bool:
        body = value.strip()
        if len(body) > 50:
            return False

        dot_position = body.find(".")
        if dot_position < 0:
            return False

        if "A" not in body[:dot_position]:
            return False

        if timezone.localdate() > self._get_qr_b_suffix_required_from():
            if "B" not in body[dot_position + 1 :]:
                return False

        digits_only = body.replace("A", "").replace("B", "").replace(".", "")
        return all(char in "1234567890" for char in digits_only)

    @staticmethod
    def _get_qr_b_suffix_required_from() -> date:
        raw_value = settings.FONDVISION_QR_B_SUFFIX_REQUIRED_FROM
        try:
            return date.fromisoformat(raw_value)
        except ValueError:
            return date(2026, 4, 10)

    @staticmethod
    def _get_reader_by_ip(*, reader_ip: str | None) -> Reader | None:
        if not reader_ip:
            return None

        return (
            Reader.objects.select_related("controller")
            .filter(ip_address=reader_ip, status=Reader.Status.ACTIVE)
            .order_by("id")
            .first()
        )

    @staticmethod
    def _get_reader_by_external_id(*, external_id: str | None) -> Reader | None:
        if not external_id:
            return None

        return (
            Reader.objects.select_related("controller")
            .filter(external_id=external_id, status=Reader.Status.ACTIVE)
            .order_by("id")
            .first()
        )

    @staticmethod
    def _get_reader_by_controller_and_number(
        *,
        controller_serial_number: str | None,
        device_number: str | None,
    ) -> Reader | None:
        if not controller_serial_number or not device_number:
            return None

        try:
            normalized_device_number = int(device_number)
        except (TypeError, ValueError):
            return None

        return (
            Reader.objects.select_related("controller")
            .filter(
                controller__serial_number=controller_serial_number,
                device_number=normalized_device_number,
                status=Reader.Status.ACTIVE,
            )
            .order_by("id")
            .first()
        )

    def _resolve_reader(
        self,
        *,
        cjihao: str | None,
        mjihao: str | None,
        sender_ip: str | None,
        reported_reader_ip: str | None,
    ) -> Reader | None:
        for candidate_ip in (reported_reader_ip, sender_ip):
            reader = self._get_reader_by_ip(reader_ip=candidate_ip)
            if reader is not None:
                return reader

        reader = self._get_reader_by_external_id(external_id=cjihao)
        if reader is not None:
            return reader

        return self._get_reader_by_controller_and_number(
            controller_serial_number=cjihao,
            device_number=mjihao,
        )

    @staticmethod
    def _get_wristband_denial(
        *,
        wristband: Wristband,
        occurred_at: datetime,
    ) -> tuple[str, str] | None:
        if wristband.status == Wristband.Status.BLOCKED:
            return "wristband_blocked", "Wristband is blocked."
        if wristband.status == Wristband.Status.LOST:
            return "wristband_lost", "Wristband is marked as lost."
        if wristband.status == Wristband.Status.RETIRED:
            return "wristband_retired", "Wristband is retired."
        if wristband.expires_at and occurred_at > wristband.expires_at:
            return "wristband_expired", "Wristband is expired."
        return None

    @staticmethod
    def _get_controller_direction(reader: Reader) -> int:
        if reader.direction == Reader.Direction.EXIT:
            return 1
        return 0

    @staticmethod
    def _get_event_direction(reader: Reader) -> str:
        if reader.direction == Reader.Direction.EXIT:
            return AccessEvent.Direction.EXIT
        return AccessEvent.Direction.ENTRY

    @staticmethod
    def _update_wristband_state(
        *,
        wristband: Wristband,
        reader: Reader,
        occurred_at: datetime,
    ) -> None:
        updated_fields = ["last_seen_at", "updated_at"]
        wristband.last_seen_at = occurred_at

        if reader.direction == Reader.Direction.ENTRY:
            new_presence_state = Wristband.PresenceState.INSIDE
        else:
            new_presence_state = Wristband.PresenceState.OUTSIDE

        if wristband.presence_state != new_presence_state:
            wristband.presence_state = new_presence_state
            updated_fields.append("presence_state")

        wristband.save(update_fields=updated_fields)

    @staticmethod
    def _create_event(
        *,
        controller: Controller | None,
        wristband: Wristband | None,
        credential_uid: str,
        event_type: str,
        decision: str,
        direction: str,
        reason_code: str,
        message: str,
        occurred_at: datetime,
        raw_payload: dict[str, object],
    ) -> AccessEvent:
        return AccessEvent.objects.create(
            controller=controller,
            wristband=wristband,
            credential_uid=credential_uid,
            event_type=event_type,
            direction=direction,
            decision=decision,
            reason_code=reason_code,
            message=message,
            occurred_at=occurred_at,
            raw_payload=raw_payload,
        )
