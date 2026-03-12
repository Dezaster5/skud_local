from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ironlogic_integration.services import IronLogicWebJsonService, parse_raw_json_body


class IronLogicWebJsonAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    service = IronLogicWebJsonService()

    def post(self, request, *args, **kwargs):
        raw_body = request.body.decode("utf-8", errors="replace")
        payload = parse_raw_json_body(raw_body)

        service_response = self.service.handle(
            payload=payload,
            raw_body=raw_body,
            headers=request.headers,
            remote_addr=request.META.get("REMOTE_ADDR"),
        )
        return Response(service_response.payload, status=service_response.http_status)

