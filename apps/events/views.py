from rest_framework import filters, permissions, viewsets

from apps.events.models import AccessEvent
from apps.events.serializers import AccessEventSerializer


class AccessEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AccessEventSerializer
    permission_classes = (permissions.IsAdminUser,)
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = (
        "credential_uid",
        "reason_code",
        "message",
        "controller__serial_number",
        "access_point__code",
        "person__first_name",
        "person__last_name",
        "wristband__uid",
    )
    ordering_fields = ("created_at", "occurred_at")
    ordering = ("-created_at", "-id")

    def get_queryset(self):
        queryset = (
            AccessEvent.objects.select_related("controller", "access_point", "person", "wristband")
            .all()
            .order_by("-created_at", "-id")
        )

        controller_id = self.request.query_params.get("controller")
        if controller_id:
            queryset = queryset.filter(controller_id=controller_id)

        access_point_id = self.request.query_params.get("access_point")
        if access_point_id:
            queryset = queryset.filter(access_point_id=access_point_id)

        decision = self.request.query_params.get("decision")
        if decision:
            queryset = queryset.filter(decision=decision)

        credential_uid = self.request.query_params.get("credential_uid")
        if credential_uid:
            queryset = queryset.filter(credential_uid__iexact=credential_uid.strip())

        return queryset
