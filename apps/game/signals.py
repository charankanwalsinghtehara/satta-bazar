from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import LedgerEntry, MarketSettings, Wallet


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
@transaction.atomic
def create_player_wallet(sender, instance, created, **kwargs):
    if not created:
        return
    starting_balance = MarketSettings.current().starting_balance
    if starting_balance < 0:
        raise ValueError("STARTING_BALANCE must be non-negative.")
    wallet = Wallet.objects.create(user=instance, balance=starting_balance)
    LedgerEntry.objects.create(
        wallet=wallet,
        kind=LedgerEntry.Kind.STARTING_BALANCE,
        delta=wallet.balance,
        balance_after=wallet.balance,
        reason="Welcome to Satta Bazar: starting virtual balance",
    )
