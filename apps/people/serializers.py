from rest_framework import serializers

from apps.people.models import Person


class PersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = (
            "id",
            "first_name",
            "last_name",
            "middle_name",
            "person_type",
            "status",
            "email",
            "phone",
            "note",
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

