from __future__ import annotations

from datetime import datetime

from django.db.models import Q

from apps.access.models import AccessPoint, AccessPolicy


def get_active_access_policies(
    *,
    person_id: int,
    access_point_id: int,
    current_time: datetime,
) -> list[AccessPolicy]:
    queryset = (
        AccessPolicy.objects.filter(
            person_id=person_id,
            access_point_id=access_point_id,
            status=AccessPolicy.Status.ACTIVE,
        )
        .filter(Q(timezone_rule__isnull=True) | Q(timezone_rule__is_active=True))
        .filter(Q(valid_from__isnull=True) | Q(valid_from__lte=current_time))
        .filter(Q(valid_until__isnull=True) | Q(valid_until__gte=current_time))
        .select_related("timezone_rule")
        .order_by("priority", "id")
    )

    return list(queryset)


def get_active_access_point_for_controller(
    *,
    controller_id: int,
    access_point_code: str | None = None,
    device_port: int | None = None,
) -> AccessPoint | None:
    queryset = AccessPoint.objects.filter(
        controller_id=controller_id,
        status=AccessPoint.Status.ACTIVE,
    ).order_by("id")

    if access_point_code:
        normalized_code = access_point_code.strip().lower()
        if not normalized_code:
            return None
        return queryset.filter(code=normalized_code).first()

    if device_port is not None:
        return queryset.filter(device_port=device_port).first()

    access_points = list(queryset[:2])
    if len(access_points) == 1:
        return access_points[0]
    return None
