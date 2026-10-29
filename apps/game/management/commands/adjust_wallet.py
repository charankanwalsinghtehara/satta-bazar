from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.game.models import Wallet
from apps.game.services import adjust_wallet


class Command(BaseCommand):
    help = "Make an audited virtual-wallet adjustment as an existing staff user."

    def add_arguments(self, parser):
        parser.add_argument("--actor", required=True, help="Username of a staff administrator.")
        parser.add_argument("--wallet", required=True, help="UUID of the wallet to adjust.")
        parser.add_argument("--amount", required=True, help="Signed amount in virtual BB.")
        parser.add_argument("--reason", required=True, help="Audit reason for this adjustment.")

    def handle(self, *args, **options):
        user_model = get_user_model()
        actor = user_model.objects.filter(username=options["actor"], is_staff=True).first()
        if actor is None:
            raise CommandError("The specified actor must be an existing staff user.")
        wallet = Wallet.objects.filter(pk=options["wallet"]).first()
        if wallet is None:
            raise CommandError("Wallet not found.")
        try:
            adjustment = adjust_wallet(actor, wallet.pk, options["amount"], options["reason"])
        except ValidationError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"Recorded adjustment {adjustment.ledger_entry.delta} BB for "
                f"{wallet.user.username}: {adjustment.reason}"
            )
        )
