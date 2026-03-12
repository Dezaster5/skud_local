from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimeStampedModel


class Person(TimeStampedModel):
    class PersonType(models.TextChoices):
        EMPLOYEE = "employee", "Employee"
        VISITOR = "visitor", "Visitor"
        CONTRACTOR = "contractor", "Contractor"
        ADMINISTRATOR = "administrator", "Administrator"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        SUSPENDED = "suspended", "Suspended"
        ARCHIVED = "archived", "Archived"

    first_name = models.CharField(max_length=128)
    last_name = models.CharField(max_length=128)
    middle_name = models.CharField(max_length=128, blank=True)
    person_type = models.CharField(
        max_length=32,
        choices=PersonType.choices,
        default=PersonType.EMPLOYEE,
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    note = models.TextField(blank=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["last_name", "first_name", "id"]
        indexes = [
            models.Index(fields=["last_name", "first_name"], name="people_person_name_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            raise ValidationError("valid_until must be greater than or equal to valid_from.")

    def __str__(self) -> str:
        parts = [self.last_name, self.first_name, self.middle_name]
        return " ".join(part for part in parts if part)
