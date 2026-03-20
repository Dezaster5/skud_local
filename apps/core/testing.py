from __future__ import annotations

from datetime import time
from itertools import count

from django.conf import settings

from apps.access.models import AccessPoint, AccessPolicy, TimeZoneRule
from apps.controllers.models import Controller, Reader
from apps.people.models import Person
from apps.wristbands.models import Wristband

_UNSET = object()

_person_sequence = count(1)
_wristband_sequence = count(1)
_controller_sequence = count(1)
_reader_sequence = count(1)
_access_point_sequence = count(1)
_timezone_sequence = count(1)
_policy_sequence = count(1)


def create_person(**overrides) -> Person:
    sequence = next(_person_sequence)
    defaults = {
        "first_name": f"Test{sequence}",
        "last_name": f"Person{sequence}",
        "person_type": Person.PersonType.EMPLOYEE,
        "status": Person.Status.ACTIVE,
    }
    defaults.update(overrides)
    return Person.objects.create(**defaults)


def create_wristband(*, person=_UNSET, **overrides) -> Wristband:
    sequence = next(_wristband_sequence)
    defaults = {
        "uid": f"04TEST{sequence:06d}",
        "status": Wristband.Status.ACTIVE,
    }
    if person is _UNSET:
        defaults["person"] = create_person()
    else:
        defaults["person"] = person

    defaults.update(overrides)
    return Wristband.objects.create(**defaults)


def create_controller(**overrides) -> Controller:
    sequence = next(_controller_sequence)
    defaults = {
        "name": f"Controller {sequence}",
        "serial_number": f"Z5R-{sequence:03d}",
        "controller_type": Controller.ControllerType.IRONLOGIC_Z5R_WEB_BT,
        "status": Controller.Status.ACTIVE,
    }
    defaults.update(overrides)
    return Controller.objects.create(**defaults)


def create_access_point(*, controller=_UNSET, **overrides) -> AccessPoint:
    sequence = next(_access_point_sequence)
    defaults = {
        "code": f"point-{sequence}",
        "name": f"Access Point {sequence}",
        "status": AccessPoint.Status.ACTIVE,
        "device_port": sequence,
    }
    if controller is _UNSET:
        defaults["controller"] = create_controller()
    else:
        defaults["controller"] = controller

    defaults.update(overrides)
    return AccessPoint.objects.create(**defaults)


def create_reader(*, controller=_UNSET, **overrides) -> Reader:
    sequence = next(_reader_sequence)
    defaults = {
        "name": f"Reader {sequence}",
        "ip_address": f"172.18.200.{sequence}",
        "external_id": f"READER-{sequence:03d}",
        "device_number": sequence,
        "direction": Reader.Direction.ENTRY,
        "status": Reader.Status.ACTIVE,
    }
    if controller is _UNSET:
        defaults["controller"] = create_controller()
    else:
        defaults["controller"] = controller

    defaults.update(overrides)
    return Reader.objects.create(**defaults)


def create_timezone_rule(**overrides) -> TimeZoneRule:
    sequence = next(_timezone_sequence)
    defaults = {
        "name": f"Time Zone {sequence}",
        "timezone_name": settings.TIME_ZONE,
        "weekdays": [1, 2, 3, 4, 5, 6, 7],
        "start_time": time(0, 0, 0),
        "end_time": time(23, 59, 59),
        "is_active": True,
    }
    defaults.update(overrides)
    return TimeZoneRule.objects.create(**defaults)


def create_access_policy(*, person=_UNSET, access_point=_UNSET, **overrides) -> AccessPolicy:
    sequence = next(_policy_sequence)
    defaults = {
        "name": f"Policy {sequence}",
        "effect": AccessPolicy.Effect.ALLOW,
        "status": AccessPolicy.Status.ACTIVE,
        "priority": 100,
    }
    if person is _UNSET:
        defaults["person"] = create_person()
    else:
        defaults["person"] = person

    if access_point is _UNSET:
        defaults["access_point"] = create_access_point()
    else:
        defaults["access_point"] = access_point

    defaults.update(overrides)
    return AccessPolicy.objects.create(**defaults)
