from __future__ import annotations

from ipaddress import ip_address

from django.http import HttpRequest, HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from apps.fondvision_integration.services import FondvisionIngressService


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(require_GET, name="dispatch")
class FondvisionMCardSeaView(View):
    service = FondvisionIngressService()

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        result = self.service.handle_request(
            query_params=request.GET,
            request_path=request.path,
            query_string=request.META.get("QUERY_STRING", ""),
            request_body=request.body.decode("utf-8", errors="replace"),
            sender_ip=self._get_sender_ip(request),
        )
        return HttpResponse(result.response_text, content_type="text/plain")

    @staticmethod
    def _get_sender_ip(request: HttpRequest) -> str | None:
        for header_name in ("HTTP_X_FORWARDED_FOR", "HTTP_CLIENT_IP", "REMOTE_ADDR"):
            raw_value = request.META.get(header_name, "")
            if not raw_value:
                continue

            sender_ip = raw_value.split(",")[0].strip()
            if not sender_ip:
                continue

            try:
                ip_address(sender_ip)
                return sender_ip
            except ValueError:
                continue

        return None
