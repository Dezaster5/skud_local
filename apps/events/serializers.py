from rest_framework import serializers

from apps.events.models import AccessEvent


class AccessEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccessEvent
        fields = (
            "id",
            "controller",
            "access_point",
            "person",
            "wristband",
            "credential_uid",
            "event_type",
            "direction",
            "decision",
            "reason_code",
            "message",
            "occurred_at",
            "raw_payload",
            "created_at",
        )
        read_only_fields = (
            "id",
            "controller",
            "access_point",
            "person",
            "wristband",
            "credential_uid",
            "event_type",
            "direction",
            "decision",
            "reason_code",
            "message",
            "occurred_at",
            "raw_payload",
            "created_at",
        )
