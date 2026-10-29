from django.core.management.base import BaseCommand, CommandError

from apps.game.services import update_market


class Command(BaseCommand):
    help = "Run deterministic local market price ticks."

    def add_arguments(self, parser):
        parser.add_argument("--ticks", type=int, default=1)
        parser.add_argument("--seed", type=int, default=1)

    def handle(self, *args, **options):
        ticks = options["ticks"]
        if ticks < 1 or ticks > 1000:
            raise CommandError("--ticks must be between 1 and 1000.")
        changed = 0
        for tick in range(ticks):
            changed += len(update_market(seed=options["seed"] + tick))
        self.stdout.write(
            self.style.SUCCESS(f"Completed {ticks} tick(s); {changed} asset price update(s).")
        )
