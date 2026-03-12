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
    WebJsonEnvelope,
    WebJsonMessage,
)
from apps.ironlogic_integration.models import WebJsonRequestLog
from apps.ironlogic_integration.response_builders import (
    build_error_response,
    build_protocol_check_access_message,
    build_protocol_controller_messages,
    build_protocol_envelope_response,
    build_protocol_error_message,
    build_protocol_events_message,
    build_protocol_set_active_message,
    build_success_response,
)


SUPPORTED_REQUEST_OPERATIONS = {"power_on", "ping", "check_access", "events"}


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

        envelope = self.adapter.parse(payload)
        controller = self._resolve_controller(envelope)
        request_log = self._create_request_log(
            controller=controller,
            request_id=self._extract_request_id(envelope),
            operation=self._summarize_operations(envelope),
            source_ip=source_ip,
            processing_status=WebJsonRequestLog.ProcessingStatus.PROCESSED,
            http_status=200,
            token_present=bool(self._extract_auth_token(headers=headers, envelope=envelope)),
            request_body=raw_body,
            request_payload=payload,
            response_payload={},
            error_message="",
        )

        security_error = self._validate_security(headers=headers, source_ip=source_ip, envelope=envelope)
        if security_error is not None:
            response_payload = self._build_error_payload(
                envelope=envelope,
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

        if controller is None:
            response_payload = self._build_error_payload(
                envelope=envelope,
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

        self._process_task_acknowledgements(
            controller=controller,
            acknowledgements=envelope.task_acknowledgements,
        )

        if controller.status == Controller.Status.DISABLED:
            if envelope.uses_message_envelope and self._contains_power_on_request(envelope):
                response_payload = build_protocol_envelope_response(
                    messages=self._build_power_on_activation_messages(
                        envelope=envelope,
                        active=False,
                        online=False,
                    ),
                    interval_seconds=settings.IRONLOGIC_RESPONSE_INTERVAL_SECONDS,
                )
                self._finalize_request_log(
                    request_log=request_log,
                    processing_status=WebJsonRequestLog.ProcessingStatus.CONTROLLER_INACTIVE,
                    http_status=200,
                    response_payload=response_payload,
                    error_message="Controller is disabled.",
                )
                return WebJsonResponse(payload=response_payload, http_status=200)

            response_payload = self._build_error_payload(
                envelope=envelope,
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

        self._update_controller_runtime_state(controller=controller, envelope=envelope)
        response = self._dispatch(envelope=envelope, controller=controller)
        processing_status = self._select_processing_status(
            envelope=envelope,
            response_payload=response.payload,
        )
        error_message = self._extract_error_message(response.payload)
        self._finalize_request_log(
            request_log=request_log,
            processing_status=processing_status,
            http_status=response.http_status,
            response_payload=response.payload,
            error_message=error_message,
        )
        return response

    def _dispatch(self, *, envelope: WebJsonEnvelope, controller: Controller) -> WebJsonResponse:
        if envelope.uses_message_envelope:
            response_messages: list[dict[str, Any]] = []
            suppress_pending_commands = False
            for message in envelope.messages:
                message_responses, message_suppresses_pending = self._dispatch_documented_message(
                    message=message,
                    controller=controller,
                )
                response_messages.extend(message_responses)
                suppress_pending_commands = suppress_pending_commands or message_suppresses_pending

            if not suppress_pending_commands:
                response_messages.extend(self._build_pending_protocol_messages(controller))
            return WebJsonResponse(
                payload=build_protocol_envelope_response(
                    messages=response_messages,
                    interval_seconds=settings.IRONLOGIC_RESPONSE_INTERVAL_SECONDS,
                ),
                http_status=200,
            )

        legacy_message = envelope.messages[0] if envelope.messages else self._build_empty_message()
        return self._dispatch_legacy_message(message=legacy_message, controller=controller)

    def _dispatch_documented_message(
        self,
        *,
        message: WebJsonMessage,
        controller: Controller,
    ) -> tuple[list[dict[str, Any]], bool]:
        if not message.operation:
            return [], False

        if message.operation not in SUPPORTED_REQUEST_OPERATIONS:
            return [
                build_protocol_error_message(
                    request_id=message.request_id,
                    operation=message.operation,
                    error_code="unknown_operation",
                    error_message="Operation is not supported by this endpoint.",
                )
            ], False

        if message.operation == "power_on":
            self._handle_power_on(controller=controller, message=message)
            activation_messages = self._build_power_on_activation_messages(
                envelope=WebJsonEnvelope(
                    controller_serial_number=controller.serial_number,
                    controller_type=None,
                    auth_token=None,
                    messages=(message,),
                    task_acknowledgements=(),
                    raw_payload=message.raw_payload,
                    uses_message_envelope=True,
                ),
                active=True,
                online=settings.IRONLOGIC_ONLINE_ACCESS_ENABLED,
            )
            return activation_messages, bool(activation_messages)

        if message.operation == "ping":
            # ASSUMPTION: ping is treated as a poll for pending commands, so the
            # response contains only command messages, if any.
            return [], False

        if message.operation == "check_access":
            decision = self._handle_check_access(controller=controller, message=message)
            return [
                build_protocol_check_access_message(
                    request_id=message.request_id,
                    granted=decision.granted,
                )
            ], False

        accepted_events = self._handle_events(controller=controller, message=message)
        return [
            build_protocol_events_message(
                request_id=message.request_id,
                events_success=accepted_events,
            )
        ], False

    def _dispatch_legacy_message(
        self,
        *,
        message: WebJsonMessage,
        controller: Controller,
    ) -> WebJsonResponse:
        if not message.operation:
            return WebJsonResponse(
                payload=build_success_response(
                    operation="ack",
                    request_id=message.request_id,
                    result={"ack": "received"},
                    commands=self._build_pending_legacy_commands(controller),
                ),
                http_status=200,
            )

        if message.operation not in SUPPORTED_REQUEST_OPERATIONS:
            return WebJsonResponse(
                payload=build_error_response(
                    operation=message.operation or "unknown",
                    request_id=message.request_id,
                    error_code="unknown_operation",
                    error_message="Operation is not supported by this endpoint.",
                ),
                http_status=200,
            )

        if message.operation == "power_on":
            self._handle_power_on(controller=controller, message=message)
            return WebJsonResponse(
                payload=build_success_response(
                    operation=message.operation,
                    request_id=message.request_id,
                    result={"ack": "power_on_received", "controller_id": controller.id},
                    commands=self._build_pending_legacy_commands(controller),
                ),
                http_status=200,
            )

        if message.operation == "ping":
            return WebJsonResponse(
                payload=build_success_response(
                    operation=message.operation,
                    request_id=message.request_id,
                    result={"ack": "pong", "controller_id": controller.id},
                    commands=self._build_pending_legacy_commands(controller),
                ),
                http_status=200,
            )

        if message.operation == "check_access":
            decision = self._handle_check_access(controller=controller, message=message)
            return WebJsonResponse(
                payload=build_success_response(
                    operation=message.operation,
                    request_id=message.request_id,
                    result=self._decision_to_result(decision),
                    commands=self._build_pending_legacy_commands(controller),
                ),
                http_status=200,
            )

        accepted_events = self._handle_events(controller=controller, message=message)
        return WebJsonResponse(
            payload=build_success_response(
                operation=message.operation,
                request_id=message.request_id,
                result={"accepted_events": accepted_events},
                commands=self._build_pending_legacy_commands(controller),
            ),
            http_status=200,
        )

    def _handle_power_on(self, *, controller: Controller, message: WebJsonMessage) -> None:
        self.event_logging_service.log_controller_event(
            controller=controller,
            message="Controller power_on received.",
            reason_code="power_on",
            raw_payload=message.raw_payload,
        )

    def _handle_check_access(
        self,
        *,
        controller: Controller,
        message: WebJsonMessage,
    ) -> AccessDecision:
        access_point = self._resolve_access_point(
            controller=controller,
            access_point_code=message.access_point_code,
            device_port=message.device_port,
        )
        if access_point is None:
            self.event_logging_service.log_controller_event(
                controller=controller,
                message="Access point could not be resolved for access check.",
                reason_code="access_point_not_found",
                credential_uid=message.credential_uid or "",
                raw_payload=message.raw_payload,
            )
            return AccessDecision(
                granted=False,
                reason_code="access_point_not_found",
                reason_message="Access point could not be resolved for access check.",
                person_id=None,
                wristband_id=None,
            )

        decision = self.access_decision_service.decide(
            uid=message.credential_uid or "",
            access_point=access_point,
        )
        self.event_logging_service.log_access_decision(
            decision=decision,
            access_point=access_point,
            credential_uid=message.credential_uid or "",
            controller=controller,
            raw_payload=message.raw_payload,
        )
        return decision

    def _handle_events(self, *, controller: Controller, message: WebJsonMessage) -> int:
        accepted_events = 0
        access_point_cache: dict[tuple[str | None, int | None], AccessPoint | None] = {}
        for incoming_event in message.events:
            cache_key = (incoming_event.access_point_code, incoming_event.device_port)
            if cache_key not in access_point_cache:
                access_point_cache[cache_key] = self._resolve_access_point(
                    controller=controller,
                    access_point_code=incoming_event.access_point_code,
                    device_port=incoming_event.device_port,
                )

            self._log_incoming_event(
                controller=controller,
                incoming_event=incoming_event,
                access_point=access_point_cache[cache_key],
            )
            accepted_events += 1

        return accepted_events

    def _resolve_controller(self, envelope: WebJsonEnvelope) -> Controller | None:
        if not envelope.controller_serial_number:
            return None
        return get_controller_by_serial_number(envelope.controller_serial_number)

    def _resolve_access_point(
        self,
        *,
        controller: Controller,
        access_point_code: str | None,
        device_port: int | None,
    ) -> AccessPoint | None:
        return get_active_access_point_for_controller(
            controller_id=controller.id,
            access_point_code=access_point_code,
            device_port=device_port,
        )

    def _build_pending_legacy_commands(self, controller: Controller) -> list[dict[str, Any]]:
        batch = self.controller_task_batch_service.dispatch_pending_batch(
            controller=controller,
            max_commands=settings.IRONLOGIC_TASK_BATCH_SIZE,
            max_payload_bytes=settings.IRONLOGIC_TASK_BATCH_MAX_BYTES,
        )
        return batch.commands

    def _build_pending_protocol_messages(self, controller: Controller) -> list[dict[str, Any]]:
        batch = self.controller_task_batch_service.dispatch_pending_batch(
            controller=controller,
            max_commands=settings.IRONLOGIC_TASK_BATCH_SIZE,
            max_payload_bytes=settings.IRONLOGIC_TASK_BATCH_MAX_BYTES,
        )
        return build_protocol_controller_messages(list(batch.tasks))

    def _build_power_on_activation_messages(
        self,
        *,
        envelope: WebJsonEnvelope,
        active: bool,
        online: bool,
    ) -> list[dict[str, Any]]:
        if not settings.IRONLOGIC_AUTO_ACTIVATE_ON_POWER_ON:
            return []

        activation_messages: list[dict[str, Any]] = []
        for message in envelope.messages:
            if message.operation != "power_on":
                continue
            if message.active_state == 1 and active:
                continue

            activation_messages.append(
                build_protocol_set_active_message(
                    request_id=message.request_id,
                    active=active,
                    online=online and active,
                )
            )

        return activation_messages

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
        acknowledgements: tuple[TaskAcknowledgement, ...],
    ) -> None:
        done_task_ids: list[int] = []
        failed_tasks: dict[int, str] = {}

        for acknowledgement in acknowledgements:
            self._log_task_acknowledgement_payload(
                controller=controller,
                acknowledgement=acknowledgement,
            )
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

    def _log_task_acknowledgement_payload(
        self,
        *,
        controller: Controller,
        acknowledgement: TaskAcknowledgement,
    ) -> None:
        raw_payload = acknowledgement.raw_payload
        if not isinstance(raw_payload, dict):
            return

        cards = raw_payload.get("cards")
        if not isinstance(cards, list):
            return

        self.event_logging_service.log_controller_event(
            controller=controller,
            message=f"Controller returned {len(cards)} cards from read_cards.",
            reason_code="read_cards_result",
            raw_payload=raw_payload,
        )

    @staticmethod
    def _decision_to_result(decision: AccessDecision) -> dict[str, Any]:
        return {
            "granted": decision.granted,
            "reason_code": decision.reason_code,
            "reason_message": decision.reason_message,
            "person_id": decision.person_id,
            "wristband_id": decision.wristband_id,
        }

    def _build_error_payload(
        self,
        *,
        envelope: WebJsonEnvelope,
        error_code: str,
        error_message: str,
    ) -> dict[str, Any]:
        if not envelope.uses_message_envelope:
            message = envelope.messages[0] if envelope.messages else self._build_empty_message()
            return build_error_response(
                operation=message.operation or "unknown",
                request_id=message.request_id,
                error_code=error_code,
                error_message=error_message,
            )

        request_messages = [message for message in envelope.messages if message.operation]
        if not request_messages:
            protocol_messages = [
                build_protocol_error_message(
                    request_id=None,
                    operation="unknown",
                    error_code=error_code,
                    error_message=error_message,
                )
            ]
        else:
            protocol_messages = [
                build_protocol_error_message(
                    request_id=message.request_id,
                    operation=message.operation or "unknown",
                    error_code=error_code,
                    error_message=error_message,
                )
                for message in request_messages
            ]

        return build_protocol_envelope_response(
            messages=protocol_messages,
            interval_seconds=settings.IRONLOGIC_RESPONSE_INTERVAL_SECONDS,
        )

    @staticmethod
    def _select_processing_status(
        *,
        envelope: WebJsonEnvelope,
        response_payload: dict[str, Any],
    ) -> str:
        if envelope.uses_message_envelope:
            messages = response_payload.get("messages")
            if isinstance(messages, list):
                for message in messages:
                    if not isinstance(message, dict):
                        continue
                    if message.get("operation") == "check_access" and message.get("granted") == 0:
                        return WebJsonRequestLog.ProcessingStatus.ACCESS_DENIED
                    if "error" in message or message.get("success") == 0:
                        return WebJsonRequestLog.ProcessingStatus.ERROR
            return WebJsonRequestLog.ProcessingStatus.PROCESSED

        if response_payload.get("status") == "error":
            return WebJsonRequestLog.ProcessingStatus.ERROR

        if envelope.messages and envelope.messages[0].operation == "check_access":
            result = response_payload.get("result", {})
            if not result.get("granted", False):
                return WebJsonRequestLog.ProcessingStatus.ACCESS_DENIED

        return WebJsonRequestLog.ProcessingStatus.PROCESSED

    @staticmethod
    def _extract_error_message(response_payload: dict[str, Any]) -> str:
        error_payload = response_payload.get("error")
        if isinstance(error_payload, dict):
            return str(error_payload.get("message") or "")

        messages = response_payload.get("messages")
        if isinstance(messages, list):
            for message in messages:
                if not isinstance(message, dict):
                    continue
                nested_error = message.get("error")
                if isinstance(nested_error, dict):
                    return str(nested_error.get("message") or "")
        return ""

    @staticmethod
    def _map_direction_to_event(value: str) -> str:
        if value == "entry":
            return AccessEvent.Direction.ENTRY
        if value == "exit":
            return AccessEvent.Direction.EXIT
        return AccessEvent.Direction.UNKNOWN

    @staticmethod
    def _extract_request_id(envelope: WebJsonEnvelope) -> str:
        for message in envelope.messages:
            if message.request_id:
                return message.request_id
        return ""

    @staticmethod
    def _summarize_operations(envelope: WebJsonEnvelope) -> str:
        operations: list[str] = []
        for message in envelope.messages:
            operation = message.operation or "ack"
            if operation not in operations:
                operations.append(operation)
        if not operations:
            return "empty"
        if len(operations) == 1:
            return operations[0]
        return ",".join(operations)[:64]

    @staticmethod
    def _contains_power_on_request(envelope: WebJsonEnvelope) -> bool:
        return any(message.operation == "power_on" for message in envelope.messages)

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
        request_log.save(
            update_fields=[
                "processing_status",
                "http_status",
                "response_payload",
                "error_message",
                "updated_at",
            ]
        )

    @staticmethod
    def _update_controller_runtime_state(
        *,
        controller: Controller,
        envelope: WebJsonEnvelope,
    ) -> None:
        updated_fields: dict[str, Any] = {"last_seen_at": timezone.now()}
        if controller.status == Controller.Status.OFFLINE:
            updated_fields["status"] = Controller.Status.ACTIVE

        for runtime_message in envelope.messages:
            if runtime_message.controller_ip:
                updated_fields["ip_address"] = runtime_message.controller_ip
            if runtime_message.firmware_version:
                updated_fields["firmware_version"] = runtime_message.firmware_version
            if runtime_message.connection_firmware_version:
                updated_fields["connection_firmware_version"] = runtime_message.connection_firmware_version
            if runtime_message.active_state is not None:
                updated_fields["active_state"] = runtime_message.active_state
            if runtime_message.mode is not None:
                updated_fields["mode_state"] = runtime_message.mode
            if runtime_message.auth_hash:
                updated_fields["last_auth_hash"] = runtime_message.auth_hash

        Controller.objects.filter(id=controller.id).update(**updated_fields)

    def _validate_security(
        self,
        *,
        headers: Mapping[str, str],
        source_ip: str | None,
        envelope: WebJsonEnvelope,
    ) -> str | None:
        configured_allowed_ips = {ip for ip in settings.IRONLOGIC_ALLOWED_IPS if ip}
        configured_token = settings.IRONLOGIC_WEBJSON_SHARED_TOKEN.strip()

        if configured_allowed_ips:
            if source_ip is None or source_ip not in configured_allowed_ips:
                return "Request IP is not allowed."

        if configured_token:
            presented_token = self._extract_auth_token(headers=headers, envelope=envelope)
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
    def _extract_auth_token(*, headers: Mapping[str, str], envelope: WebJsonEnvelope) -> str | None:
        bearer_header = headers.get("Authorization", "")
        if bearer_header.lower().startswith("bearer "):
            return bearer_header.split(" ", 1)[1].strip()

        for header_name in ("X-Ironlogic-Token", "X-Controller-Token"):
            token_value = headers.get(header_name)
            if token_value:
                return token_value.strip()

        return envelope.auth_token

    @staticmethod
    def _build_empty_message() -> WebJsonMessage:
        return WebJsonMessage(
            operation="",
            request_id=None,
            access_point_code=None,
            device_port=None,
            credential_uid=None,
            auth_token=None,
            auth_hash=None,
            events=(),
            task_acknowledgements=(),
            firmware_version=None,
            connection_firmware_version=None,
            controller_ip=None,
            active_state=None,
            mode=None,
            raw_payload={},
        )


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
