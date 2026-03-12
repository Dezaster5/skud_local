from __future__ import annotations

from datetime import time, timedelta

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.access.models import AccessPolicy
from apps.controllers.models import ControllerTask
from apps.controllers.services import ControllerTaskService
from apps.core.testing import (
    create_access_point,
    create_access_policy,
    create_controller,
    create_person,
    create_timezone_rule,
    create_wristband,
)
from apps.events.models import AccessEvent
from apps.ironlogic_integration.models import WebJsonRequestLog
from apps.people.models import Person
from apps.wristbands.models import Wristband


@override_settings(
    IRONLOGIC_ALLOWED_IPS=[],
    IRONLOGIC_WEBJSON_SHARED_TOKEN="",
    IRONLOGIC_TASK_BATCH_SIZE=20,
    IRONLOGIC_TASK_BATCH_MAX_BYTES=16384,
)
class IronLogicWebJsonAPITests(APITestCase):
    def setUp(self) -> None:
        self.url = reverse("ironlogic:ironlogic-webjson")
        self.controller = create_controller(serial_number="Z5R-001")
        self.access_point = create_access_point(
            controller=self.controller,
            code="main-entry",
            device_port=1,
        )

    def _post(self, payload: dict) -> tuple[int, dict]:
        response = self.client.post(self.url, data=payload, format="json")
        return response.status_code, response.json()

    def _check_access_payload(self, uid: str) -> dict:
        return {
            "request_id": "acc-1",
            "operation": "check_access",
            "controller": {
                "serial_number": self.controller.serial_number,
                "access_point_code": self.access_point.code,
            },
            "credential": {
                "uid": uid,
            },
        }

    def test_check_access_granted(self) -> None:
        person = create_person()
        wristband = create_wristband(person=person, uid="04ALLOW0001")
        create_access_policy(person=person, access_point=self.access_point)

        status_code, payload = self._post(self._check_access_payload(wristband.uid))

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["result"]["granted"])
        self.assertEqual(payload["result"]["reason_code"], "access_granted")
        self.assertEqual(AccessEvent.objects.filter(decision=AccessEvent.Decision.GRANTED).count(), 1)

    def test_check_access_denies_for_missing_wristband(self) -> None:
        status_code, payload = self._post(self._check_access_payload("04UNKNOWN0001"))

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["result"]["reason_code"], "wristband_not_found")
        self.assertFalse(payload["result"]["granted"])

    def test_check_access_denies_for_blocked_wristband(self) -> None:
        wristband = create_wristband(status=Wristband.Status.BLOCKED, uid="04BLOCK0001")

        status_code, payload = self._post(self._check_access_payload(wristband.uid))

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["result"]["reason_code"], "wristband_blocked")
        self.assertFalse(payload["result"]["granted"])

    def test_check_access_denies_for_inactive_person(self) -> None:
        person = create_person(status=Person.Status.INACTIVE)
        wristband = create_wristband(person=person, uid="04PERSOFF01")

        status_code, payload = self._post(self._check_access_payload(wristband.uid))

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["result"]["reason_code"], "person_inactive")
        self.assertFalse(payload["result"]["granted"])

    def test_check_access_denies_for_expired_wristband(self) -> None:
        wristband = create_wristband(
            uid="04EXP000001",
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        status_code, payload = self._post(self._check_access_payload(wristband.uid))

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["result"]["reason_code"], "wristband_expired")
        self.assertFalse(payload["result"]["granted"])

    def test_check_access_denies_without_policy(self) -> None:
        wristband = create_wristband(uid="04NOPOLICY1")

        status_code, payload = self._post(self._check_access_payload(wristband.uid))

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["result"]["reason_code"], "no_access_policy")
        self.assertFalse(payload["result"]["granted"])

    def test_check_access_denies_outside_timezone(self) -> None:
        now = timezone.localtime(timezone.now())
        current_weekday = now.isoweekday()
        denied_weekday = 1 if current_weekday != 1 else 2

        person = create_person()
        wristband = create_wristband(person=person, uid="04OUTSIDE01")
        timezone_rule = create_timezone_rule(
            weekdays=[denied_weekday],
            start_time=time(8, 0, 0),
            end_time=time(18, 0, 0),
        )
        create_access_policy(
            person=person,
            access_point=self.access_point,
            timezone_rule=timezone_rule,
        )

        status_code, payload = self._post(self._check_access_payload(wristband.uid))

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["result"]["reason_code"], "outside_timezone")
        self.assertFalse(payload["result"]["granted"])

    def test_ping_returns_pending_tasks_and_marks_them_sent(self) -> None:
        task_service = ControllerTaskService()
        task = task_service.enqueue_manual_open(controller=self.controller, duration_seconds=3)

        status_code, payload = self._post(
            {
                "request_id": "ping-1",
                "operation": "ping",
                "controller": {
                    "serial_number": self.controller.serial_number,
                },
            }
        )

        task.refresh_from_db()
        self.assertEqual(status_code, 200)
        self.assertEqual(payload["result"]["ack"], "pong")
        self.assertEqual(len(payload["commands"]), 1)
        self.assertEqual(payload["commands"][0]["task_id"], task.id)
        self.assertEqual(task.status, ControllerTask.Status.SENT)

    def test_ping_processes_task_acknowledgements(self) -> None:
        task_service = ControllerTaskService()
        done_task = task_service.enqueue_manual_open(controller=self.controller, duration_seconds=3)
        failed_task = task_service.enqueue_manual_open(controller=self.controller, duration_seconds=5)
        task_service.mark_tasks_as_sent([done_task, failed_task])

        status_code, payload = self._post(
            {
                "request_id": "ping-ack-1",
                "operation": "ping",
                "controller": {
                    "serial_number": self.controller.serial_number,
                },
                "task_results": [
                    {
                        "task_id": done_task.id,
                        "status": "done",
                    },
                    {
                        "task_id": failed_task.id,
                        "status": "failed",
                        "error_message": "memory full",
                    },
                ],
            }
        )

        done_task.refresh_from_db()
        failed_task.refresh_from_db()
        self.assertEqual(status_code, 200)
        self.assertEqual(payload["result"]["ack"], "pong")
        self.assertEqual(done_task.status, ControllerTask.Status.DONE)
        self.assertEqual(failed_task.status, ControllerTask.Status.FAILED)
        self.assertEqual(failed_task.error_message, "memory full")

    def test_events_operation_saves_event(self) -> None:
        status_code, payload = self._post(
            {
                "request_id": "evt-1",
                "operation": "events",
                "controller": {
                    "serial_number": self.controller.serial_number,
                },
                "events": [
                    {
                        "timestamp": timezone.now().isoformat(),
                        "uid": "04EVENT0001",
                        "direction": "entry",
                        "reason_code": "turnstile_passed",
                        "message": "Pass completed",
                        "point": self.access_point.code,
                    }
                ],
            }
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["result"]["accepted_events"], 1)
        self.assertEqual(AccessEvent.objects.filter(event_type=AccessEvent.EventType.CONTROLLER_EVENT).count(), 1)
        self.assertEqual(AccessEvent.objects.get().credential_uid, "04EVENT0001")

    def test_unknown_operation_does_not_crash_endpoint(self) -> None:
        status_code, payload = self._post(
            {
                "request_id": "unknown-1",
                "operation": "reboot_now",
                "controller": {
                    "serial_number": self.controller.serial_number,
                },
            }
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"]["code"], "unknown_operation")
        self.assertEqual(WebJsonRequestLog.objects.count(), 1)
