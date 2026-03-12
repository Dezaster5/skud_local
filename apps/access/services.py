from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone

from apps.access.models import AccessPoint, AccessPolicy, TimeZoneRule
from apps.access.selectors import get_active_access_policies
from apps.wristbands.services import WristbandValidationService


@dataclass(slots=True, frozen=True)
class AccessDecision:
    granted: bool
    reason_code: str
    reason_message: str
    person_id: int | None
    wristband_id: int | None


class AccessDecisionService:
    def __init__(self, *, wristband_validation_service: WristbandValidationService | None = None) -> None:
        self.wristband_validation_service = wristband_validation_service or WristbandValidationService()

    def decide(
        self,
        *,
        uid: str,
        access_point: AccessPoint,
        current_time: datetime | None = None,
    ) -> AccessDecision:
        effective_time = self._normalize_datetime(current_time)
        normalized_uid = uid.strip().upper()

        if not normalized_uid:
            return AccessDecision(
                granted=False,
                reason_code="empty_credential_uid",
                reason_message="Credential UID is empty.",
                person_id=None,
                wristband_id=None,
            )

        if access_point.status != AccessPoint.Status.ACTIVE:
            return AccessDecision(
                granted=False,
                reason_code="access_point_inactive",
                reason_message="Access point is not active.",
                person_id=None,
                wristband_id=None,
            )

        validation_result = self.wristband_validation_service.validate_uid(
            normalized_uid,
            current_time=effective_time,
        )
        if not validation_result.is_valid:
            return AccessDecision(
                granted=False,
                reason_code=validation_result.reason_code,
                reason_message=validation_result.reason_message,
                person_id=validation_result.person_id,
                wristband_id=validation_result.wristband_id,
            )

        assert validation_result.person_id is not None

        policies = get_active_access_policies(
            person_id=validation_result.person_id,
            access_point_id=access_point.id,
            current_time=effective_time,
        )
        if not policies:
            return AccessDecision(
                granted=False,
                reason_code="no_access_policy",
                reason_message="No active access policy exists for this person and access point.",
                person_id=validation_result.person_id,
                wristband_id=validation_result.wristband_id,
            )

        matched_policy, timezone_error = self._pick_matching_policy(
            policies=policies,
            current_time=effective_time,
        )
        if timezone_error is not None:
            return AccessDecision(
                granted=False,
                reason_code="invalid_timezone_rule",
                reason_message=timezone_error,
                person_id=validation_result.person_id,
                wristband_id=validation_result.wristband_id,
            )

        if matched_policy is None:
            return AccessDecision(
                granted=False,
                reason_code="outside_timezone",
                reason_message="Access is outside the allowed time window.",
                person_id=validation_result.person_id,
                wristband_id=validation_result.wristband_id,
            )

        if matched_policy.effect == AccessPolicy.Effect.DENY:
            return AccessDecision(
                granted=False,
                reason_code="access_denied_by_policy",
                reason_message=f"Access denied by policy '{matched_policy.name}'.",
                person_id=validation_result.person_id,
                wristband_id=validation_result.wristband_id,
            )

        return AccessDecision(
            granted=True,
            reason_code="access_granted",
            reason_message=f"Access granted by policy '{matched_policy.name}'.",
            person_id=validation_result.person_id,
            wristband_id=validation_result.wristband_id,
        )

    @staticmethod
    def _normalize_datetime(current_time: datetime | None) -> datetime:
        if current_time is None:
            return timezone.now()

        if timezone.is_naive(current_time):
            return timezone.make_aware(current_time, timezone.get_current_timezone())

        return current_time

    def _pick_matching_policy(
        self,
        *,
        policies: list[AccessPolicy],
        current_time: datetime,
    ) -> tuple[AccessPolicy | None, str | None]:
        policies_by_priority: dict[int, list[AccessPolicy]] = defaultdict(list)
        for policy in policies:
            policies_by_priority[policy.priority].append(policy)

        for priority in sorted(policies_by_priority):
            matched_policies: list[AccessPolicy] = []
            for policy in policies_by_priority[priority]:
                matches, timezone_error = self._policy_matches_time_window(policy=policy, current_time=current_time)
                if timezone_error is not None:
                    return None, timezone_error
                if matches:
                    matched_policies.append(policy)

            if not matched_policies:
                continue

            # Security-first rule: deny wins over allow at the same priority.
            for policy in matched_policies:
                if policy.effect == AccessPolicy.Effect.DENY:
                    return policy, None

            return matched_policies[0], None

        return None, None

    def _policy_matches_time_window(
        self,
        *,
        policy: AccessPolicy,
        current_time: datetime,
    ) -> tuple[bool, str | None]:
        if policy.timezone_rule is None:
            return True, None

        try:
            return self._timezone_rule_matches(policy.timezone_rule, current_time), None
        except ZoneInfoNotFoundError:
            return False, f"Time zone rule '{policy.timezone_rule.name}' has an invalid IANA timezone."

    @staticmethod
    def _timezone_rule_matches(rule: TimeZoneRule, current_time: datetime) -> bool:
        localized_time = timezone.localtime(current_time, ZoneInfo(rule.timezone_name))
        current_weekday = localized_time.isoweekday()
        local_wall_time = localized_time.replace(tzinfo=None).time()

        start_time = rule.start_time
        end_time = rule.end_time
        weekdays = set(rule.weekdays)

        # Windows are evaluated as [start_time, end_time). Overnight windows inherit
        # the weekday from the start of the interval, e.g. Mon 22:00-06:00 covers Tue 02:00.
        if start_time < end_time:
            return current_weekday in weekdays and start_time <= local_wall_time < end_time

        if local_wall_time >= start_time:
            return current_weekday in weekdays

        previous_weekday = 7 if current_weekday == 1 else current_weekday - 1
        return previous_weekday in weekdays and local_wall_time < end_time

