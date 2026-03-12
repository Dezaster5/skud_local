from django.core.management.base import BaseCommand, CommandError

from apps.controllers.models import Controller
from apps.controllers.services import ControllerSyncService


class Command(BaseCommand):
    help = "Queue wristband synchronization tasks for a controller."

    def add_arguments(self, parser) -> None:
        controller_group = parser.add_mutually_exclusive_group(required=True)
        controller_group.add_argument("--controller-id", type=int)
        controller_group.add_argument("--serial-number", type=str)

        parser.add_argument(
            "--force-full",
            action="store_true",
            help="Queue a full controller reload: clear cards first, then re-add active wristbands.",
        )
        parser.add_argument(
            "--wristband-id",
            action="append",
            dest="wristband_ids",
            type=int,
            default=[],
            help="Specific wristband IDs for delta sync. Repeat the option to pass multiple IDs.",
        )
        parser.add_argument(
            "--no-clear-first",
            action="store_true",
            help="Do not enqueue clear_cards before a full sync.",
        )
        parser.add_argument(
            "--chunk-size",
            type=int,
            default=None,
            help="Override the number of wristbands per add/del task batch.",
        )
        parser.add_argument(
            "--requested-by",
            type=str,
            default="management_command",
            help="Free-form operator label stored in task payload metadata.",
        )

    def handle(self, *args, **options) -> None:
        controller = self._get_controller(
            controller_id=options.get("controller_id"),
            serial_number=options.get("serial_number"),
        )
        wristband_ids: list[int] = options["wristband_ids"]
        force_full = bool(options["force_full"] or not wristband_ids)

        if not force_full and not wristband_ids:
            raise CommandError("Provide at least one --wristband-id for delta sync or use --force-full.")

        if force_full and wristband_ids:
            raise CommandError("Do not pass --wristband-id together with --force-full.")

        sync_service = ControllerSyncService()
        tasks = sync_service.plan_wristband_sync(
            controller=controller,
            force_full=force_full,
            wristband_ids=wristband_ids,
            clear_first=not options["no_clear_first"],
            chunk_size=options["chunk_size"],
            requested_by=options["requested_by"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Queued {len(tasks)} task(s) for controller {controller.serial_number}."
            )
        )
        for task in tasks:
            self.stdout.write(
                f"- task_id={task.id} type={task.task_type} priority={task.priority} status={task.status}"
            )

    @staticmethod
    def _get_controller(*, controller_id: int | None, serial_number: str | None) -> Controller:
        if controller_id is not None:
            controller = Controller.objects.filter(id=controller_id).first()
        else:
            normalized_serial_number = (serial_number or "").strip().upper()
            controller = Controller.objects.filter(serial_number=normalized_serial_number).first()

        if controller is None:
            raise CommandError("Controller was not found.")

        return controller
