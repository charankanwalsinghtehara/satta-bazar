import random
import time

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.game.models import GameRound, MarketEventTemplate, MarketSettings
from apps.game.services import (
    apply_event,
    capture_daily_portfolios,
    transition_rounds,
    update_market,
)


class Command(BaseCommand):
    help = "Run the local SQLite market and game-round scheduler."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Run one price and round tick.")
        parser.add_argument("--seed", type=int, default=None, help="Optional deterministic seed.")
        parser.add_argument(
            "--event-chance",
            type=float,
            default=0.08,
            help="Probability from 0 to 1 of starting a global event on a market tick.",
        )

    def handle(self, *args, **options):
        chance = options["event_chance"]
        if not 0 <= chance <= 1:
            raise CommandError("--event-chance must be between 0 and 1.")
        rng = random.Random(options["seed"])
        tick = 0
        round_tick = 0
        interval = MarketSettings.current().price_update_interval_seconds
        next_market_update = 0.0
        next_round_update = 0.0
        last_snapshot_date = None
        self.stdout.write("Local scheduler running. Press Ctrl+C to stop.")
        while True:
            now = timezone.now()
            today = timezone.localdate(now)
            if today != last_snapshot_date:
                snapshots = capture_daily_portfolios(at=now)
                self.stdout.write(f"Captured {len(snapshots)} daily portfolio snapshot(s).")
                last_snapshot_date = today
            started_or_completed = transition_rounds(at=now)
            if started_or_completed:
                self.stdout.write(f"Completed {len(started_or_completed)} game round(s).")
            if time.monotonic() >= next_market_update:
                seed = None if options["seed"] is None else options["seed"] + tick
                updated = update_market(seed=seed, at=now)
                self.stdout.write(f"Price tick {tick + 1}: updated {len(updated)} asset(s).")
                if rng.random() < chance:
                    templates = list(
                        MarketEventTemplate.objects.filter(is_active=True).order_by("pk")
                    )
                    if templates:
                        weights = [template.rarity for template in templates]
                        template = rng.choices(templates, weights=weights, k=1)[0]
                        try:
                            apply_event(template, at=now)
                        except ValidationError as exc:
                            self.stdout.write(self.style.WARNING(f"Event skipped: {exc}"))
                tick += 1
                next_market_update = time.monotonic() + interval
                next_round_update = time.monotonic() + 1
            elif (
                time.monotonic() >= next_round_update
                and GameRound.objects.filter(status=GameRound.Status.ACTIVE).exists()
            ):
                seed = None if options["seed"] is None else options["seed"] + tick + round_tick
                update_market(seed=seed, at=now, include_persistent=False)
                round_tick += 1
                next_round_update = time.monotonic() + 1
            if options["once"]:
                break
            time.sleep(1)
