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
class WebJsonCommand:
    operation: str
    request_id: str | None
    controller_serial_number: str | None
    access_point_code: str | None
    device_port: int | None
    credential_uid: str | None
    auth_token: str | None
    events: tuple[IncomingControllerEvent, ...]
    task_acknowledgements: tuple[TaskAcknowledgement, ...]
    raw_payload: dict[str, Any]


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

    def parse(self, payload: dict[str, Any]) -> WebJsonCommand:
        controller_data = self._get_mapping(payload.get("controller"))
        credential_data = self._get_mapping(payload.get("credential"))

        operation = self._normalize_operation(
            self._first_value(
                payload.get("operation"),
                payload.get("event"),
                payload.get("command"),
                payload.get("cmd"),
            )
        )
        request_id = self._string_or_none(
            self._first_value(payload.get("request_id"), payload.get("requestId"), payload.get("id"))
        )
        controller_serial_number = self._string_or_none(
            self._first_value(
                controller_data.get("serial_number"),
                controller_data.get("serialNumber"),
                payload.get("controller_serial_number"),
                payload.get("serial_number"),
                payload.get("sn"),
            )
        )
        access_point_code = self._normalize_code(
            self._first_value(
                controller_data.get("access_point_code"),
                controller_data.get("accessPointCode"),
                payload.get("access_point_code"),
                payload.get("point"),
                payload.get("reader"),
            )
        )
        device_port = self._int_or_none(
            self._first_value(
                controller_data.get("device_port"),
                controller_data.get("devicePort"),
                payload.get("device_port"),
                payload.get("port"),
                payload.get("door"),
            )
        )
        credential_uid = self._normalize_uid(
            self._first_value(
                credential_data.get("uid"),
                credential_data.get("card_uid"),
                payload.get("uid"),
                payload.get("card"),
                payload.get("card_uid"),
            )
        )
        auth_token = self._string_or_none(
            self._first_value(
                payload.get("token"),
                payload.get("auth_token"),
                self._get_mapping(payload.get("meta")).get("token"),
            )
        )
        events = tuple(self._parse_events(payload))
        task_acknowledgements = tuple(self._parse_task_acknowledgements(payload))

        return WebJsonCommand(
            operation=operation,
            request_id=request_id,
            controller_serial_number=controller_serial_number,
            access_point_code=access_point_code,
            device_port=device_port,
            credential_uid=credential_uid,
            auth_token=auth_token,
            events=events,
            task_acknowledgements=task_acknowledgements,
            raw_payload=payload,
        )

    def _parse_events(self, payload: dict[str, Any]) -> list[IncomingControllerEvent]:
        raw_events = payload.get("events")
        if not isinstance(raw_events, list):
            return []

        parsed_events: list[IncomingControllerEvent] = []
        for raw_event in raw_events:
            event_data = self._get_mapping(raw_event)
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
                        )
                    ),
                    direction=self._normalize_direction(
                        self._first_value(event_data.get("direction"), event_data.get("dir"))
                    ),
                    reason_code=self._string_or_none(
                        self._first_value(event_data.get("reason_code"), event_data.get("event_code"))
                    )
                    or "",
                    message=self._string_or_none(
                        self._first_value(event_data.get("message"), event_data.get("description"))
                    )
                    or "Controller event received.",
                    access_point_code=self._normalize_code(
                        self._first_value(
                            event_data.get("access_point_code"),
                            event_data.get("point"),
                            payload.get("access_point_code"),
                        )
                    ),
                    device_port=self._int_or_none(
                        self._first_value(
                            event_data.get("device_port"),
                            event_data.get("port"),
                            payload.get("device_port"),
                        )
                    ),
                    raw_payload=event_data,
                )
            )

        return parsed_events

    def _parse_task_acknowledgements(self, payload: dict[str, Any]) -> list[TaskAcknowledgement]:
        acknowledgements_by_task_id: dict[int, TaskAcknowledgement] = {}

        for task_id in self._parse_integer_list(payload.get("completed_task_ids")):
            acknowledgements_by_task_id[task_id] = TaskAcknowledgement(
                task_id=task_id,
                status="done",
                error_message="",
                raw_payload={"task_id": task_id, "status": "done"},
            )

        raw_task_results = payload.get("task_results")
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

        raw_failed_tasks = payload.get("failed_tasks")
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
