from __future__ import annotations

import base64
import hashlib
from datetime import datetime

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.controllers.models import Controller, ControllerTask
from apps.controllers.services import ControllerTaskService
from apps.core.testing import create_controller, create_reader, create_wristband
from apps.events.models import AccessEvent
from apps.fondvision_integration.models import FondvisionRequestLog
from apps.fondvision_integration.services import FondvisionIngressService
from apps.fondvision_integration.views import FondvisionMCardSeaView
from apps.wristbands.models import Wristband


class FondvisionMCardSeaViewTests(TestCase):
    def setUp(self) -> None:
        self.url = reverse("fondvision-mcardsea")
        self.original_service = FondvisionMCardSeaView.service
        FondvisionMCardSeaView.service = FondvisionIngressService(
            task_service=ControllerTaskService(),
        )

    def tearDown(self) -> None:
        FondvisionMCardSeaView.service = self.original_service

    @staticmethod
    def _encrypt_qr20(text: str, password: str) -> str:
        plaintext = text.encode("utf-8")[:15].ljust(15, b"\0")
        key = hashlib.sha256(password.encode("utf-8")).digest()
        nonce = hashlib.sha256(f"{password}|nonce".encode("utf-8")).digest()[:16]
        cipher = Cipher(algorithms.AES(key), modes.CTR(nonce))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(plaintext) + encryptor.finalize()
        raw = ciphertext[:15]
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")[:20]

    def test_entry_reader_opens_door_and_sets_wristband_inside(self) -> None:
        controller = create_controller(
            serial_number="CTRL-ENTRY-01",
            controller_type=Controller.ControllerType.FONDVISION_ER80,
            ip_address="172.18.54.10",
        )
        reader = create_reader(
            controller=controller,
            name="Main Entry Reader",
            ip_address="172.18.54.12",
            external_id="H3485CB0",
            device_number=1,
            direction="entry",
        )
        wristband = create_wristband(person=None, uid="04AABBCCDD")

        response = self.client.get(
            self.url,
            {
                "cardid": wristband.uid,
                "mjihao": "1",
                "cjihao": reader.external_id,
                "status": "11",
                "time": "1773692713",
            },
            REMOTE_ADDR="172.18.54.12",
        )

        request_log = FondvisionRequestLog.objects.get()
        access_event = AccessEvent.objects.get()
        controller_task = ControllerTask.objects.get()
        wristband.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
        self.assertEqual(request_log.reader_id, reader.id)
        self.assertEqual(request_log.controller_id, controller.id)
        self.assertEqual(request_log.wristband_id, wristband.id)
        self.assertEqual(request_log.sender_ip, "172.18.54.12")
        self.assertEqual(access_event.controller_id, controller.id)
        self.assertIsNone(access_event.person_id)
        self.assertIsNone(access_event.access_point_id)
        self.assertEqual(access_event.wristband_id, wristband.id)
        self.assertEqual(access_event.event_type, AccessEvent.EventType.ACCESS_GRANTED)
        self.assertEqual(access_event.reason_code, "access_granted")
        self.assertEqual(access_event.direction, AccessEvent.Direction.ENTRY)
        self.assertEqual(controller_task.controller_id, controller.id)
        self.assertEqual(controller_task.task_type, ControllerTask.TaskType.OPEN_DOOR)
        self.assertEqual(controller_task.status, ControllerTask.Status.PENDING)
        self.assertEqual(controller_task.payload["protocol"], {"direction": 0})
        self.assertEqual(controller_task.payload["meta"]["source"], "fondvision_qr_scan")
        self.assertEqual(controller_task.payload["meta"]["reader_id"], reader.id)
        self.assertEqual(controller_task.payload["meta"]["wristband_id"], wristband.id)
        self.assertEqual(access_event.raw_payload["controller_task_id"], controller_task.id)
        self.assertEqual(wristband.presence_state, Wristband.PresenceState.INSIDE)
        self.assertEqual(
            int(access_event.occurred_at.timestamp()),
            int(datetime.fromtimestamp(1773692713).timestamp()),
        )

    def test_exit_reader_opens_door_and_sets_wristband_outside(self) -> None:
        controller = create_controller(
            serial_number="CTRL-EXIT-01",
            controller_type=Controller.ControllerType.FONDVISION_ER80,
            ip_address="172.18.54.11",
        )
        reader = create_reader(
            controller=controller,
            name="Main Exit Reader",
            ip_address="172.18.54.13",
            external_id="H3485CB1",
            device_number=2,
            direction="exit",
        )
        wristband = create_wristband(
            person=None,
            uid="04EXIT000001",
            presence_state=Wristband.PresenceState.INSIDE,
        )

        response = self.client.get(
            self.url,
            {
                "cardid": wristband.uid,
                "mjihao": "2",
                "cjihao": reader.external_id,
                "status": "11",
                "time": "1773692713",
            },
            REMOTE_ADDR="172.18.54.13",
        )

        access_event = AccessEvent.objects.get()
        controller_task = ControllerTask.objects.get()
        wristband.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(access_event.event_type, AccessEvent.EventType.ACCESS_GRANTED)
        self.assertEqual(access_event.direction, AccessEvent.Direction.EXIT)
        self.assertEqual(controller_task.payload["protocol"], {"direction": 1})
        self.assertEqual(wristband.presence_state, Wristband.PresenceState.OUTSIDE)

    def test_legacy_ip_query_param_overrides_gateway_ip(self) -> None:
        controller = create_controller(
            serial_number="CTRL-LEGACY-01",
            controller_type=Controller.ControllerType.FONDVISION_ER80,
            ip_address="172.18.54.10",
        )
        reader = create_reader(
            controller=controller,
            ip_address="172.18.12.11",
            external_id="LEGACY-R01",
            device_number=9,
        )
        wristband = create_wristband(person=None, uid="04LEGACYIP01")

        response = self.client.get(
            self.url,
            {
                "cardid": wristband.uid,
                "mjihao": "999",
                "cjihao": "UNKNOWN-READER",
                "status": "11",
                "time": "1773692713",
                "ip": "172.18.12.11",
            },
            REMOTE_ADDR="172.22.0.1",
        )

        request_log = FondvisionRequestLog.objects.get(cardid=wristband.uid)
        access_event = AccessEvent.objects.get(credential_uid=wristband.uid)
        controller_task = ControllerTask.objects.get()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(request_log.sender_ip, "172.22.0.1")
        self.assertEqual(request_log.reader_id, reader.id)
        self.assertEqual(request_log.raw_query_params["ip"], "172.18.12.11")
        self.assertEqual(access_event.event_type, AccessEvent.EventType.ACCESS_GRANTED)
        self.assertEqual(controller_task.payload["protocol"], {"direction": 0})

    def test_reader_is_resolved_by_external_id_when_sender_ip_is_masked(self) -> None:
        controller = create_controller(
            serial_number="CTRL-DOCKER-01",
            controller_type=Controller.ControllerType.FONDVISION_ER80,
            ip_address="172.18.54.10",
        )
        reader = create_reader(
            controller=controller,
            ip_address="172.18.12.11",
            external_id="H3485CB0",
            device_number=1,
        )
        wristband = create_wristband(person=None, uid="04DOCKER0001")

        response = self.client.get(
            self.url,
            {
                "cardid": wristband.uid,
                "mjihao": "1",
                "cjihao": reader.external_id,
                "status": "11",
                "time": "1773692713",
            },
            REMOTE_ADDR="172.22.0.1",
        )

        access_event = AccessEvent.objects.get(credential_uid=wristband.uid)
        controller_task = ControllerTask.objects.get()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(access_event.event_type, AccessEvent.EventType.ACCESS_GRANTED)
        self.assertEqual(access_event.raw_payload["reader_id"], reader.id)
        self.assertEqual(controller_task.payload["protocol"], {"direction": 0})

    @override_settings(
        FONDVISION_QR_PASSWORD="om9HP1LSkx2BppF3vFz32nV2YI5D/B+moxFH/6/qer4=",
        FONDVISION_QR_B_SUFFIX_REQUIRED_FROM="2026-04-10",
    )
    def test_encrypted_qr_cardid_is_decoded_before_wristband_lookup(self) -> None:
        controller = create_controller(
            serial_number="CTRL-QR-01",
            controller_type=Controller.ControllerType.FONDVISION_ER80,
            ip_address="172.18.54.10",
        )
        reader = create_reader(
            controller=controller,
            ip_address="172.18.54.12",
            external_id="H3485CB0",
            device_number=1,
        )
        decoded_cardid = "A123.456789"
        encrypted_cardid = self._encrypt_qr20(decoded_cardid, "om9HP1LSkx2BppF3vFz32nV2YI5D/B+moxFH/6/qer4=")
        wristband = create_wristband(person=None, uid=decoded_cardid)

        response = self.client.get(
            self.url,
            {
                "cardid": encrypted_cardid,
                "mjihao": "1",
                "cjihao": reader.external_id,
                "status": "11",
                "time": "1774032996",
            },
            REMOTE_ADDR="172.18.54.12",
        )

        access_event = AccessEvent.objects.get(credential_uid=decoded_cardid)
        request_log = FondvisionRequestLog.objects.get(wristband=wristband)
        controller_task = ControllerTask.objects.get()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(request_log.cardid, decoded_cardid)
        self.assertEqual(access_event.event_type, AccessEvent.EventType.ACCESS_GRANTED)
        self.assertEqual(access_event.raw_payload["raw_cardid"], encrypted_cardid)
        self.assertEqual(access_event.raw_payload["decoded_cardid"], decoded_cardid)
        self.assertEqual(controller_task.payload["protocol"], {"direction": 0})

    @override_settings(
        FONDVISION_QR_PASSWORD="om9HP1LSkx2BppF3vFz32nV2YI5D/B+moxFH/6/qer4=",
        FONDVISION_QR_B_SUFFIX_REQUIRED_FROM="2026-01-01",
    )
    def test_invalid_decrypted_qr_is_rejected(self) -> None:
        controller = create_controller(
            serial_number="CTRL-QR-02",
            controller_type=Controller.ControllerType.FONDVISION_ER80,
            ip_address="172.18.54.10",
        )
        reader = create_reader(
            controller=controller,
            ip_address="172.18.54.12",
            external_id="H3485CB0",
            device_number=1,
        )
        invalid_decoded_cardid = "A123.456789"
        encrypted_cardid = self._encrypt_qr20(invalid_decoded_cardid, "om9HP1LSkx2BppF3vFz32nV2YI5D/B+moxFH/6/qer4=")

        response = self.client.get(
            self.url,
            {
                "cardid": encrypted_cardid,
                "mjihao": "1",
                "cjihao": reader.external_id,
                "status": "11",
                "time": "1774032996",
            },
            REMOTE_ADDR="172.18.54.12",
        )

        access_event = AccessEvent.objects.get()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(access_event.event_type, AccessEvent.EventType.ACCESS_DENIED)
        self.assertEqual(access_event.reason_code, "invalid_qr_code")
        self.assertEqual(access_event.credential_uid, encrypted_cardid)
        self.assertEqual(access_event.raw_payload["decoded_cardid"], invalid_decoded_cardid)
        self.assertFalse(ControllerTask.objects.exists())

    def test_unknown_cardid_does_not_open_door(self) -> None:
        controller = create_controller(
            serial_number="CTRL-UNKNOWN-01",
            controller_type=Controller.ControllerType.FONDVISION_ER80,
            ip_address="172.18.54.10",
        )
        reader = create_reader(
            controller=controller,
            ip_address="172.18.54.12",
            external_id="H3485CB0",
            device_number=1,
        )

        response = self.client.get(
            self.url,
            {
                "cardid": "04UNKNOWN0001",
                "mjihao": "1",
                "cjihao": reader.external_id,
                "status": "11",
                "time": "1773692713",
            },
            REMOTE_ADDR="172.18.54.12",
        )

        request_log = FondvisionRequestLog.objects.get()
        access_event = AccessEvent.objects.get()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
        self.assertEqual(request_log.wristband, None)
        self.assertEqual(request_log.reader_id, reader.id)
        self.assertEqual(access_event.event_type, AccessEvent.EventType.ACCESS_DENIED)
        self.assertEqual(access_event.reason_code, "wristband_not_found")
        self.assertEqual(access_event.credential_uid, "04UNKNOWN0001")
        self.assertFalse(ControllerTask.objects.exists())

    def test_endpoint_does_not_fail_when_reader_is_unknown(self) -> None:
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
        self.assertIsNone(request_log.controller)
        self.assertIsNone(request_log.reader)
        self.assertEqual(request_log.cjihao, "HONLYDEVICE1")
        self.assertEqual(request_log.sender_ip, "172.18.12.11")
        self.assertEqual(request_log.raw_query_params, {"cjihao": "HONLYDEVICE1"})
        self.assertEqual(access_event.reason_code, "fondvision_reader_not_configured")
        self.assertEqual(access_event.credential_uid, "")
        self.assertFalse(ControllerTask.objects.exists())
