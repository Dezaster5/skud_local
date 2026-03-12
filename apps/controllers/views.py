from rest_framework import filters, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.controllers.models import Controller, ControllerTask
from apps.controllers.serializers import (
    ControllerSerializer,
    ControllerTaskSerializer,
    ManualOpenDoorTaskSerializer,
    SyncWristbandsTaskSerializer,
)
from apps.controllers.services import ControllerSyncService, ControllerTaskService


class ControllerViewSet(viewsets.ModelViewSet):
    queryset = Controller.objects.all().order_by("name", "serial_number")
    serializer_class = ControllerSerializer
    permission_classes = (permissions.IsAdminUser,)
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ("name", "serial_number", "ip_address", "firmware_version")
    ordering_fields = ("created_at", "updated_at", "name", "serial_number", "last_seen_at")
    ordering = ("name", "serial_number")
    task_service = ControllerTaskService()
    sync_service = ControllerSyncService(task_service=task_service)
    action_serializer_classes = {
        "open_door": ManualOpenDoorTaskSerializer,
        "sync_wristbands": SyncWristbandsTaskSerializer,
    }

    def get_serializer_class(self):
        return self.action_serializer_classes.get(self.action, super().get_serializer_class())

    def get_queryset(self):
        queryset = Controller.objects.all().order_by("name", "serial_number")

        status_value = self.request.query_params.get("status")
        if status_value:
            queryset = queryset.filter(status=status_value)

        controller_type = self.request.query_params.get("controller_type")
        if controller_type:
            queryset = queryset.filter(controller_type=controller_type)

        return queryset

    @action(detail=True, methods=["post"], url_path="open-door")
    def open_door(self, request: Request, pk: int | None = None) -> Response:
        controller = self.get_object()
        serializer = self.get_serializer(data=request.data, context={"controller": controller})
        serializer.is_valid(raise_exception=True)

        task = self.task_service.enqueue_manual_open(
            controller=controller,
            access_point=serializer.validated_data.get("access_point"),
            duration_seconds=serializer.validated_data["duration_seconds"],
            requested_by=request.user.get_username(),
        )
        return Response(ControllerTaskSerializer(task, context=self.get_serializer_context()).data, status=201)

    @action(detail=True, methods=["post"], url_path="sync-wristbands")
    def sync_wristbands(self, request: Request, pk: int | None = None) -> Response:
        controller = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        wristband_ids = [wristband.id for wristband in serializer.validated_data.get("wristband_ids", [])]
        tasks = self.sync_service.plan_wristband_sync(
            controller=controller,
            force_full=serializer.validated_data["force_full"],
            wristband_ids=wristband_ids,
            clear_first=serializer.validated_data["clear_first"],
            chunk_size=serializer.validated_data.get("chunk_size"),
            requested_by=request.user.get_username(),
        )
        return Response(
            {
                "total_created": len(tasks),
                "created_tasks": ControllerTaskSerializer(
                    tasks,
                    many=True,
                    context=self.get_serializer_context(),
                ).data,
            },
            status=201,
        )


class ControllerTaskViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ControllerTaskSerializer
    permission_classes = (permissions.IsAdminUser,)
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ("controller__name", "controller__serial_number", "task_type", "status")
    ordering_fields = ("created_at", "updated_at", "priority", "scheduled_for", "sent_at", "completed_at")
    ordering = ("priority", "created_at", "id")

    def get_queryset(self):
        queryset = ControllerTask.objects.select_related("controller").all().order_by("priority", "created_at", "id")

        controller_id = self.request.query_params.get("controller")
        if controller_id:
            queryset = queryset.filter(controller_id=controller_id)

        status_value = self.request.query_params.get("status")
        if status_value:
            queryset = queryset.filter(status=status_value)

        task_type = self.request.query_params.get("task_type")
        if task_type:
            queryset = queryset.filter(task_type=task_type)

        return queryset
