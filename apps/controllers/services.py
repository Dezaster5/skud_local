from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.access.models import AccessPoint
from apps.controllers.models import Controller, ControllerTask
from apps.controllers.selectors import get_pending_controller_tasks
from apps.wristbands.models import Wristband
from apps.wristbands.selectors import get_wristbands_for_sync


@dataclass(slots=True, frozen=True)
class ControllerTaskBatch:
    tasks: tuple[ControllerTask, ...]
    commands: list[dict[str, Any]]
    estimated_payload_bytes: int
    has_more: bool


class ControllerTaskService:
    def get_pending_tasks(
        self,
        *,
        controller: Controller,
        limit: int = 100,
        scheduled_before: datetime | None = None,
    ) -> list[ControllerTask]:
        return get_pending_controller_tasks(
            controller_id=controller.id,
            limit=limit,
            scheduled_before=scheduled_before,
        )

    def create_task(
        self,
        *,
        controller: Controller,
        task_type: str,
        payload: dict[str, Any] | None = None,
        priority: int = 100,
        scheduled_for: datetime | None = None,
    ) -> ControllerTask:
        return ControllerTask.objects.create(
            controller=controller,
            task_type=task_type,
            payload=payload or {},
            priority=priority,
            scheduled_for=scheduled_for,
        )

    def mark_tasks_as_sent(
        self,
        tasks: Sequence[ControllerTask],
        *,
        sent_at: datetime | None = None,
    ) -> int:
        task_ids = [task.id for task in tasks]
        if not task_ids:
            return 0

        effective_sent_at = sent_at or timezone.now()
        return ControllerTask.objects.filter(
            id__in=task_ids,
            status=ControllerTask.Status.PENDING,
        ).update(
            status=ControllerTask.Status.SENT,
            sent_at=effective_sent_at,
            attempts=F("attempts") + 1,
            updated_at=effective_sent_at,
        )

    def mark_tasks_as_done(
        self,
        *,
        controller: Controller,
        task_ids: Sequence[int],
        completed_at: datetime | None = None,
    ) -> int:
        if not task_ids:
            return 0

        effective_completed_at = completed_at or timezone.now()
        return ControllerTask.objects.filter(
            controller=controller,
            id__in=list(task_ids),
        ).exclude(
            status__in=[ControllerTask.Status.DONE, ControllerTask.Status.FAILED],
        ).update(
            status=ControllerTask.Status.DONE,
            completed_at=effective_completed_at,
            error_message="",
            updated_at=effective_completed_at,
        )

    def mark_tasks_as_failed(
        self,
        *,
        controller: Controller,
        failures: Mapping[int, str],
        completed_at: datetime | None = None,
    ) -> int:
        if not failures:
            return 0

        effective_completed_at = completed_at or timezone.now()
        updated_count = 0
        for task_id, error_message in failures.items():
            updated_count += ControllerTask.objects.filter(
                controller=controller,
                id=task_id,
            ).exclude(
                status__in=[ControllerTask.Status.DONE, ControllerTask.Status.FAILED],
            ).update(
                status=ControllerTask.Status.FAILED,
                completed_at=effective_completed_at,
                error_message=error_message[:2000],
                updated_at=effective_completed_at,
            )

        return updated_count

    def requeue_stale_sent_tasks(
        self,
        *,
        controller: Controller,
        retry_after_seconds: int | None = None,
    ) -> int:
        effective_retry_after_seconds = (
            retry_after_seconds
            if retry_after_seconds is not None
            else settings.IRONLOGIC_TASK_SENT_RETRY_SECONDS
        )
        if effective_retry_after_seconds <= 0:
            return 0

        retry_deadline = timezone.now() - timedelta(seconds=effective_retry_after_seconds)
        effective_updated_at = timezone.now()
        return ControllerTask.objects.filter(
            controller=controller,
            status=ControllerTask.Status.SENT,
            sent_at__isnull=False,
            sent_at__lte=retry_deadline,
            completed_at__isnull=True,
        ).update(
            status=ControllerTask.Status.PENDING,
            sent_at=None,
            updated_at=effective_updated_at,
        )

    def enqueue_manual_open(
        self,
        *,
        controller: Controller,
        access_point: AccessPoint | None = None,
        duration_seconds: int = 3,
        requested_by: str = "",
    ) -> ControllerTask:
        protocol_payload: dict[str, Any] = {
            "duration_seconds": duration_seconds,
        }
        if access_point is not None:
            protocol_payload["access_point_id"] = access_point.id
            protocol_payload["access_point_code"] = access_point.code
            protocol_payload["direction"] = (
                1 if access_point.direction == AccessPoint.Direction.EXIT else 0
            )

        payload = self._build_task_payload(
            protocol_payload=protocol_payload,
            source="manual_open",
            requested_by=requested_by,
        )
        return self.create_task(
            controller=controller,
            task_type=ControllerTask.TaskType.OPEN_DOOR,
            payload=payload,
            priority=10,
        )

    def enqueue_clear_cards(
        self,
        *,
        controller: Controller,
        requested_by: str = "",
        sync_strategy: str = "full_sync",
        reason: str = "controller_resync",
    ) -> ControllerTask:
        payload = self._build_task_payload(
            protocol_payload={"scope": "all"},
            source="controller_sync_service",
            requested_by=requested_by,
            sync_strategy=sync_strategy,
            reason=reason,
        )
        return self.create_task(
            controller=controller,
            task_type=ControllerTask.TaskType.CLEAR_CARDS,
            payload=payload,
            priority=20,
        )

    def enqueue_read_cards(
        self,
        *,
        controller: Controller,
        requested_by: str = "",
    ) -> ControllerTask:
        payload = self._build_task_payload(
            protocol_payload={},
            source="controller_read_cards",
            requested_by=requested_by,
        )
        return self.create_task(
            controller=controller,
            task_type=ControllerTask.TaskType.READ_CARDS,
            payload=payload,
            priority=35,
        )

    def enqueue_set_door_params(
        self,
        *,
        controller: Controller,
        open_time: int,
        open_control_time: int,
        close_control_time: int,
        requested_by: str = "",
    ) -> ControllerTask:
        payload = self._build_task_payload(
            protocol_payload={
                "open": open_time,
                "open_control": open_control_time,
                "close_control": close_control_time,
            },
            source="controller_door_params_update",
            requested_by=requested_by,
        )
        return self.create_task(
            controller=controller,
            task_type=ControllerTask.TaskType.SET_DOOR_PARAMS,
            payload=payload,
            priority=30,
        )

    def enqueue_set_mode(
        self,
        *,
        controller: Controller,
        mode: str,
        options: dict[str, Any] | None = None,
        requested_by: str = "",
    ) -> ControllerTask:
        payload = self._build_task_payload(
            protocol_payload={
                "mode": mode,
                "options": options or {},
            },
            source="controller_mode_update",
            requested_by=requested_by,
        )
        return self.create_task(
            controller=controller,
            task_type=ControllerTask.TaskType.SET_MODE,
            payload=payload,
            priority=40,
        )

    def enqueue_set_timezone(
        self,
        *,
        controller: Controller,
        timezone_payload: dict[str, Any],
        requested_by: str = "",
    ) -> ControllerTask:
        payload = self._build_task_payload(
            protocol_payload={"timezone": timezone_payload},
            source="controller_timezone_update",
            requested_by=requested_by,
        )
        return self.create_task(
            controller=controller,
            task_type=ControllerTask.TaskType.SET_TIMEZONE,
            payload=payload,
            priority=40,
        )

    def enqueue_add_wristbands_batch(
        self,
        *,
        controller: Controller,
        cards: list[dict[str, Any]],
        batch_sequence: int,
        batch_total: int,
        sync_strategy: str,
        requested_by: str = "",
    ) -> ControllerTask:
        payload = self._build_task_payload(
            protocol_payload={"cards": cards},
            source="controller_sync_service",
            requested_by=requested_by,
            sync_strategy=sync_strategy,
            batch={"sequence": batch_sequence, "total": batch_total},
            card_count=len(cards),
        )
        return self.create_task(
            controller=controller,
            task_type=ControllerTask.TaskType.ADD_WRISTBANDS,
            payload=payload,
            priority=30,
        )

    def enqueue_delete_wristbands_batch(
        self,
        *,
        controller: Controller,
        cards: list[dict[str, Any]],
        batch_sequence: int,
        batch_total: int,
        sync_strategy: str,
        requested_by: str = "",
    ) -> ControllerTask:
        payload = self._build_task_payload(
            protocol_payload={"cards": cards},
            source="controller_sync_service",
            requested_by=requested_by,
            sync_strategy=sync_strategy,
            batch={"sequence": batch_sequence, "total": batch_total},
            card_count=len(cards),
        )
        return self.create_task(
            controller=controller,
            task_type=ControllerTask.TaskType.DEL_WRISTBANDS,
            payload=payload,
            priority=25,
        )

    def enqueue_sync_wristbands(
        self,
        *,
        controller: Controller,
        force_full: bool = True,
        wristband_ids: list[int] | None = None,
        clear_first: bool = True,
        chunk_size: int | None = None,
        requested_by: str = "",
    ) -> list[ControllerTask]:
        return ControllerSyncService(task_service=self).plan_wristband_sync(
            controller=controller,
            force_full=force_full,
            wristband_ids=wristband_ids,
            clear_first=clear_first,
            chunk_size=chunk_size,
            requested_by=requested_by,
        )

    @staticmethod
    def _build_task_payload(
        *,
        protocol_payload: dict[str, Any],
        source: str,
        requested_by: str = "",
        **meta: Any,
    ) -> dict[str, Any]:
        payload_meta: dict[str, Any] = {"source": source}
        if requested_by:
            payload_meta["requested_by"] = requested_by
        payload_meta.update({key: value for key, value in meta.items() if value not in (None, "", [], {})})

        return {
            "protocol": protocol_payload,
            "meta": payload_meta,
        }


class ControllerTaskBatchService:
    PREFETCH_MULTIPLIER = 4

    def __init__(self, *, task_service: ControllerTaskService | None = None) -> None:
        self.task_service = task_service or ControllerTaskService()

    def build_batch(
        self,
        *,
        controller: Controller,
        max_commands: int | None = None,
        max_payload_bytes: int | None = None,
        scheduled_before: datetime | None = None,
    ) -> ControllerTaskBatch:
        effective_max_commands = max_commands or settings.IRONLOGIC_TASK_BATCH_SIZE
        effective_max_payload_bytes = max_payload_bytes or settings.IRONLOGIC_TASK_BATCH_MAX_BYTES
        # If the controller never acknowledges a previously sent batch, retry it
        # after a timeout instead of letting "sent" tasks get stuck forever.
        self.task_service.requeue_stale_sent_tasks(controller=controller)

        fetch_limit = max(effective_max_commands * self.PREFETCH_MULTIPLIER, effective_max_commands + 1)
        candidate_tasks = self.task_service.get_pending_tasks(
            controller=controller,
            limit=fetch_limit,
            scheduled_before=scheduled_before,
        )
        if not candidate_tasks:
            return ControllerTaskBatch(tasks=(), commands=[], estimated_payload_bytes=0, has_more=False)

        from apps.ironlogic_integration.response_builders import build_controller_command

        selected_tasks: list[ControllerTask] = []
        commands: list[dict[str, Any]] = []
        estimated_payload_bytes = 2
        has_more = False

        for index, task in enumerate(candidate_tasks):
            if len(selected_tasks) >= effective_max_commands:
                has_more = True
                break

            command = build_controller_command(task)
            command_size = self._estimate_command_size(command)
            next_size = estimated_payload_bytes + command_size + (1 if commands else 0)

            if commands and next_size > effective_max_payload_bytes:
                has_more = True
                break

            # Include one oversized command rather than starving it forever.
            if not commands and next_size > effective_max_payload_bytes:
                selected_tasks.append(task)
                commands.append(command)
                estimated_payload_bytes = next_size
                has_more = index < len(candidate_tasks) - 1
                break

            selected_tasks.append(task)
            commands.append(command)
            estimated_payload_bytes = next_size

        if not has_more and len(candidate_tasks) > len(selected_tasks):
            has_more = True

        return ControllerTaskBatch(
            tasks=tuple(selected_tasks),
            commands=commands,
            estimated_payload_bytes=estimated_payload_bytes if commands else 0,
            has_more=has_more,
        )

    def dispatch_pending_batch(
        self,
        *,
        controller: Controller,
        max_commands: int | None = None,
        max_payload_bytes: int | None = None,
        scheduled_before: datetime | None = None,
    ) -> ControllerTaskBatch:
        batch = self.build_batch(
            controller=controller,
            max_commands=max_commands,
            max_payload_bytes=max_payload_bytes,
            scheduled_before=scheduled_before,
        )
        if batch.tasks:
            self.task_service.mark_tasks_as_sent(batch.tasks)
        return batch

    @staticmethod
    def _estimate_command_size(command: dict[str, Any]) -> int:
        return len(json.dumps(command, separators=(",", ":"), sort_keys=True).encode("utf-8"))


class ControllerSyncService:
    def __init__(self, *, task_service: ControllerTaskService | None = None) -> None:
        self.task_service = task_service or ControllerTaskService()

    def plan_wristband_sync(
        self,
        *,
        controller: Controller,
        force_full: bool = True,
        wristband_ids: list[int] | None = None,
        clear_first: bool = True,
        chunk_size: int | None = None,
        requested_by: str = "",
    ) -> list[ControllerTask]:
        effective_chunk_size = max(1, chunk_size or settings.IRONLOGIC_SYNC_WRISTBAND_CHUNK_SIZE)
        effective_wristband_ids = wristband_ids or []
        sync_strategy = "full_sync" if force_full else "delta_sync"

        wristbands = get_wristbands_for_sync(
            wristband_ids=None if force_full else effective_wristband_ids,
        )
        addable_wristbands, removable_wristbands = self._split_wristbands_for_sync(wristbands)
        tasks: list[ControllerTask] = []

        with transaction.atomic():
            if force_full and clear_first:
                tasks.append(
                    self.task_service.enqueue_clear_cards(
                        controller=controller,
                        requested_by=requested_by,
                        sync_strategy=sync_strategy,
                        reason="full_sync_reload",
                    )
                )

            if removable_wristbands and (not force_full or not clear_first):
                tasks.extend(
                    self._enqueue_delete_batches(
                        controller=controller,
                        wristbands=removable_wristbands,
                        sync_strategy=sync_strategy,
                        chunk_size=effective_chunk_size,
                        requested_by=requested_by,
                    )
                )

            if addable_wristbands:
                tasks.extend(
                    self._enqueue_add_batches(
                        controller=controller,
                        wristbands=addable_wristbands,
                        sync_strategy=sync_strategy,
                        chunk_size=effective_chunk_size,
                        requested_by=requested_by,
                    )
                )

        return tasks

    def _enqueue_add_batches(
        self,
        *,
        controller: Controller,
        wristbands: list[Wristband],
        sync_strategy: str,
        chunk_size: int,
        requested_by: str,
    ) -> list[ControllerTask]:
        cards = [self._serialize_add_card(wristband) for wristband in wristbands]
        return self._enqueue_card_batches(
            controller=controller,
            cards=cards,
            sync_strategy=sync_strategy,
            chunk_size=chunk_size,
            requested_by=requested_by,
            batch_creator=self.task_service.enqueue_add_wristbands_batch,
        )

    def _enqueue_delete_batches(
        self,
        *,
        controller: Controller,
        wristbands: list[Wristband],
        sync_strategy: str,
        chunk_size: int,
        requested_by: str,
    ) -> list[ControllerTask]:
        cards = [self._serialize_delete_card(wristband) for wristband in wristbands]
        return self._enqueue_card_batches(
            controller=controller,
            cards=cards,
            sync_strategy=sync_strategy,
            chunk_size=chunk_size,
            requested_by=requested_by,
            batch_creator=self.task_service.enqueue_delete_wristbands_batch,
        )

    @staticmethod
    def _enqueue_card_batches(
        *,
        controller: Controller,
        cards: list[dict[str, Any]],
        sync_strategy: str,
        chunk_size: int,
        requested_by: str,
        batch_creator,
    ) -> list[ControllerTask]:
        if not cards:
            return []

        total_batches = (len(cards) + chunk_size - 1) // chunk_size
        tasks: list[ControllerTask] = []
        for index, start in enumerate(range(0, len(cards), chunk_size), start=1):
            chunk = cards[start : start + chunk_size]
            tasks.append(
                batch_creator(
                    controller=controller,
                    cards=chunk,
                    batch_sequence=index,
                    batch_total=total_batches,
                    sync_strategy=sync_strategy,
                    requested_by=requested_by,
                )
            )

        return tasks

    def _split_wristbands_for_sync(self, wristbands: Sequence[Wristband]) -> tuple[list[Wristband], list[Wristband]]:
        current_time = timezone.now()
        addable: list[Wristband] = []
        removable: list[Wristband] = []

        for wristband in wristbands:
            if self._should_exist_on_controller(wristband, current_time=current_time):
                addable.append(wristband)
            else:
                removable.append(wristband)

        return addable, removable

    @staticmethod
    def _should_exist_on_controller(wristband: Wristband, *, current_time: datetime) -> bool:
        if wristband.status != Wristband.Status.ACTIVE:
            return False

        if wristband.issued_at and current_time < wristband.issued_at:
            return False

        if wristband.expires_at and current_time > wristband.expires_at:
            return False

        person = wristband.person
        if person is None:
            return False

        if person.status != person.Status.ACTIVE:
            return False

        if person.valid_from and current_time < person.valid_from:
            return False

        if person.valid_until and current_time > person.valid_until:
            return False

        return True

    @staticmethod
    def _serialize_add_card(wristband: Wristband) -> dict[str, Any]:
        card_payload: dict[str, Any] = {
            "uid": wristband.uid,
            "person_id": wristband.person_id,
            "identifier_type": "wristband",
        }
        effective_valid_until = ControllerSyncService._get_effective_valid_until(wristband)
        if effective_valid_until is not None:
            card_payload["valid_until"] = effective_valid_until.isoformat()

        return card_payload

    @staticmethod
    def _serialize_delete_card(wristband: Wristband) -> dict[str, Any]:
        return {"uid": wristband.uid}

    @staticmethod
    def _get_effective_valid_until(wristband: Wristband) -> datetime | None:
        candidates = [value for value in [wristband.expires_at, wristband.person.valid_until if wristband.person else None] if value]
        if not candidates:
            return None
        return min(candidates)
