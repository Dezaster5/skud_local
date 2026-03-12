from django.core.management.base import BaseCommand

from apps.core.demo_data import seed_demo_data


class Command(BaseCommand):
    help = "Create or refresh idempotent demo data for local SKUD development."

    def handle(self, *args, **options) -> None:
        result = seed_demo_data()

        self.stdout.write(self.style.SUCCESS("Demo data is ready."))
        self.stdout.write(f"People: {result.people}")
        self.stdout.write(f"Wristbands: {result.wristbands}")
        self.stdout.write(f"Controllers: {result.controllers}")
        self.stdout.write(f"Access points: {result.access_points}")
        self.stdout.write(f"Access policies: {result.access_policies}")
        self.stdout.write(f"Controller tasks: {result.controller_tasks}")
        self.stdout.write(f"Access events: {result.access_events}")
        self.stdout.write(f"Audit logs: {result.audit_logs}")
