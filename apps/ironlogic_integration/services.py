from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from django.conf import settings
from django.utils import timezone

from apps.access.models import AccessPoint
from apps.access.selectors import get_active_access_point_for_controller
from apps.access.services import AccessDecision, AccessDecisionService
from apps.controllers.models import Controller
from apps.controllers.selectors import get_controller_by_serial_number
from apps.controllers.services import ControllerTaskBatchService, ControllerTaskService
from apps.events.models import AccessEvent
from apps.events.services import EventLoggingService
from apps.ironlogic_integration.adapters import (
    IncomingControllerEvent,
    TaskAcknowledgement,
    WebJsonAdapter,
    WebJsonCommand,
)
from apps.ironlogic_integration.models import WebJsonRequestLog
from apps.ironlogic_integration.response_builders import build_error_response, build_success_response


@dataclass(slots=True, frozen=True)
class WebJsonResponse:
    payload: dict[str, Any]
    http_status: int


class IronLogicWebJsonService:
    def __init__(
        self,
        *,
        adapter: WebJsonAdapter | None = None,
        access_decision_service: AccessDecisionService | None = None,
        controller_task_service: ControllerTaskService | None = None,
        controller_task_batch_service: ControllerTaskBatchService | None = None,
        event_logging_service: EventLoggingService | None = None,
    ) -> None:
        self.adapter = adapter or WebJsonAdapter()
        self.access_decision_service = access_decision_service or AccessDecisionService()
        self.controller_task_service = controller_task_service or ControllerTaskService()
        self.controller_task_batch_service = controller_task_batch_service or ControllerTaskBatchService(
            task_service=self.controller_task_service
        )
        self.event_logging_service = event_logging_service or EventLoggingService()

    def handle(
        self,
        *,
        payload: dict[str, Any] | None,
        raw_body: str,
        headers: Mapping[str, str],
        remote_addr: str | None,
    ) -> WebJsonResponse:
        source_ip = self._extract_source_ip(headers=headers, remote_addr=remote_addr)

        if payload is None or not isinstance(payload, dict):
            response_payload = build_error_response(
                operation="unknown",
                request_id=None,
                error_code="invalid_json",
                error_message="Request body is not valid JSON.",
            )
            self._create_request_log(
                controller=None,
                request_id="",
                operation="unknown",
                source_ip=source_ip,
                processing_status=WebJsonRequestLog.ProcessingStatus.INVALID_PAYLOAD,
                http_status=400,
                token_present=False,
                request_body=raw_body,
                request_payload={},
                response_payload=response_payload,
                error_message="Request body is not valid JSON.",
            )
            return WebJsonResponse(payload=response_payload, http_status=400)

        command = self.adapter.parse(payload)
        controller = self._resolve_controller(command)
        request_log = self._create_request_log(
            controller=controller,
            request_id=command.request_id or "",
            operation=command.operation,
            source_ip=source_ip,
            processing_status=WebJsonRequestLog.ProcessingStatus.PROCESSED,
            http_status=200,
            token_present=bool(self._extract_auth_token(headers=headers, command=command)),
            request_body=raw_body,
            request_payload=payload,
            response_payload={},
            error_message="",
        )

        security_error = self._validate_security(headers=headers, source_ip=source_ip, command=command)
        if security_error is not None:
            response_payload = build_error_response(
                operation=command.operation or "unknown",
                request_id=command.request_id,
                error_code="unauthorized",
                error_message=security_error,
            )
            self._finalize_request_log(
                request_log=request_log,
                processing_status=WebJsonRequestLog.ProcessingStatus.REJECTED,
                http_status=403,
                response_payload=response_payload,
                error_message=security_error,
            )
            return WebJsonResponse(payload=response_payload, http_status=403)

        if command.operation not in {"power_on", "ping", "check_access", "events"}:
            response_payload = build_error_response(
                operation=command.operation or "unknown",
                request_id=command.request_id,
                error_code="unknown_operation",
                error_message="Operation is not supported by this endpoint.",
            )
            self._finalize_request_log(
                request_log=request_log,
                processing_status=WebJsonRequestLog.ProcessingStatus.UNKNOWN_OPERATION,
                http_status=200,
                response_payload=response_payload,
                error_message="Operation is not supported by this endpoint.",
            )
            return WebJsonResponse(payload=response_payload, http_status=200)

        if controller is None:
            response_payload = build_error_response(
                operation=command.operation,
                request_id=command.request_id,
                error_code="controller_not_found",
                error_message="Controller was not found by serial number.",
            )
            self._finalize_request_log(
                request_log=request_log,
                processing_status=WebJsonRequestLog.ProcessingStatus.CONTROLLER_NOT_FOUND,
                http_status=200,
                response_payload=response_payload,
                error_message="Controller was not found by serial number.",
            )
            return WebJsonResponse(payload=response_payload, http_status=200)

        self._process_task_acknowledgements(controller=controller, command=command)
        if controller.status == Controller.Status.DISABLED:
            response_payload = build_error_response(
                operation=command.operation,
                request_id=command.request_id,
                error_code="controller_disabled",
                error_message="Controller is disabled.",
            )
            self._finalize_request_log(
                request_log=request_log,
                processing_status=WebJsonRequestLog.ProcessingStatus.CONTROLLER_INACTIVE,
                http_status=200,
                response_payload=response_payload,
                error_message="Controller is disabled.",
            )
            return WebJsonResponse(payload=response_payload, http_status=200)

        self._mark_controller_seen(controller)
        response = self._dispatch(command=command, controller=controller)
        processing_status = self._select_processing_status(command=command, response_payload=response.payload)
        error_message = self._extract_error_message(response.payload)
        self._finalize_request_log(
            request_log=request_log,
            processing_status=processing_status,
            http_status=response.http_status,
            response_payload=response.payload,
            error_message=error_message,
        )
        return response

    def _dispatch(self, *, command: WebJsonCommand, controller: Controller) -> WebJsonResponse:
        if command.operation == "power_on":
            self.event_logging_service.log_controller_event(
                controller=controller,
                message="Controller power_on received.",
                reason_code="power_on",
                raw_payload=command.raw_payload,
            )
            return WebJsonResponse(
                payload=build_success_response(
                    operation=command.operation,
                    request_id=command.request_id,
                    result={"ack": "power_on_received", "controller_id": controller.id},
                    commands=self._build_pending_commands(controller),
                ),
                http_status=200,
            )

        if command.operation == "ping":
            return WebJsonResponse(
                payload=build_success_response(
                    operation=command.operation,
                    request_id=command.request_id,
                    result={"ack": "pong", "controller_id": controller.id},
                    commands=self._build_pending_commands(controller),
                ),
                http_status=200,
            )

        if command.operation == "check_access":
            access_point = self._resolve_access_point(command=command, controller=controller)
            if access_point is None:
                self.event_logging_service.log_controller_event(
                    controller=controller,
                    message="Access point could not be resolved for access check.",
                    reason_code="access_point_not_found",
                    credential_uid=command.credential_uid or "",
                    raw_payload=command.raw_payload,
                )
                decision = AccessDecision(
                    granted=False,
                    reason_code="access_point_not_found",
                    reason_message="Access point could not be resolved for access check.",
                    person_id=None,
                    wristband_id=None,
                )
                return WebJsonResponse(
                    payload=build_success_response(
                        operation=command.operation,
                        request_id=command.request_id,
                        result=self._decision_to_result(decision),
                        commands=self._build_pending_commands(controller),
                    ),
                    http_status=200,
                )

            decision = self.access_decision_service.decide(
                uid=command.credential_uid or "",
                access_point=access_point,
            )
            self.event_logging_service.log_access_decision(
                decision=decision,
                access_point=access_point,
                credential_uid=command.credential_uid or "",
                controller=controller,
                raw_payload=command.raw_payload,
            )
            return WebJsonResponse(
                payload=build_success_response(
                    operation=command.operation,
                    request_id=command.request_id,
                    result=self._decision_to_result(decision),
                    commands=self._build_pending_commands(controller),
                ),
                http_status=200,
            )

        accepted_events = 0
        access_point_cache: dict[tuple[str | None, int | None], AccessPoint | None] = {}
        for incoming_event in command.events:
            cache_key = (incoming_event.access_point_code or command.access_point_code, incoming_event.device_port or command.device_port)
            access_point = access_point_cache.get(cache_key)
            if cache_key not in access_point_cache:
                access_point = self._resolve_access_point(
                    command=command,
                    controller=controller,
                    access_point_code=incoming_event.access_point_code,
                    device_port=incoming_event.device_port,
                )
                access_point_cache[cache_key] = access_point

            self._log_incoming_event(
                controller=controller,
                incoming_event=incoming_event,
                access_point=access_point,
            )
            accepted_events += 1

        return WebJsonResponse(
            payload=build_success_response(
                operation=command.operation,
                request_id=command.request_id,
                result={"accepted_events": accepted_events},
                commands=self._build_pending_commands(controller),
            ),
            http_status=200,
        )

    def _resolve_controller(self, command: WebJsonCommand) -> Controller | None:
        if not command.controller_serial_number:
            return None
        return get_controller_by_serial_number(command.controller_serial_number)

    def _resolve_access_point(
        self,
        *,
        command: WebJsonCommand,
        controller: Controller,
        access_point_code: str | None = None,
        device_port: int | None = None,
    ) -> AccessPoint | None:
        effective_code = access_point_code or command.access_point_code
        effective_port = device_port if device_port is not None else command.device_port
        return get_active_access_point_for_controller(
            controller_id=controller.id,
            access_point_code=effective_code,
            device_port=effective_port,
        )

    def _build_pending_commands(self, controller: Controller) -> list[dict[str, Any]]:
        batch = self.controller_task_batch_service.dispatch_pending_batch(
            controller=controller,
            max_commands=settings.IRONLOGIC_TASK_BATCH_SIZE,
            max_payload_bytes=settings.IRONLOGIC_TASK_BATCH_MAX_BYTES,
        )
        return batch.commands

    def _log_incoming_event(
        self,
        *,
        controller: Controller,
        incoming_event: IncomingControllerEvent,
        access_point: AccessPoint | None,
    ) -> None:
        self.event_logging_service.log_controller_event(
            controller=controller,
            access_point=access_point,
            credential_uid=incoming_event.credential_uid or "",
            occurred_at=incoming_event.occurred_at,
            direction=self._map_direction_to_event(incoming_event.direction),
            reason_code=incoming_event.reason_code,
            message=incoming_event.message,
            raw_payload=incoming_event.raw_payload,
        )

    def _process_task_acknowledgements(
        self,
        *,
        controller: Controller,
        command: WebJsonCommand,
    ) -> None:
        done_task_ids: list[int] = []
        failed_tasks: dict[int, str] = {}

        for acknowledgement in command.task_acknowledgements:
            self._accumulate_task_acknowledgement(
                acknowledgement=acknowledgement,
                done_task_ids=done_task_ids,
                failed_tasks=failed_tasks,
            )

        if done_task_ids:
            self.controller_task_service.mark_tasks_as_done(
                controller=controller,
                task_ids=done_task_ids,
            )

        if failed_tasks:
            self.controller_task_service.mark_tasks_as_failed(
                controller=controller,
                failures=failed_tasks,
            )

    @staticmethod
    def _accumulate_task_acknowledgement(
        *,
        acknowledgement: TaskAcknowledgement,
        done_task_ids: list[int],
        failed_tasks: dict[int, str],
    ) -> None:
        if acknowledgement.status == "done":
            done_task_ids.append(acknowledgement.task_id)
            failed_tasks.pop(acknowledgement.task_id, None)
            return

        if acknowledgement.status == "failed":
            failed_tasks[acknowledgement.task_id] = acknowledgement.error_message or "Controller reported task failure."

    @staticmethod
    def _decision_to_result(decision: AccessDecision) -> dict[str, Any]:
        return {
            "granted": decision.granted,
            "reason_code": decision.reason_code,
            "reason_message": decision.reason_message,
            "person_id": decision.person_id,
            "wristband_id": decision.wristband_id,
        }

    @staticmethod
    def _select_processing_status(
        *,
        command: WebJsonCommand,
        response_payload: dict[str, Any],
    ) -> str:
        if response_payload.get("status") == "error":
            return WebJsonRequestLog.ProcessingStatus.ERROR

        if command.operation == "check_access":
            result = response_payload.get("result", {})
            if not result.get("granted", False):
                return WebJsonRequestLog.ProcessingStatus.ACCESS_DENIED

        return WebJsonRequestLog.ProcessingStatus.PROCESSED

    @staticmethod
    def _extract_error_message(response_payload: dict[str, Any]) -> str:
        error_payload = response_payload.get("error")
        if isinstance(error_payload, dict):
            return str(error_payload.get("message") or "")
        return ""

    @staticmethod
    def _map_direction_to_event(value: str) -> str:
        if value == "entry":
            return AccessEvent.Direction.ENTRY
        if value == "exit":
            return AccessEvent.Direction.EXIT
        return AccessEvent.Direction.UNKNOWN

    @staticmethod
    def _create_request_log(
        *,
        controller: Controller | None,
        request_id: str,
        operation: str,
        source_ip: str | None,
        processing_status: str,
        http_status: int,
        token_present: bool,
        request_body: str,
        request_payload: dict[str, Any],
        response_payload: dict[str, Any],
        error_message: str,
    ) -> WebJsonRequestLog:
        return WebJsonRequestLog.objects.create(
            controller=controller,
            request_id=request_id,
            operation=operation,
            source_ip=source_ip,
            processing_status=processing_status,
            http_status=http_status,
            token_present=token_present,
            request_body=request_body,
            request_payload=request_payload,
            response_payload=response_payload,
            error_message=error_message,
        )

    @staticmethod
    def _finalize_request_log(
        *,
        request_log: WebJsonRequestLog,
        processing_status: str,
        http_status: int,
        response_payload: dict[str, Any],
        error_message: str,
    ) -> None:
        request_log.processing_status = processing_status
        request_log.http_status = http_status
        request_log.response_payload = response_payload
        request_log.error_message = error_message
        request_log.save(update_fields=["processing_status", "http_status", "response_payload", "error_message", "updated_at"])

    @staticmethod
    def _mark_controller_seen(controller: Controller) -> None:
        updated_fields = {"last_seen_at": timezone.now()}
        if controller.status == Controller.Status.OFFLINE:
            updated_fields["status"] = Controller.Status.ACTIVE

        Controller.objects.filter(id=controller.id).update(**updated_fields)

    def _validate_security(
        self,
        *,
        headers: Mapping[str, str],
        source_ip: str | None,
        command: WebJsonCommand,
    ) -> str | None:
        configured_allowed_ips = {ip for ip in settings.IRONLOGIC_ALLOWED_IPS if ip}
        configured_token = settings.IRONLOGIC_WEBJSON_SHARED_TOKEN.strip()

        if configured_allowed_ips:
            if source_ip is None or source_ip not in configured_allowed_ips:
                return "Request IP is not allowed."

        if configured_token:
            presented_token = self._extract_auth_token(headers=headers, command=command)
            if presented_token != configured_token:
                return "Shared token validation failed."

        return None

    def _extract_source_ip(self, *, headers: Mapping[str, str], remote_addr: str | None) -> str | None:
        if settings.IRONLOGIC_TRUST_X_FORWARDED_FOR:
            forwarded_for = headers.get("X-Forwarded-For", "")
            if forwarded_for:
                return forwarded_for.split(",")[0].strip() or None
        return remote_addr

    @staticmethod
    def _extract_auth_token(*, headers: Mapping[str, str], command: WebJsonCommand) -> str | None:
        bearer_header = headers.get("Authorization", "")
        if bearer_header.lower().startswith("bearer "):
            return bearer_header.split(" ", 1)[1].strip()

        for header_name in ("X-Ironlogic-Token", "X-Controller-Token"):
            token_value = headers.get(header_name)
            if token_value:
                return token_value.strip()

        return command.auth_token


def parse_raw_json_body(raw_body: str) -> dict[str, Any] | None:
    if not raw_body.strip():
        return {}

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return None

    if isinstance(payload, dict):
        return payload
    return None
