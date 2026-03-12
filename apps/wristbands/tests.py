from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.core.testing import create_person, create_wristband
from apps.people.models import Person
from apps.wristbands.models import Wristband
from apps.wristbands.services import WristbandValidationService


class WristbandValidationServiceTests(TestCase):
    def setUp(self) -> None:
        self.service = WristbandValidationService()

    def test_validate_uid_returns_valid_result_for_active_wristband(self) -> None:
        person = create_person()
        wristband = create_wristband(person=person)

        result = self.service.validate_uid(wristband.uid)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.reason_code, "ok")
        self.assertEqual(result.person_id, person.id)
        self.assertEqual(result.wristband_id, wristband.id)

    def test_validate_uid_returns_not_found_for_unknown_uid(self) -> None:
        result = self.service.validate_uid("04UNKNOWN0001")

        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason_code, "wristband_not_found")

    def test_validate_uid_returns_blocked_for_blocked_wristband(self) -> None:
        wristband = create_wristband(status=Wristband.Status.BLOCKED)

        result = self.service.validate_uid(wristband.uid)

        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason_code, "wristband_blocked")
        self.assertEqual(result.wristband_id, wristband.id)

    def test_validate_uid_returns_person_inactive_when_holder_is_inactive(self) -> None:
        person = create_person(status=Person.Status.INACTIVE)
        wristband = create_wristband(person=person)

        result = self.service.validate_uid(wristband.uid)

        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason_code, "person_inactive")
        self.assertEqual(result.person_id, person.id)

    def test_validate_uid_returns_expired_when_wristband_is_expired(self) -> None:
        wristband = create_wristband(expires_at=timezone.now() - timedelta(minutes=1))

        result = self.service.validate_uid(wristband.uid)

        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason_code, "wristband_expired")

    def test_validate_uid_returns_unassigned_when_wristband_has_no_person(self) -> None:
        wristband = create_wristband(person=None, uid="04UNASSIGNED1")

        result = self.service.validate_uid(wristband.uid)

        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason_code, "wristband_unassigned")
        self.assertEqual(result.wristband_id, wristband.id)
