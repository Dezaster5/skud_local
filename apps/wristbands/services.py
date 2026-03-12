from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.utils import timezone

from apps.people.models import Person
from apps.wristbands.models import Wristband
from apps.wristbands.selectors import get_wristband_by_uid


@dataclass(slots=True, frozen=True)
class WristbandValidationResult:
    is_valid: bool
    reason_code: str
    reason_message: str
    person_id: int | None
    wristband_id: int | None
    person: Person | None = None
    wristband: Wristband | None = None


class WristbandValidationService:
    def validate_uid(self, uid: str, *, current_time: datetime | None = None) -> WristbandValidationResult:
        wristband = get_wristband_by_uid(uid)
        return self.validate_wristband(wristband, current_time=current_time)

    def validate_wristband(
        self,
        wristband: Wristband | None,
        *,
        current_time: datetime | None = None,
    ) -> WristbandValidationResult:
        effective_time = self._normalize_datetime(current_time)

        if wristband is None:
            return self._invalid_result(
                reason_code="wristband_not_found",
                reason_message="Wristband was not found.",
            )

        if wristband.status != Wristband.Status.ACTIVE:
            return self._invalid_result(
                reason_code=f"wristband_{wristband.status}",
                reason_message=f"Wristband status is {wristband.get_status_display().lower()}.",
                wristband=wristband,
            )

        if wristband.issued_at and effective_time < wristband.issued_at:
            return self._invalid_result(
                reason_code="wristband_not_yet_active",
                reason_message="Wristband validity period has not started yet.",
                wristband=wristband,
            )

        if wristband.expires_at and effective_time > wristband.expires_at:
            return self._invalid_result(
                reason_code="wristband_expired",
                reason_message="Wristband validity period has expired.",
                wristband=wristband,
            )

        person = wristband.person
        if person is None:
            return self._invalid_result(
                reason_code="wristband_unassigned",
                reason_message="Wristband is not assigned to a person.",
                wristband=wristband,
            )

        if person.status != Person.Status.ACTIVE:
            return self._invalid_result(
                reason_code=f"person_{person.status}",
                reason_message=f"Person status is {person.get_status_display().lower()}.",
                wristband=wristband,
                person=person,
            )

        if person.valid_from and effective_time < person.valid_from:
            return self._invalid_result(
                reason_code="person_not_yet_active",
                reason_message="Person validity period has not started yet.",
                wristband=wristband,
                person=person,
            )

        if person.valid_until and effective_time > person.valid_until:
            return self._invalid_result(
                reason_code="person_expired",
                reason_message="Person validity period has expired.",
                wristband=wristband,
                person=person,
            )

        return WristbandValidationResult(
            is_valid=True,
            reason_code="ok",
            reason_message="Wristband is valid for access policy evaluation.",
            person_id=person.id,
            wristband_id=wristband.id,
            person=person,
            wristband=wristband,
        )

    @staticmethod
    def _normalize_datetime(current_time: datetime | None) -> datetime:
        if current_time is None:
            return timezone.now()

        if timezone.is_naive(current_time):
            return timezone.make_aware(current_time, timezone.get_current_timezone())

        return current_time

    @staticmethod
    def _invalid_result(
        *,
        reason_code: str,
        reason_message: str,
        wristband: Wristband | None = None,
        person: Person | None = None,
    ) -> WristbandValidationResult:
        return WristbandValidationResult(
            is_valid=False,
            reason_code=reason_code,
            reason_message=reason_message,
            person_id=person.id if person else wristband.person_id if wristband else None,
            wristband_id=wristband.id if wristband else None,
            person=person,
            wristband=wristband,
        )


class WristbandManagementService:
    def assign_to_person(self, *, wristband: Wristband, person: Person) -> Wristband:
        wristband.person = person
        wristband.save()
        return wristband

    def unassign(self, *, wristband: Wristband) -> Wristband:
        wristband.person = None
        wristband.save()
        return wristband

    def block(self, *, wristband: Wristband) -> Wristband:
        wristband.status = Wristband.Status.BLOCKED
        wristband.save()
        return wristband

    def unblock(self, *, wristband: Wristband) -> Wristband:
        wristband.status = Wristband.Status.ACTIVE
        wristband.save()
        return wristband
