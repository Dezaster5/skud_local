from rest_framework import filters, permissions, viewsets

from apps.people.models import Person
from apps.people.serializers import PersonSerializer


class PersonViewSet(viewsets.ModelViewSet):
    queryset = Person.objects.all().order_by("last_name", "first_name", "id")
    serializer_class = PersonSerializer
    permission_classes = (permissions.IsAdminUser,)
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ("first_name", "last_name", "middle_name", "email", "phone")
    ordering_fields = ("created_at", "updated_at", "last_name", "first_name")
    ordering = ("last_name", "first_name", "id")

    def get_queryset(self):
        queryset = Person.objects.all().order_by("last_name", "first_name", "id")

        status_value = self.request.query_params.get("status")
        if status_value:
            queryset = queryset.filter(status=status_value)

        person_type = self.request.query_params.get("person_type")
        if person_type:
            queryset = queryset.filter(person_type=person_type)

        return queryset
