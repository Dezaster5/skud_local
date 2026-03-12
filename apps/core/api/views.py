from django.db import connections
from django.db.utils import OperationalError
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_safe


@require_safe
def live_health_view(request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        {
            "status": "ok",
            "service": "skud_local",
            "checks": {"application": "ok"},
        }
    )


@require_safe
def ready_health_view(request: HttpRequest) -> JsonResponse:
    try:
        connection = connections["default"]
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except OperationalError:
        return JsonResponse(
            {
                "status": "error",
                "service": "skud_local",
                "checks": {"database": "error"},
            },
            status=503,
        )

    return JsonResponse(
        {
            "status": "ok",
            "service": "skud_local",
            "checks": {"database": "ok"},
        }
    )

