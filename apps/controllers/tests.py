from __future__ import annotations

from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.controllers.models import ControllerTask
from apps.controllers.services import ControllerSyncService, ControllerTaskBatchService, ControllerTaskService
from apps.core.testing import create_access_point, create_controller, create_person, create_wristband
from apps.wristbands.models import Wristband


class ControllerTaskServiceTests(TestCase):
    def setUp(self) -> None:
        self.controller = create_controller()
        self.task_service = ControllerTaskService()

    def test_mark_tasks_as_sent_updates_status_and_attempts(self) -> None:
        task = self.task_service.enqueue_manual_open(controller=self.controller, duration_seconds=3)

        updated_count = self.task_service.mark_tasks_as_sent([task])

        task.refresh_from_db()
        self.assertEqual(updated_count, 1)
        self.assertEqual(task.status, ControllerTask.Status.SENT)
        self.assertEqual(task.attempts, 1)
        self.assertIsNotNone(task.sent_at)

    def test_mark_tasks_as_done_updates_status_and_completed_at(self) -> None:
        task = self.task_service.enqueue_manual_open(controller=self.controller, duration_seconds=3)
        self.task_service.mark_tasks_as_sent([task])

        updated_count = self.task_service.mark_tasks_as_done(
            controller=self.controller,
            task_ids=[task.id],
        )

        task.refresh_from_db()
        self.assertEqual(updated_count, 1)
        self.assertEqual(task.status, ControllerTask.Status.DONE)
        self.assertEqual(task.error_message, "")
        self.assertIsNotNone(task.completed_at)
        self.assertGreaterEqual(task.updated_at, task.completed_at)

    def test_mark_tasks_as_failed_updates_status_and_error_message(self) -> None:
        task = self.task_service.enqueue_manual_open(controller=self.controller, duration_seconds=3)
        self.task_service.mark_tasks_as_sent([task])

        updated_count = self.task_service.mark_tasks_as_failed(
            controller=self.controller,
            failures={task.id: "controller memory full"},
        )

        task.refresh_from_db()
        self.assertEqual(updated_count, 1)
        self.assertEqual(task.status, ControllerTask.Status.FAILED)
        self.assertEqual(task.error_message, "controller memory full")
        self.assertIsNotNone(task.completed_at)

    @override_settings(IRONLOGIC_TASK_SENT_RETRY_SECONDS=1)
    def test_requeue_stale_sent_tasks_returns_old_sent_tasks_to_pending(self) -> None:
        task = self.task_service.enqueue_manual_open(controller=self.controller, duration_seconds=3)
        task.status = ControllerTask.Status.SENT
        task.sent_at = timezone.now() - timedelta(seconds=10)
        task.save(update_fields=["status", "sent_at", "updated_at"])

        updated_count = self.task_service.requeue_stale_sent_tasks(controller=self.controller)

        task.refresh_from_db()
        self.assertEqual(updated_count, 1)
        self.assertEqual(task.status, ControllerTask.Status.PENDING)
        self.assertIsNone(task.sent_at)

    def test_sync_service_full_sync_creates_clear_and_add_batches(self) -> None:
        sync_service = ControllerSyncService(task_service=self.task_service)
        person = create_person()
        create_wristband(person=person, uid="04SYNC000001")
        create_wristband(person=person, uid="04SYNC000002")
        create_wristband(person=person, uid="04SYNC000003")

        tasks = sync_service.plan_wristband_sync(
            controller=self.controller,
            force_full=True,
            clear_first=True,
            chunk_size=2,
            requested_by="test-suite",
        )

        self.assertEqual([task.task_type for task in tasks], [
            ControllerTask.TaskType.CLEAR_CARDS,
            ControllerTask.TaskType.ADD_WRISTBANDS,
            ControllerTask.TaskType.ADD_WRISTBANDS,
        ])
        self.assertEqual(tasks[1].payload["meta"]["batch"]["sequence"], 1)
        self.assertEqual(tasks[2].payload["meta"]["batch"]["sequence"], 2)

    def test_sync_service_delta_sync_creates_delete_and_add_batches(self) -> None:
        sync_service = ControllerSyncService(task_service=self.task_service)
        person = create_person()
        valid_wristband = create_wristband(person=person, uid="04DELTA0001")
        blocked_wristband = create_wristband(
            person=person,
            uid="04DELTA0002",
            status=Wristband.Status.BLOCKED,
        )
        unassigned_wristband = create_wristband(person=None, uid="04DELTA0003")

        tasks = sync_service.plan_wristband_sync(
            controller=self.controller,
            force_full=False,
            wristband_ids=[valid_wristband.id, blocked_wristband.id, unassigned_wristband.id],
            chunk_size=10,
            requested_by="test-suite",
        )

        self.assertEqual(
            [task.task_type for task in tasks],
            [
                ControllerTask.TaskType.DEL_WRISTBANDS,
                ControllerTask.TaskType.ADD_WRISTBANDS,
            ],
        )
        self.assertEqual(
            {card["uid"] for card in tasks[0].payload["protocol"]["cards"]},
            {"04DELTA0002", "04DELTA0003"},
        )
        self.assertEqual(
            tasks[1].payload["protocol"]["cards"][0]["uid"],
            "04DELTA0001",
        )

    def test_enqueue_set_door_params_creates_documented_protocol_payload(self) -> None:
        task = self.task_service.enqueue_set_door_params(
            controller=self.controller,
            open_time=10,
            open_control_time=20,
            close_control_time=30,
            requested_by="test-suite",
        )

        self.assertEqual(task.task_type, ControllerTask.TaskType.SET_DOOR_PARAMS)
        self.assertEqual(
            task.payload["protocol"],
            {
                "open": 10,
                "open_control": 20,
                "close_control": 30,
            },
        )

    def test_enqueue_read_cards_creates_protocol_task(self) -> None:
        task = self.task_service.enqueue_read_cards(
            controller=self.controller,
            requested_by="test-suite",
        )

        self.assertEqual(task.task_type, ControllerTask.TaskType.READ_CARDS)
        self.assertEqual(task.payload["protocol"], {})

    @override_settings(IRONLOGIC_TASK_BATCH_SIZE=10, IRONLOGIC_TASK_BATCH_MAX_BYTES=150)
    def test_batch_service_respects_payload_limit_and_marks_tasks_sent(self) -> None:
        batch_service = ControllerTaskBatchService(task_service=self.task_service)
        task_one = self.task_service.create_task(
            controller=self.controller,
            task_type=ControllerTask.TaskType.OPEN_DOOR,
            payload={"protocol": {"duration_seconds": 3, "padding": "x" * 60}},
            priority=10,
        )
        task_two = self.task_service.create_task(
            controller=self.controller,
            task_type=ControllerTask.TaskType.OPEN_DOOR,
            payload={"protocol": {"duration_seconds": 3, "padding": "y" * 60}},
            priority=20,
        )

        batch = batch_service.dispatch_pending_batch(controller=self.controller)

        self.assertEqual(len(batch.tasks), 1)
        self.assertEqual(batch.tasks[0].id, task_one.id)
        self.assertTrue(batch.has_more)

        task_one.refresh_from_db()
        task_two.refresh_from_db()
        self.assertEqual(task_one.status, ControllerTask.Status.SENT)
        self.assertEqual(task_two.status, ControllerTask.Status.PENDING)
