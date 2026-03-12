from rest_framework import filters, permissions, viewsets

from apps.access.models import AccessPoint, AccessPolicy
from apps.access.serializers import AccessPointSerializer, AccessPolicySerializer


class AccessPointViewSet(viewsets.ModelViewSet):
    queryset = AccessPoint.objects.select_related("controller").all().order_by("name", "id")
    serializer_class = AccessPointSerializer
    permission_classes = (permissions.IsAdminUser,)
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ("code", "name", "location", "controller__name", "controller__serial_number")
    ordering_fields = ("created_at", "updated_at", "name", "code", "device_port")
    ordering = ("name", "id")

    def get_queryset(self):
        queryset = AccessPoint.objects.select_related("controller").all().order_by("name", "id")

        controller_id = self.request.query_params.get("controller")
        if controller_id:
            queryset = queryset.filter(controller_id=controller_id)

        status_value = self.request.query_params.get("status")
        if status_value:
            queryset = queryset.filter(status=status_value)

        return queryset


class AccessPolicyViewSet(viewsets.ModelViewSet):
    queryset = (
        AccessPolicy.objects.select_related("person", "access_point", "timezone_rule")
        .all()
        .order_by("priority", "id")
    )
    serializer_class = AccessPolicySerializer
    permission_classes = (permissions.IsAdminUser,)
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ("name", "person__first_name", "person__last_name", "access_point__name", "access_point__code")
    ordering_fields = ("created_at", "updated_at", "priority", "valid_from", "valid_until")
    ordering = ("priority", "id")

    def get_queryset(self):
        queryset = (
            AccessPolicy.objects.select_related("person", "access_point", "timezone_rule")
            .all()
            .order_by("priority", "id")
        )

        person_id = self.request.query_params.get("person")
        if person_id:
            queryset = queryset.filter(person_id=person_id)

        access_point_id = self.request.query_params.get("access_point")
        if access_point_id:
            queryset = queryset.filter(access_point_id=access_point_id)

        status_value = self.request.query_params.get("status")
        if status_value:
            queryset = queryset.filter(status=status_value)

        return queryset
