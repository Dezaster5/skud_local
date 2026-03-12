from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.controllers.models import ControllerTask


TASK_COMMAND_MAP = {
    ControllerTask.TaskType.SET_ACTIVE: "set_active",
    ControllerTask.TaskType.OPEN_DOOR: "open_door",
    ControllerTask.TaskType.ADD_WRISTBANDS: "add_cards",
    ControllerTask.TaskType.DEL_WRISTBANDS: "del_cards",
    ControllerTask.TaskType.CLEAR_CARDS: "clear_cards",
    ControllerTask.TaskType.SET_MODE: "set_mode",
    ControllerTask.TaskType.SET_TIMEZONE: "set_timezone",
    ControllerTask.TaskType.READ_CARDS: "read_cards",
    # Legacy fallback if a planner task reaches the response builder directly.
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


def build_controller_commands(tasks: list[ControllerTask]) -> list[dict[str, Any]]:
    return [build_controller_command(task) for task in tasks]


def build_controller_command(task: ControllerTask) -> dict[str, Any]:
    payload_wrapper = dict(task.payload or {})
    protocol_payload = payload_wrapper.get("protocol")
    payload = dict(protocol_payload) if isinstance(protocol_payload, dict) else payload_wrapper
    command_name = TASK_COMMAND_MAP.get(task.task_type, task.task_type)
    payload.pop("command", None)
    payload.pop("meta", None)

    if task.task_type in {ControllerTask.TaskType.ADD_WRISTBANDS, ControllerTask.TaskType.DEL_WRISTBANDS}:
        payload["cards"] = _normalize_cards(payload.pop("wristbands", payload.get("cards", [])))

    return {
        "task_id": task.id,
        "command": command_name,
        **payload,
    }


def _normalize_cards(raw_cards: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_cards, list):
        return []

    cards: list[dict[str, Any]] = []
    for raw_card in raw_cards:
        if isinstance(raw_card, str):
            normalized_uid = raw_card.strip().upper()
            if normalized_uid:
                cards.append({"uid": normalized_uid})
            continue

        if not isinstance(raw_card, dict):
            continue

        normalized_uid = str(
            raw_card.get("uid") or raw_card.get("card_uid") or raw_card.get("card") or ""
        ).strip().upper()
        if not normalized_uid:
            continue

        card_payload = dict(raw_card)
        card_payload["uid"] = normalized_uid
        card_payload.pop("card_uid", None)
        card_payload.pop("card", None)
        cards.append(card_payload)

    return cards
