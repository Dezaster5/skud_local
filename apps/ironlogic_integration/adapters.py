from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from django.utils import timezone
from django.utils.dateparse import parse_datetime


@dataclass(slots=True, frozen=True)
class IncomingControllerEvent:
    credential_uid: str | None
    occurred_at: datetime | None
    direction: str
    reason_code: str
    message: str
    access_point_code: str | None
    device_port: int | None
    raw_payload: dict[str, Any]


@dataclass(slots=True, frozen=True)
class TaskAcknowledgement:
    task_id: int
    status: str
    error_message: str
    raw_payload: dict[str, Any]


@dataclass(slots=True, frozen=True)
class WebJsonMessage:
    operation: str
    request_id: str | None
    access_point_code: str | None
    device_port: int | None
    credential_uid: str | None
    auth_token: str | None
    auth_hash: str | None
    events: tuple[IncomingControllerEvent, ...]
    task_acknowledgements: tuple[TaskAcknowledgement, ...]
    firmware_version: str | None
    connection_firmware_version: str | None
    controller_ip: str | None
    active_state: int | None
    mode: int | None
    raw_payload: dict[str, Any]


@dataclass(slots=True, frozen=True)
class WebJsonEnvelope:
    controller_serial_number: str | None
    controller_type: str | None
    auth_token: str | None
    messages: tuple[WebJsonMessage, ...]
    task_acknowledgements: tuple[TaskAcknowledgement, ...]
    raw_payload: dict[str, Any]
    uses_message_envelope: bool


class WebJsonAdapter:
    OPERATION_ALIASES = {
        "power_on": "power_on",
        "poweron": "power_on",
        "boot": "power_on",
        "ping": "ping",
        "check_access": "check_access",
        "checkaccess": "check_access",
        "access": "check_access",
        "events": "events",
        "event": "events",
    }

    def parse(self, payload: dict[str, Any]) -> WebJsonEnvelope:
        controller_data = self._get_mapping(payload.get("controller"))
        raw_messages = payload.get("messages")
        uses_message_envelope = isinstance(raw_messages, list)

        message_payloads = self._get_message_payloads(payload=payload, raw_messages=raw_messages)
        parsed_messages = tuple(
            self._parse_message(
                message_payload=message_payload,
                root_payload=payload,
                controller_data=controller_data,
                legacy_mode=not uses_message_envelope,
            )
            for message_payload in message_payloads
        )

        controller_serial_number = self._string_or_none(
            self._first_value(
                controller_data.get("serial_number"),
                controller_data.get("serialNumber"),
                payload.get("controller_serial_number"),
                payload.get("serial_number"),
                payload.get("sn"),
                parsed_messages[0].raw_payload.get("serial_number") if parsed_messages else None,
                parsed_messages[0].raw_payload.get("sn") if parsed_messages else None,
            )
        )
        auth_token = self._string_or_none(
            self._first_value(
                payload.get("token"),
                payload.get("auth_token"),
                self._get_mapping(payload.get("meta")).get("token"),
                payload.get("auth_hash"),
                parsed_messages[0].auth_token if parsed_messages else None,
            )
        )
        task_acknowledgements = tuple(
            acknowledgement
            for message in parsed_messages
            for acknowledgement in message.task_acknowledgements
        )

        return WebJsonEnvelope(
            controller_serial_number=controller_serial_number,
            controller_type=self._string_or_none(payload.get("type")),
            auth_token=auth_token,
            messages=parsed_messages,
            task_acknowledgements=task_acknowledgements,
            raw_payload=payload,
            uses_message_envelope=uses_message_envelope,
        )

    def _parse_message(
        self,
        *,
        message_payload: dict[str, Any],
        root_payload: dict[str, Any],
        controller_data: dict[str, Any],
        legacy_mode: bool,
    ) -> WebJsonMessage:
        credential_data = self._get_mapping(
            self._first_value(
                message_payload.get("credential"),
                root_payload.get("credential"),
            )
        )

        request_id = self._string_or_none(
            self._first_value(
                message_payload.get("request_id"),
                message_payload.get("requestId"),
                message_payload.get("id"),
                root_payload.get("request_id") if legacy_mode else None,
                root_payload.get("requestId") if legacy_mode else None,
                root_payload.get("id") if legacy_mode else None,
            )
        )
        operation = self._normalize_operation(
            self._first_value(
                message_payload.get("operation"),
                message_payload.get("event"),
                message_payload.get("command"),
                message_payload.get("cmd"),
                root_payload.get("operation") if legacy_mode else None,
                root_payload.get("event") if legacy_mode else None,
                root_payload.get("command") if legacy_mode else None,
                root_payload.get("cmd") if legacy_mode else None,
            )
        )
        access_point_code = self._normalize_code(
            self._first_value(
                controller_data.get("access_point_code"),
                controller_data.get("accessPointCode"),
                message_payload.get("access_point_code"),
                message_payload.get("accessPointCode"),
                message_payload.get("point"),
                root_payload.get("access_point_code") if legacy_mode else None,
                root_payload.get("point") if legacy_mode else None,
            )
        )
        device_port = self._int_or_none(
            self._first_value(
                controller_data.get("device_port"),
                controller_data.get("devicePort"),
                message_payload.get("device_port"),
                message_payload.get("devicePort"),
                message_payload.get("reader"),
                message_payload.get("port"),
                message_payload.get("door"),
                root_payload.get("device_port") if legacy_mode else None,
                root_payload.get("reader") if legacy_mode else None,
                root_payload.get("port") if legacy_mode else None,
                root_payload.get("door") if legacy_mode else None,
            )
        )
        credential_uid = self._normalize_uid(
            self._first_value(
                credential_data.get("uid"),
                credential_data.get("card_uid"),
                message_payload.get("uid"),
                message_payload.get("card"),
                message_payload.get("card_uid"),
                root_payload.get("uid") if legacy_mode else None,
                root_payload.get("card") if legacy_mode else None,
                root_payload.get("card_uid") if legacy_mode else None,
            )
        )
        auth_token = self._string_or_none(
            self._first_value(
                message_payload.get("token"),
                message_payload.get("auth_token"),
                message_payload.get("auth_hash"),
                root_payload.get("token") if legacy_mode else None,
                root_payload.get("auth_token") if legacy_mode else None,
                root_payload.get("auth_hash") if legacy_mode else None,
                self._get_mapping(root_payload.get("meta")).get("token") if legacy_mode else None,
            )
        )
        auth_hash = self._string_or_none(
            self._first_value(
                message_payload.get("auth_hash"),
                root_payload.get("auth_hash") if legacy_mode else None,
            )
        )
        events = tuple(
            self._parse_events(
                events_payload=self._first_value(
                    message_payload.get("events"),
                    root_payload.get("events") if legacy_mode else None,
                ),
                message_payload=message_payload,
                root_payload=root_payload,
            )
        )
        task_acknowledgements = tuple(
            self._parse_task_acknowledgements(
                message_payload=message_payload,
                root_payload=root_payload,
                request_id=request_id,
                operation=operation,
                legacy_mode=legacy_mode,
            )
        )

        return WebJsonMessage(
            operation=operation,
            request_id=request_id,
            access_point_code=access_point_code,
            device_port=device_port,
            credential_uid=credential_uid,
            auth_token=auth_token,
            auth_hash=auth_hash,
            events=events,
            task_acknowledgements=task_acknowledgements,
            firmware_version=self._string_or_none(message_payload.get("fw")),
            connection_firmware_version=self._string_or_none(message_payload.get("conn_fw")),
            controller_ip=self._string_or_none(message_payload.get("controller_ip")),
            active_state=self._int_or_none(message_payload.get("active")),
            mode=self._int_or_none(message_payload.get("mode")),
            raw_payload=message_payload,
        )

    def _parse_events(
        self,
        *,
        events_payload: Any,
        message_payload: dict[str, Any],
        root_payload: dict[str, Any],
    ) -> list[IncomingControllerEvent]:
        if not isinstance(events_payload, list):
            return []

        parsed_events: list[IncomingControllerEvent] = []
        for raw_event in events_payload:
            event_data = self._get_mapping(raw_event)
            raw_event_code = self._first_value(
                event_data.get("event"),
                event_data.get("event_code"),
                event_data.get("reason_code"),
            )
            reason_code = self._string_or_none(raw_event_code)
            if reason_code and reason_code.isdigit():
                reason_code = f"controller_event_{reason_code}"

            event_message = self._string_or_none(
                self._first_value(
                    event_data.get("message"),
                    event_data.get("description"),
                )
            )
            if event_message is None and raw_event_code is not None:
                event_message = f"Controller event code {raw_event_code} received."

            parsed_events.append(
                IncomingControllerEvent(
                    credential_uid=self._normalize_uid(
                        self._first_value(
                            event_data.get("uid"),
                            event_data.get("card"),
                            event_data.get("card_uid"),
                        )
                    ),
                    occurred_at=self._parse_occurred_at(
                        self._first_value(
                            event_data.get("occurred_at"),
                            event_data.get("occurredAt"),
                            event_data.get("timestamp"),
                            event_data.get("time"),
                        )
                    ),
                    direction=self._normalize_direction(
                        self._first_value(
                            event_data.get("direction"),
                            event_data.get("dir"),
                        )
                    ),
                    reason_code=reason_code or "controller_event",
                    message=event_message or "Controller event received.",
                    access_point_code=self._normalize_code(
                        self._first_value(
                            event_data.get("access_point_code"),
                            event_data.get("point"),
                            message_payload.get("access_point_code"),
                            root_payload.get("access_point_code"),
                        )
                    ),
                    device_port=self._int_or_none(
                        self._first_value(
                            event_data.get("device_port"),
                            event_data.get("reader"),
                            event_data.get("port"),
                            message_payload.get("device_port"),
                            message_payload.get("reader"),
                            root_payload.get("device_port"),
                            root_payload.get("reader"),
                        )
                    ),
                    raw_payload=event_data,
                )
            )

        return parsed_events

    def _parse_task_acknowledgements(
        self,
        *,
        message_payload: dict[str, Any],
        root_payload: dict[str, Any],
        request_id: str | None,
        operation: str,
        legacy_mode: bool,
    ) -> list[TaskAcknowledgement]:
        acknowledgements_by_task_id: dict[int, TaskAcknowledgement] = {}

        if "success" in message_payload and request_id is not None:
            task_id = self._int_or_none(request_id)
            success_value = self._int_or_none(message_payload.get("success"))
            if task_id is not None and success_value is not None:
                acknowledgements_by_task_id[task_id] = TaskAcknowledgement(
                    task_id=task_id,
                    status="done" if success_value else "failed",
                    error_message=""
                    if success_value
                    else (
                        self._string_or_none(
                            self._first_value(
                                message_payload.get("error_message"),
                                message_payload.get("error"),
                                message_payload.get("message"),
                            )
                        )
                        or "Controller reported task failure."
                    ),
                    raw_payload=message_payload,
                )

        if not operation and "cards" in message_payload and request_id is not None:
            task_id = self._int_or_none(request_id)
            if task_id is not None:
                acknowledgements_by_task_id[task_id] = TaskAcknowledgement(
                    task_id=task_id,
                    status="done",
                    error_message="",
                    raw_payload=message_payload,
                )

        sources = [message_payload]
        if legacy_mode:
            sources.append(root_payload)

        for source in sources:
            for task_id in self._parse_integer_list(source.get("completed_task_ids")):
                acknowledgements_by_task_id[task_id] = TaskAcknowledgement(
                    task_id=task_id,
                    status="done",
                    error_message="",
                    raw_payload={"task_id": task_id, "status": "done"},
                )

            raw_task_results = source.get("task_results")
            if isinstance(raw_task_results, list):
                for raw_task_result in raw_task_results:
                    task_result_data = self._get_mapping(raw_task_result)
                    task_id = self._int_or_none(
                        self._first_value(
                            task_result_data.get("task_id"),
                            task_result_data.get("taskId"),
                            task_result_data.get("id"),
                        )
                    )
                    status = self._normalize_task_status(
                        self._first_value(
                            task_result_data.get("status"),
                            task_result_data.get("result"),
                        )
                    )
                    if task_id is None or status is None:
                        continue

                    acknowledgements_by_task_id[task_id] = TaskAcknowledgement(
                        task_id=task_id,
                        status=status,
                        error_message=self._string_or_none(
                            self._first_value(
                                task_result_data.get("error_message"),
                                task_result_data.get("error"),
                                task_result_data.get("message"),
                            )
                        )
                        or "",
                        raw_payload=task_result_data,
                    )

            raw_failed_tasks = source.get("failed_tasks")
            if isinstance(raw_failed_tasks, list):
                for raw_failed_task in raw_failed_tasks:
                    failed_task_data = self._get_mapping(raw_failed_task)
                    task_id = self._int_or_none(
                        self._first_value(
                            failed_task_data.get("task_id"),
                            failed_task_data.get("taskId"),
                            failed_task_data.get("id"),
                            raw_failed_task if not isinstance(raw_failed_task, dict) else None,
                        )
                    )
                    if task_id is None:
                        continue

                    acknowledgements_by_task_id[task_id] = TaskAcknowledgement(
                        task_id=task_id,
                        status="failed",
                        error_message=self._string_or_none(
                            self._first_value(
                                failed_task_data.get("error_message"),
                                failed_task_data.get("error"),
                                failed_task_data.get("message"),
                            )
                        )
                        or "Controller reported task failure.",
                        raw_payload=failed_task_data or {"task_id": task_id, "status": "failed"},
                    )

        return list(acknowledgements_by_task_id.values())

    @staticmethod
    def _get_message_payloads(*, payload: dict[str, Any], raw_messages: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_messages, list):
            return [payload]

        parsed_messages = [raw_message for raw_message in raw_messages if isinstance(raw_message, dict)]
        if parsed_messages:
            return parsed_messages
        return []

    @classmethod
    def _normalize_operation(cls, value: Any) -> str:
        normalized = cls._string_or_none(value)
        if normalized is None:
            return ""
        normalized = normalized.strip().lower().replace("-", "_").replace(" ", "_")
        return cls.OPERATION_ALIASES.get(normalized, normalized)

    @staticmethod
    def _normalize_uid(value: Any) -> str | None:
        normalized = WebJsonAdapter._string_or_none(value)
        if normalized is None:
            return None
        normalized = normalized.strip().upper()
        return normalized or None

    @staticmethod
    def _normalize_code(value: Any) -> str | None:
        normalized = WebJsonAdapter._string_or_none(value)
        if normalized is None:
            return None
        normalized = normalized.strip().lower()
        return normalized or None

    @staticmethod
    def _normalize_direction(value: Any) -> str:
        normalized = WebJsonAdapter._string_or_none(value)
        if normalized is None:
            return "unknown"

        normalized = normalized.strip().lower()
        if normalized in {"in", "entry", "enter"}:
            return "entry"
        if normalized in {"out", "exit", "leave"}:
            return "exit"
        return "unknown"

    @staticmethod
    def _normalize_task_status(value: Any) -> str | None:
        normalized = WebJsonAdapter._string_or_none(value)
        if normalized is None:
            return None

        normalized = normalized.strip().lower()
        if normalized in {"done", "ok", "success", "completed"}:
            return "done"
        if normalized in {"failed", "error", "rejected"}:
            return "failed"
        return None

    @staticmethod
    def _parse_occurred_at(value: Any) -> datetime | None:
        if value is None:
            return None

        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=UTC)

        if isinstance(value, str):
            parsed_value = parse_datetime(value)
            if parsed_value is None:
                try:
                    parsed_value = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    return None
            if timezone.is_naive(parsed_value):
                return timezone.make_aware(parsed_value, timezone.get_current_timezone())
            return parsed_value

        return None

    @staticmethod
    def _int_or_none(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_integer_list(value: Any) -> list[int]:
        if not isinstance(value, list):
            return []

        parsed_values: list[int] = []
        for item in value:
            parsed_item = WebJsonAdapter._int_or_none(item)
            if parsed_item is not None:
                parsed_values.append(parsed_item)
        return parsed_values

    @staticmethod
    def _string_or_none(value: Any) -> str | None:
        if value is None:
            return None
        value_as_text = str(value).strip()
        return value_as_text or None

    @staticmethod
    def _first_value(*values: Any) -> Any:
        for value in values:
            if value not in (None, ""):
                return value
        return None

    @staticmethod
    def _get_mapping(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        return {}
