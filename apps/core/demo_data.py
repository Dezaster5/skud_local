from __future__ import annotations

from dataclasses import dataclass
from datetime import time, timedelta
from typing import Any, TypeVar

from django.db import models, transaction
from django.utils import timezone

from apps.access.models import AccessPoint, AccessPolicy, TimeZoneRule
from apps.controllers.models import Controller, ControllerTask
from apps.events.models import AccessEvent, AuditLog
from apps.people.models import Person
from apps.wristbands.models import Wristband

ModelT = TypeVar("ModelT", bound=models.Model)


@dataclass(slots=True, frozen=True)
class DemoSeedResult:
    people: int
    wristbands: int
    controllers: int
    access_points: int
    access_policies: int
    controller_tasks: int
    access_events: int
    audit_logs: int


def seed_demo_data() -> DemoSeedResult:
    now = timezone.now()

    with transaction.atomic():
        controller, _ = _upsert_single(
            Controller,
            lookup={"serial_number": "DEMO-Z5R-001"},
            defaults={
                "name": "Demo Gate Controller",
                "controller_type": Controller.ControllerType.IRONLOGIC_Z5R_WEB_BT,
                "status": Controller.Status.ACTIVE,
                "ip_address": "192.168.1.150",
                "firmware_version": "demo-fw-1.0",
                "description": "Demo controller for local development and manual API checks.",
                "last_seen_at": now,
            },
        )

        entry_point, _ = _upsert_single(
            AccessPoint,
            lookup={"controller": controller, "code": "main-entry"},
            defaults={
                "name": "Main Entry",
                "direction": AccessPoint.Direction.ENTRY,
                "status": AccessPoint.Status.ACTIVE,
                "device_port": 1,
                "location": "Lobby",
                "description": "Primary entry turnstile.",
            },
        )
        exit_point, _ = _upsert_single(
            AccessPoint,
            lookup={"controller": controller, "code": "main-exit"},
            defaults={
                "name": "Main Exit",
                "direction": AccessPoint.Direction.EXIT,
                "status": AccessPoint.Status.ACTIVE,
                "device_port": 2,
                "location": "Lobby",
                "description": "Primary exit turnstile.",
            },
        )

        office_hours_rule, _ = _upsert_single(
            TimeZoneRule,
            lookup={"name": "demo_weekday_office_hours"},
            defaults={
                "description": "Weekday daytime access for demo visitors.",
                "timezone_name": "Asia/Almaty",
                "weekdays": [1, 2, 3, 4, 5],
                "start_time": time(8, 0, 0),
                "end_time": time(20, 0, 0),
                "is_active": True,
            },
        )

        employee, _ = _upsert_single(
            Person,
            lookup={"email": "alice.demo@example.com"},
            defaults={
                "first_name": "Alice",
                "last_name": "Demo",
                "person_type": Person.PersonType.EMPLOYEE,
                "status": Person.Status.ACTIVE,
                "phone": "+77000000001",
                "note": "Always-allowed employee demo profile.",
            },
        )
        visitor, _ = _upsert_single(
            Person,
            lookup={"email": "bob.demo@example.com"},
            defaults={
                "first_name": "Bob",
                "last_name": "Visitor",
                "person_type": Person.PersonType.VISITOR,
                "status": Person.Status.ACTIVE,
                "phone": "+77000000002",
                "valid_until": now + timedelta(days=14),
                "note": "Visitor demo profile with office-hours-only access.",
            },
        )
        suspended_person, _ = _upsert_single(
            Person,
            lookup={"email": "eve.demo@example.com"},
            defaults={
                "first_name": "Eve",
                "last_name": "Blocked",
                "person_type": Person.PersonType.CONTRACTOR,
                "status": Person.Status.SUSPENDED,
                "phone": "+77000000003",
                "note": "Negative demo profile for denied access scenarios.",
            },
        )

        employee_wristband, _ = _upsert_single(
            Wristband,
            lookup={"uid": "04DEMO000001"},
            defaults={
                "person": employee,
                "status": Wristband.Status.ACTIVE,
                "issued_at": now - timedelta(days=30),
                "note": "Demo employee wristband.",
            },
        )
        visitor_wristband, _ = _upsert_single(
            Wristband,
            lookup={"uid": "04DEMO000002"},
            defaults={
                "person": visitor,
                "status": Wristband.Status.ACTIVE,
                "issued_at": now - timedelta(days=7),
                "expires_at": now + timedelta(days=14),
                "note": "Demo visitor wristband.",
            },
        )
        blocked_wristband, _ = _upsert_single(
            Wristband,
            lookup={"uid": "04DEMO000003"},
            defaults={
                "person": suspended_person,
                "status": Wristband.Status.BLOCKED,
                "issued_at": now - timedelta(days=14),
                "note": "Blocked demo wristband.",
            },
        )
        spare_wristband, _ = _upsert_single(
            Wristband,
            lookup={"uid": "04DEMO000004"},
            defaults={
                "person": None,
                "status": Wristband.Status.ACTIVE,
                "note": "Unassigned spare demo wristband.",
            },
        )

        _upsert_single(
            AccessPolicy,
            lookup={"name": "demo_employee_entry_allow"},
            defaults={
                "description": "24/7 access for Alice on main entry.",
                "person": employee,
                "access_point": entry_point,
                "timezone_rule": None,
                "effect": AccessPolicy.Effect.ALLOW,
                "status": AccessPolicy.Status.ACTIVE,
                "priority": 100,
            },
        )
        _upsert_single(
            AccessPolicy,
            lookup={"name": "demo_employee_exit_allow"},
            defaults={
                "description": "24/7 access for Alice on main exit.",
                "person": employee,
                "access_point": exit_point,
                "timezone_rule": None,
                "effect": AccessPolicy.Effect.ALLOW,
                "status": AccessPolicy.Status.ACTIVE,
                "priority": 100,
            },
        )
        _upsert_single(
            AccessPolicy,
            lookup={"name": "demo_visitor_entry_allow"},
            defaults={
                "description": "Office-hours-only access for Bob on main entry.",
                "person": visitor,
                "access_point": entry_point,
                "timezone_rule": office_hours_rule,
                "effect": AccessPolicy.Effect.ALLOW,
                "status": AccessPolicy.Status.ACTIVE,
                "priority": 100,
            },
        )
        _upsert_single(
            AccessPolicy,
            lookup={"name": "demo_blocked_entry_deny"},
            defaults={
                "description": "Explicit deny rule for blocked demo profile.",
                "person": suspended_person,
                "access_point": entry_point,
                "timezone_rule": None,
                "effect": AccessPolicy.Effect.DENY,
                "status": AccessPolicy.Status.ACTIVE,
                "priority": 50,
            },
        )

        _ensure_pending_task(
            controller=controller,
            task_type=ControllerTask.TaskType.OPEN_DOOR,
            priority=10,
            protocol_payload={
                "duration_seconds": 3,
                "access_point_id": entry_point.id,
                "access_point_code": entry_point.code,
            },
            meta={
                "source": "seed_demo_data",
                "requested_by": "seed_demo_data",
            },
        )
        _ensure_pending_task(
            controller=controller,
            task_type=ControllerTask.TaskType.READ_CARDS,
            priority=40,
            protocol_payload={"scope": "all"},
            meta={
                "source": "seed_demo_data",
                "requested_by": "seed_demo_data",
            },
        )

        _upsert_single(
            AccessEvent,
            lookup={
                "event_type": AccessEvent.EventType.ACCESS_GRANTED,
                "reason_code": "demo_access_granted",
                "credential_uid": employee_wristband.uid,
            },
            defaults={
                "controller": controller,
                "access_point": entry_point,
                "person": employee,
                "wristband": employee_wristband,
                "direction": AccessEvent.Direction.ENTRY,
                "decision": AccessEvent.Decision.GRANTED,
                "message": "Demo granted access event.",
                "occurred_at": now - timedelta(minutes=10),
                "raw_payload": {
                    "operation": "check_access",
                    "uid": employee_wristband.uid,
                    "result": "granted",
                },
            },
        )
        _upsert_single(
            AccessEvent,
            lookup={
                "event_type": AccessEvent.EventType.ACCESS_DENIED,
                "reason_code": "demo_access_denied",
                "credential_uid": blocked_wristband.uid,
            },
            defaults={
                "controller": controller,
                "access_point": entry_point,
                "person": suspended_person,
                "wristband": blocked_wristband,
                "direction": AccessEvent.Direction.ENTRY,
                "decision": AccessEvent.Decision.DENIED,
                "message": "Demo denied access event.",
                "occurred_at": now - timedelta(minutes=5),
                "raw_payload": {
                    "operation": "check_access",
                    "uid": blocked_wristband.uid,
                    "result": "denied",
                },
            },
        )
        _upsert_single(
            AuditLog,
            lookup={
                "action": "seed_demo_data",
                "object_type": "system",
                "object_id": "demo_seed_v1",
            },
            defaults={
                "source": AuditLog.Source.SYSTEM,
                "object_repr": "Demo seed data",
                "details": {
                    "controller_serial_number": controller.serial_number,
                    "entry_point": entry_point.code,
                    "employee_uid": employee_wristband.uid,
                    "visitor_uid": visitor_wristband.uid,
                    "spare_uid": spare_wristband.uid,
                },
            },
        )

    return DemoSeedResult(
        people=Person.objects.count(),
        wristbands=Wristband.objects.count(),
        controllers=Controller.objects.count(),
        access_points=AccessPoint.objects.count(),
        access_policies=AccessPolicy.objects.count(),
        controller_tasks=ControllerTask.objects.count(),
        access_events=AccessEvent.objects.count(),
        audit_logs=AuditLog.objects.count(),
    )


def _upsert_single(
    model: type[ModelT],
    *,
    lookup: dict[str, Any],
    defaults: dict[str, Any],
) -> tuple[ModelT, bool]:
    instance = model.objects.filter(**lookup).order_by("id").first()
    if instance is None:
        return model.objects.create(**lookup, **defaults), True

    changed_fields: list[str] = []
    for field_name, value in defaults.items():
        if getattr(instance, field_name) != value:
            setattr(instance, field_name, value)
            changed_fields.append(field_name)

    if changed_fields:
        instance.save(update_fields=changed_fields + ["updated_at"] if _has_field(instance, "updated_at") else changed_fields)

    return instance, False


def _ensure_pending_task(
    *,
    controller: Controller,
    task_type: str,
    priority: int,
    protocol_payload: dict[str, Any],
    meta: dict[str, Any],
) -> ControllerTask:
    payload = {
        "protocol": protocol_payload,
        "meta": meta,
    }
    task = (
        ControllerTask.objects.filter(
            controller=controller,
            task_type=task_type,
            status=ControllerTask.Status.PENDING,
        )
        .order_by("id")
        .first()
    )
    if task is None:
        return ControllerTask.objects.create(
            controller=controller,
            task_type=task_type,
            status=ControllerTask.Status.PENDING,
            payload=payload,
            priority=priority,
        )

    task.payload = payload
    task.priority = priority
    task.error_message = ""
    task.scheduled_for = None
    task.sent_at = None
    task.completed_at = None
    task.save(
        update_fields=[
            "payload",
            "priority",
            "error_message",
            "scheduled_for",
            "sent_at",
            "completed_at",
            "updated_at",
        ]
    )
    return task


def _has_field(instance: models.Model, field_name: str) -> bool:
    return any(field.name == field_name for field in instance._meta.concrete_fields)
