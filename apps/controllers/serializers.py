from rest_framework import serializers

from apps.access.models import AccessPoint
from apps.controllers.models import Controller, ControllerTask
from apps.wristbands.models import Wristband


class ControllerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Controller
        fields = (
            "id",
            "name",
            "serial_number",
            "controller_type",
            "status",
            "ip_address",
            "firmware_version",
            "connection_firmware_version",
            "active_state",
            "mode_state",
            "last_auth_hash",
            "description",
            "last_seen_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "last_seen_at",
            "firmware_version",
            "connection_firmware_version",
            "active_state",
            "mode_state",
            "last_auth_hash",
        )

    def validate_serial_number(self, value: str) -> str:
        normalized_serial_number = value.strip().upper()
        if not normalized_serial_number:
            raise serializers.ValidationError("Serial number cannot be empty.")
        return normalized_serial_number


class ControllerTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = ControllerTask
        fields = (
            "id",
            "controller",
            "task_type",
            "status",
            "payload",
            "priority",
            "attempts",
            "error_message",
            "scheduled_for",
            "sent_at",
            "completed_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "controller",
            "task_type",
            "status",
            "payload",
            "priority",
            "attempts",
            "error_message",
            "scheduled_for",
            "sent_at",
            "completed_at",
            "created_at",
            "updated_at",
        )


class ManualOpenDoorTaskSerializer(serializers.Serializer):
    access_point_id = serializers.PrimaryKeyRelatedField(
        queryset=AccessPoint.objects.select_related("controller").all(),
        source="access_point",
        allow_null=True,
        required=False,
    )
    duration_seconds = serializers.IntegerField(min_value=1, max_value=30, default=3)

    def validate(self, attrs: dict) -> dict:
        access_point = attrs.get("access_point")
        controller: Controller = self.context["controller"]
        if access_point is not None and access_point.controller_id != controller.id:
            raise serializers.ValidationError("The selected access point does not belong to this controller.")
        return attrs


class SetDoorParamsTaskSerializer(serializers.Serializer):
    open = serializers.IntegerField(min_value=0, max_value=255)
    open_control = serializers.IntegerField(min_value=0, max_value=255)
    close_control = serializers.IntegerField(min_value=0, max_value=255)


class ReadCardsTaskSerializer(serializers.Serializer):
    pass


class SyncWristbandsTaskSerializer(serializers.Serializer):
    force_full = serializers.BooleanField(default=True)
    clear_first = serializers.BooleanField(required=False)
    chunk_size = serializers.IntegerField(min_value=1, max_value=1000, required=False)
    wristband_ids = serializers.PrimaryKeyRelatedField(
        queryset=Wristband.objects.all(),
        many=True,
        required=False,
    )

    def validate(self, attrs: dict) -> dict:
        force_full = attrs.get("force_full", True)
        clear_first = attrs.get("clear_first", force_full)
        wristband_ids = attrs.get("wristband_ids", [])

        if force_full and wristband_ids:
            raise serializers.ValidationError("wristband_ids are not allowed when force_full is true.")

        if not force_full and not wristband_ids:
            raise serializers.ValidationError("Provide wristband_ids when force_full is false.")

        if not force_full and clear_first:
            raise serializers.ValidationError("clear_first can only be used when force_full is true.")

        attrs["clear_first"] = clear_first
        return attrs
