from collections.abc import Sequence

from apps.wristbands.models import Wristband


def get_wristband_by_uid(uid: str) -> Wristband | None:
    # Hot path assumes canonical uppercase UIDs in storage; write paths must keep that invariant.
    normalized_uid = uid.strip().upper()
    if not normalized_uid:
        return None

    return (
        Wristband.objects.select_related("person")
        .defer("note", "person__note")
        .filter(uid=normalized_uid)
        .first()
    )


def get_wristbands_for_sync(*, wristband_ids: Sequence[int] | None = None) -> list[Wristband]:
    queryset = Wristband.objects.select_related("person").defer("note", "person__note").order_by("id")
    if wristband_ids:
        queryset = queryset.filter(id__in=list(wristband_ids))

    return list(queryset)
