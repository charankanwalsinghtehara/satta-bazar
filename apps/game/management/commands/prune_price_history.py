from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.game.models import PriceSnapshot, RoundPriceSnapshot


class Command(BaseCommand):
    help = "Prune persistent and round price snapshots older than a retention window."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30)

    def handle(self, *args, **options):
        days = options["days"]
        if days < 1:
            raise CommandError("--days must be at least one.")
        cutoff = timezone.now() - timedelta(days=days)
        persistent_count, _ = PriceSnapshot.objects.filter(created_at__lt=cutoff).delete()
        round_count, _ = RoundPriceSnapshot.objects.filter(created_at__lt=cutoff).delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Pruned {persistent_count} persistent and {round_count} round price snapshots."
            )
        )
