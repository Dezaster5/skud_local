from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.controllers.models import ControllerTask


TASK_OPERATION_MAP = {
    ControllerTask.TaskType.SET_ACTIVE: "set_active",
    ControllerTask.TaskType.OPEN_DOOR: "open_door",
    ControllerTask.TaskType.SET_DOOR_PARAMS: "set_door_params",
    ControllerTask.TaskType.ADD_WRISTBANDS: "add_cards",
    ControllerTask.TaskType.DEL_WRISTBANDS: "del_cards",
    ControllerTask.TaskType.CLEAR_CARDS: "clear_cards",
    ControllerTask.TaskType.SET_MODE: "set_mode",
    ControllerTask.TaskType.SET_TIMEZONE: "set_timezone",
    ControllerTask.TaskType.READ_CARDS: "read_cards",
    ControllerTask.TaskType.SYNC_WRISTBANDS: "sync_wristbands",
}


def build_success_response(
    *,
    operation: str,
    request_id: str | None,
    result: dict[str, Any],
    commands: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "operation": operation,
        "status": "ok",
        "server_time": timezone.now().isoformat(),
        "result": result,
        "commands": commands or [],
    }


def build_error_response(
    *,
    operation: str,
    request_id: str | None,
    error_code: str,
    error_message: str,
    commands: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "operation": operation,
        "status": "error",
        "server_time": timezone.now().isoformat(),
        "error": {
            "code": error_code,
            "message": error_message,
        },
        "commands": commands or [],
    }


def build_protocol_envelope_response(
    *,
    messages: list[dict[str, Any]],
    interval_seconds: int,
) -> dict[str, Any]:
    return {
        "date": timezone.localtime(timezone.now()).strftime("%Y-%m-%d %H:%M:%S"),
        "interval": interval_seconds,
        "messages": messages,
    }


def build_protocol_error_message(
    *,
    request_id: str | None,
    operation: str,
    error_code: str,
    error_message: str,
) -> dict[str, Any]:
    message: dict[str, Any] = {
        "operation": operation or "unknown",
        "success": 0,
        "error": {
            "code": error_code,
            "message": error_message,
        },
    }
    if request_id is not None:
        message["id"] = _normalize_identifier(request_id)
    return message


def build_protocol_check_access_message(*, request_id: str | None, granted: bool) -> dict[str, Any]:
    message: dict[str, Any] = {
        "operation": "check_access",
        "granted": 1 if granted else 0,
    }
    if request_id is not None:
        message["id"] = _normalize_identifier(request_id)
    return message


def build_protocol_set_active_message(
    *,
    request_id: str | None,
    active: bool,
    online: bool,
) -> dict[str, Any]:
    message: dict[str, Any] = {
        "operation": "set_active",
        "active": 1 if active else 0,
        "online": 1 if online else 0,
    }
    if request_id is not None:
        message["id"] = _normalize_identifier(request_id)
    return message


def build_protocol_events_message(*, request_id: str | None, events_success: int) -> dict[str, Any]:
    message: dict[str, Any] = {
        "operation": "events",
        "events_success": events_success,
    }
    if request_id is not None:
        message["id"] = _normalize_identifier(request_id)
    return message


def build_controller_commands(tasks: list[ControllerTask]) -> list[dict[str, Any]]:
    return [build_controller_command(task) for task in tasks]


def build_protocol_controller_messages(tasks: list[ControllerTask]) -> list[dict[str, Any]]:
    return [build_protocol_controller_message(task) for task in tasks]


def build_controller_command(task: ControllerTask) -> dict[str, Any]:
    payload_wrapper = dict(task.payload or {})
    protocol_payload = payload_wrapper.get("protocol")
    payload = dict(protocol_payload) if isinstance(protocol_payload, dict) else payload_wrapper
    command_name = TASK_OPERATION_MAP.get(task.task_type, task.task_type)
    payload.pop("command", None)
    payload.pop("meta", None)

    if task.task_type in {ControllerTask.TaskType.ADD_WRISTBANDS, ControllerTask.TaskType.DEL_WRISTBANDS}:
        payload["cards"] = _normalize_legacy_cards(payload.pop("wristbands", payload.get("cards", [])))

    return {
        "task_id": task.id,
        "command": command_name,
        **payload,
    }


def build_protocol_controller_message(task: ControllerTask) -> dict[str, Any]:
    payload_wrapper = dict(task.payload or {})
    protocol_payload = payload_wrapper.get("protocol")
    payload = dict(protocol_payload) if isinstance(protocol_payload, dict) else payload_wrapper
    operation = TASK_OPERATION_MAP.get(task.task_type, task.task_type)

    message: dict[str, Any] = {
        "id": task.id,
        "operation": operation,
    }

    if task.task_type == ControllerTask.TaskType.OPEN_DOOR:
        message["direction"] = payload.get("direction", 0)
        return message

    if task.task_type == ControllerTask.TaskType.SET_ACTIVE:
        message["active"] = payload.get("active", 1)
        message["online"] = payload.get("online", 1)
        return message

    if task.task_type == ControllerTask.TaskType.SET_MODE:
        message["mode"] = payload.get("mode", 0)
        return message

    if task.task_type == ControllerTask.TaskType.SET_DOOR_PARAMS:
        message["open"] = _normalize_int(payload.get("open"), default=0)
        message["open_control"] = _normalize_int(payload.get("open_control"), default=0)
        message["close_control"] = _normalize_int(payload.get("close_control"), default=0)
        return message

    if task.task_type == ControllerTask.TaskType.SET_TIMEZONE:
        timezone_payload = payload.get("timezone")
        if isinstance(timezone_payload, dict):
            message.update(timezone_payload)
        else:
            message.update(payload)
        return message

    if task.task_type in {ControllerTask.TaskType.ADD_WRISTBANDS, ControllerTask.TaskType.DEL_WRISTBANDS}:
        message["cards"] = _normalize_protocol_cards(
            payload.get("cards", payload.get("wristbands", [])),
            include_flags=task.task_type == ControllerTask.TaskType.ADD_WRISTBANDS,
        )
        return message

    if task.task_type == ControllerTask.TaskType.CLEAR_CARDS:
        return message

    if task.task_type == ControllerTask.TaskType.READ_CARDS:
        return message

    message.update(payload)
    return message


def _normalize_legacy_cards(raw_cards: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_cards, list):
        return []

    cards: list[dict[str, Any]] = []
    for raw_card in raw_cards:
        normalized_uid = _extract_uid(raw_card)
        if not normalized_uid:
            continue

        if isinstance(raw_card, dict):
            card_payload = dict(raw_card)
        else:
            card_payload = {}

        card_payload["uid"] = normalized_uid
        card_payload.pop("card_uid", None)
        card_payload.pop("card", None)
        cards.append(card_payload)

    return cards


def _normalize_protocol_cards(raw_cards: Any, *, include_flags: bool) -> list[dict[str, Any]]:
    if not isinstance(raw_cards, list):
        return []

    cards: list[dict[str, Any]] = []
    for raw_card in raw_cards:
        normalized_uid = _extract_uid(raw_card)
        if not normalized_uid:
            continue

        card_payload = {"card": normalized_uid}
        if include_flags:
            flags = 0
            timezone_bank = 255
            if isinstance(raw_card, dict):
                flags = _normalize_int(raw_card.get("flags"), default=0)
                timezone_bank = _normalize_int(
                    raw_card.get("tz", raw_card.get("timezone_bank")),
                    default=255,
                )
            card_payload["flags"] = flags
            card_payload["tz"] = timezone_bank
        cards.append(card_payload)

    return cards


def _extract_uid(raw_card: Any) -> str:
    if isinstance(raw_card, str):
        return raw_card.strip().upper()

    if not isinstance(raw_card, dict):
        return ""

    return str(
        raw_card.get("uid") or raw_card.get("card_uid") or raw_card.get("card") or ""
    ).strip().upper()


def _normalize_identifier(value: str) -> int | str:
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def _normalize_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
