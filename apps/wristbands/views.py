from rest_framework import filters, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.wristbands.models import Wristband
from apps.wristbands.serializers import (
    WristbandActionSerializer,
    WristbandAssignmentSerializer,
    WristbandSerializer,
)
from apps.wristbands.services import WristbandManagementService


class WristbandViewSet(viewsets.ModelViewSet):
    queryset = Wristband.objects.select_related("person").order_by("uid")
    serializer_class = WristbandSerializer
    permission_classes = (permissions.IsAdminUser,)
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ("uid", "person__first_name", "person__last_name", "person__middle_name")
    ordering_fields = ("created_at", "updated_at", "uid", "expires_at")
    ordering = ("uid",)
    management_service = WristbandManagementService()
    action_serializer_classes = {
        "assign": WristbandAssignmentSerializer,
        "unassign": WristbandActionSerializer,
        "block": WristbandActionSerializer,
        "unblock": WristbandActionSerializer,
    }

    def get_serializer_class(self):
        return self.action_serializer_classes.get(self.action, super().get_serializer_class())

    def get_queryset(self):
        queryset = Wristband.objects.select_related("person").order_by("uid")

        status_value = self.request.query_params.get("status")
        if status_value:
            queryset = queryset.filter(status=status_value)

        person_id = self.request.query_params.get("person")
        if person_id:
            queryset = queryset.filter(person_id=person_id)

        return queryset

    @action(detail=True, methods=["post"])
    def assign(self, request: Request, pk: int | None = None) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        wristband = self.management_service.assign_to_person(
            wristband=self.get_object(),
            person=serializer.validated_data["person"],
        )
        return Response(WristbandSerializer(wristband, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def unassign(self, request: Request, pk: int | None = None) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        wristband = self.management_service.unassign(wristband=self.get_object())
        return Response(WristbandSerializer(wristband, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def block(self, request: Request, pk: int | None = None) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        wristband = self.management_service.block(wristband=self.get_object())
        return Response(WristbandSerializer(wristband, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def unblock(self, request: Request, pk: int | None = None) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        wristband = self.management_service.unblock(wristband=self.get_object())
        return Response(WristbandSerializer(wristband, context=self.get_serializer_context()).data)
