from __future__ import annotations

from datetime import datetime

from django.test import TestCase
from django.urls import reverse

from apps.controllers.models import Controller
from apps.core.testing import create_access_point, create_controller, create_person, create_wristband
from apps.events.models import AccessEvent
from apps.fondvision_integration.models import FondvisionRequestLog


class FondvisionMCardSeaViewTests(TestCase):
    def setUp(self) -> None:
        self.url = reverse("fondvision-mcardsea")

    def test_endpoint_returns_200_and_saves_request_and_access_event(self) -> None:
        controller = create_controller(
            serial_number="H3485CB0",
            controller_type=Controller.ControllerType.GENERIC_WEB_JSON,
        )
        access_point = create_access_point(
            controller=controller,
            device_port=1,
            code="fondvision-reader-1",
        )
        person = create_person()
        wristband = create_wristband(person=person, uid="04AABBCCDD")

        response = self.client.get(
            self.url,
            {
                "cardid": wristband.uid,
                "mjihao": "1",
                "cjihao": controller.serial_number,
                "status": "11",
                "time": "1773692713",
            },
            REMOTE_ADDR="172.18.12.11",
        )

        request_log = FondvisionRequestLog.objects.get()
        access_event = AccessEvent.objects.get()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
        self.assertEqual(request_log.sender_ip, "172.18.12.11")
        self.assertEqual(
            request_log.raw_query_params,
            {
                "cardid": wristband.uid,
                "mjihao": "1",
                "cjihao": controller.serial_number,
                "status": "11",
                "time": "1773692713",
            },
        )
        self.assertEqual(request_log.controller_id, controller.id)
        self.assertEqual(request_log.wristband_id, wristband.id)
        self.assertEqual(request_log.access_event_id, access_event.id)
        self.assertEqual(request_log.cardid, wristband.uid)
        self.assertEqual(request_log.cjihao, controller.serial_number)
        self.assertEqual(access_event.controller_id, controller.id)
        self.assertEqual(access_event.access_point_id, access_point.id)
        self.assertEqual(access_event.wristband_id, wristband.id)
        self.assertEqual(access_event.person_id, person.id)
        self.assertEqual(access_event.credential_uid, wristband.uid)
        self.assertEqual(access_event.event_type, AccessEvent.EventType.ACCESS_CHECK)
        self.assertEqual(access_event.reason_code, "fondvision_mcardsea")
        self.assertEqual(
            int(access_event.occurred_at.timestamp()),
            int(datetime.fromtimestamp(1773692713).timestamp()),
        )

    def test_unknown_cjihao_creates_controller_and_links_request(self) -> None:
        response = self.client.get(
            self.url,
            {
                "cardid": "04UNKNOWN0001",
                "mjihao": "1",
                "cjihao": "H3485CB0",
                "status": "11",
                "time": "1773692713",
            },
            REMOTE_ADDR="172.18.12.11",
        )

        controller = Controller.objects.get(serial_number="H3485CB0")
        request_log = FondvisionRequestLog.objects.get()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(controller.controller_type, Controller.ControllerType.GENERIC_WEB_JSON)
        self.assertEqual(controller.ip_address, "172.18.12.11")
        self.assertEqual(request_log.controller_id, controller.id)
        self.assertIsNone(request_log.wristband)

    def test_endpoint_does_not_fail_on_incomplete_params(self) -> None:
        response = self.client.get(
            self.url,
            {
                "cjihao": "HONLYDEVICE1",
            },
            REMOTE_ADDR="172.18.12.11",
        )

        request_log = FondvisionRequestLog.objects.get()
        access_event = AccessEvent.objects.get()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
        self.assertEqual(request_log.cjihao, "HONLYDEVICE1")
        self.assertEqual(request_log.sender_ip, "172.18.12.11")
        self.assertEqual(request_log.raw_query_params, {"cjihao": "HONLYDEVICE1"})
        self.assertEqual(access_event.reason_code, "fondvision_mcardsea_incomplete")
        self.assertEqual(access_event.credential_uid, "")
