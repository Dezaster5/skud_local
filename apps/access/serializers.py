from rest_framework import serializers

from apps.access.models import AccessPoint, AccessPolicy, TimeZoneRule
from apps.controllers.models import Controller
from apps.people.models import Person


class AccessPointSerializer(serializers.ModelSerializer):
    controller = serializers.PrimaryKeyRelatedField(queryset=Controller.objects.all())

    class Meta:
        model = AccessPoint
        fields = (
            "id",
            "code",
            "name",
            "controller",
            "direction",
            "status",
            "device_port",
            "location",
            "description",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_code(self, value: str) -> str:
        normalized_code = value.strip().lower()
        if not normalized_code:
            raise serializers.ValidationError("Code cannot be empty.")
        return normalized_code


class AccessPolicySerializer(serializers.ModelSerializer):
    person = serializers.PrimaryKeyRelatedField(queryset=Person.objects.all())
    access_point = serializers.PrimaryKeyRelatedField(queryset=AccessPoint.objects.all())
    timezone_rule = serializers.PrimaryKeyRelatedField(
        queryset=TimeZoneRule.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = AccessPolicy
        fields = (
            "id",
            "name",
            "description",
            "person",
            "access_point",
            "timezone_rule",
            "effect",
            "status",
            "priority",
            "valid_from",
            "valid_until",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs: dict) -> dict:
        valid_from = attrs.get("valid_from", getattr(self.instance, "valid_from", None))
        valid_until = attrs.get("valid_until", getattr(self.instance, "valid_until", None))
        if valid_from and valid_until and valid_until < valid_from:
            raise serializers.ValidationError("valid_until must be greater than or equal to valid_from.")
        return attrs
