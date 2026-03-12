from __future__ import annotations

from datetime import time

from django.test import TestCase
from django.utils import timezone

from apps.access.models import AccessPolicy
from apps.access.services import AccessDecisionService
from apps.core.testing import (
    create_access_point,
    create_access_policy,
    create_controller,
    create_person,
    create_timezone_rule,
    create_wristband,
)


class AccessDecisionServiceTests(TestCase):
    def setUp(self) -> None:
        self.service = AccessDecisionService()
        self.controller = create_controller()
        self.access_point = create_access_point(controller=self.controller, code="main-entry", device_port=1)

    def test_decide_grants_access_for_valid_wristband_and_policy(self) -> None:
        person = create_person()
        wristband = create_wristband(person=person)
        create_access_policy(person=person, access_point=self.access_point)

        decision = self.service.decide(uid=wristband.uid, access_point=self.access_point)

        self.assertTrue(decision.granted)
        self.assertEqual(decision.reason_code, "access_granted")
        self.assertEqual(decision.person_id, person.id)

    def test_decide_denies_when_wristband_is_not_found(self) -> None:
        decision = self.service.decide(uid="04NOTFOUND", access_point=self.access_point)

        self.assertFalse(decision.granted)
        self.assertEqual(decision.reason_code, "wristband_not_found")

    def test_decide_denies_when_no_policy_exists(self) -> None:
        person = create_person()
        wristband = create_wristband(person=person)

        decision = self.service.decide(uid=wristband.uid, access_point=self.access_point)

        self.assertFalse(decision.granted)
        self.assertEqual(decision.reason_code, "no_access_policy")

    def test_decide_denies_outside_timezone_window(self) -> None:
        now = timezone.localtime(timezone.now())
        current_weekday = now.isoweekday()
        denied_weekday = 1 if current_weekday != 1 else 2

        person = create_person()
        wristband = create_wristband(person=person)
        timezone_rule = create_timezone_rule(
            weekdays=[denied_weekday],
            start_time=time(8, 0, 0),
            end_time=time(18, 0, 0),
        )
        create_access_policy(
            person=person,
            access_point=self.access_point,
            timezone_rule=timezone_rule,
        )

        decision = self.service.decide(uid=wristband.uid, access_point=self.access_point)

        self.assertFalse(decision.granted)
        self.assertEqual(decision.reason_code, "outside_timezone")

    def test_decide_prefers_deny_policy_over_allow_with_same_priority(self) -> None:
        person = create_person()
        wristband = create_wristband(person=person)
        create_access_policy(
            person=person,
            access_point=self.access_point,
            name="allow-main-entry",
            effect=AccessPolicy.Effect.ALLOW,
            priority=50,
        )
        create_access_policy(
            person=person,
            access_point=self.access_point,
            name="deny-main-entry",
            effect=AccessPolicy.Effect.DENY,
            priority=50,
        )

        decision = self.service.decide(uid=wristband.uid, access_point=self.access_point)

        self.assertFalse(decision.granted)
        self.assertEqual(decision.reason_code, "access_denied_by_policy")
