from rest_framework import serializers

from apps.people.models import Person
from apps.wristbands.models import Wristband


class WristbandSerializer(serializers.ModelSerializer):
    person = serializers.PrimaryKeyRelatedField(
        queryset=Person.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Wristband
        fields = (
            "id",
            "uid",
            "person",
            "status",
            "presence_state",
            "issued_at",
            "expires_at",
            "last_seen_at",
            "note",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "last_seen_at")

    def validate_uid(self, value: str) -> str:
        normalized_uid = value.strip().upper()
        if not normalized_uid:
            raise serializers.ValidationError("UID cannot be empty.")
        return normalized_uid


class WristbandAssignmentSerializer(serializers.Serializer):
    person_id = serializers.PrimaryKeyRelatedField(
        queryset=Person.objects.all(),
        source="person",
    )


class WristbandActionSerializer(serializers.Serializer):
    pass
