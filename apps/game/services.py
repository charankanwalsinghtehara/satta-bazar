import random
import re
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from .models import (
    Asset,
    AuditEvent,
    DailyRewardClaim,
    GameRound,
    LedgerEntry,
    MarketEvent,
    MarketEventTemplate,
    MarketSettings,
    Position,
    PriceSnapshot,
    RoundAssetState,
    RoundPriceSnapshot,
    Trade,
    UserMission,
    Wallet,
    WalletAdjustment,
)

CENT = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")


def _publish(group, payload):
    async_to_sync(get_channel_layer().group_send)(
        group, {"type": "market.message", "payload": payload}
    )


def money(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def validate_event_effects(effects):
    if not isinstance(effects, dict):
        raise ValidationError("Event effects must be a mapping of asset symbols to fractions.")
    for symbol, effect in effects.items():
        if not isinstance(symbol, str) or not re.fullmatch(r"[A-Z0-9]{2,12}", symbol):
            raise ValidationError(f"Invalid asset symbol in event effects: {symbol!r}.")
        if isinstance(effect, bool):
            raise ValidationError("Event effect fractions must be numbers.")
        try:
            number = Decimal(str(effect))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValidationError(f"Invalid effect for {symbol}.") from exc
        if not number.is_finite() or number < Decimal("-0.5") or number > Decimal("0.5"):
            raise ValidationError("Event effect fractions must be between -0.5 and 0.5.")


def _lock_wallet(user):
    Wallet.objects.get_or_create(
        user=user,
        defaults={"balance": MarketSettings.current().starting_balance},
    )
    return Wallet.objects.select_for_update().get(user=user)


def _write_ledger(wallet, kind, delta, reason, idempotency_key=""):
    balance = money(wallet.balance + delta)
    if balance < 0:
        raise ValidationError({"detail": "Insufficient Bazar Bucks."})
    wallet.balance = balance
    wallet.save(update_fields=["balance", "updated_at"])
    return LedgerEntry.objects.create(
        wallet=wallet,
        kind=kind,
        delta=money(delta),
        balance_after=balance,
        reason=reason,
        idempotency_key=idempotency_key,
    )


@transaction.atomic
def execute_trade(user, symbol, side, quantity, idempotency_key):
    if not idempotency_key or len(idempotency_key) > 100:
        raise ValidationError({"idempotency_key": "A key of 1-100 characters is required."})
    try:
        quantity = Decimal(str(quantity))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError({"quantity": "Enter a valid decimal quantity."}) from exc
    if not quantity.is_finite() or quantity <= 0 or quantity != quantity.quantize(FOUR_PLACES):
        raise ValidationError({"quantity": "Quantity must be positive with at most 4 decimals."})
    if side not in (Trade.Side.BUY, Trade.Side.SELL):
        raise ValidationError({"side": "Side must be buy or sell."})

    previous = Trade.objects.filter(user=user, idempotency_key=idempotency_key).first()
    if previous:
        if (
            previous.asset.symbol != symbol.upper()
            or previous.side != side
            or previous.quantity != quantity
        ):
            raise ValidationError(
                {"idempotency_key": "This key was already used for a different trade."}
            )
        return previous

    settings_row = MarketSettings.current()
    if quantity > settings_row.max_trade_quantity:
        raise ValidationError({"quantity": "Quantity exceeds the configured trade limit."})
    asset = Asset.objects.select_for_update().filter(symbol=symbol.upper(), is_active=True).first()
    if asset is None:
        raise ValidationError({"asset": "Asset was not found or is inactive."})

    wallet = _lock_wallet(user)
    previous = Trade.objects.filter(user=user, idempotency_key=idempotency_key).first()
    if previous:
        if previous.asset_id != asset.pk or previous.side != side or previous.quantity != quantity:
            raise ValidationError(
                {"idempotency_key": "This key was already used for a different trade."}
            )
        return previous
    position, _ = Position.objects.get_or_create(
        user=user, asset=asset, defaults={"quantity": Decimal("0")}
    )
    position = Position.objects.select_for_update().get(pk=position.pk)
    price = money(asset.current_price)
    gross = money(price * quantity)
    fee = money(gross * settings_row.trade_fee_fraction)

    if side == Trade.Side.BUY:
        _write_ledger(
            wallet,
            LedgerEntry.Kind.BUY,
            -(gross + fee),
            f"Bought {quantity} {asset.symbol}",
            f"trade:{idempotency_key}",
        )
        existing_cost = position.average_entry_price * position.quantity
        position.quantity += quantity
        position.average_entry_price = money((existing_cost + gross + fee) / position.quantity)
        realized = Decimal("0.00")
    else:
        if position.quantity < quantity:
            raise ValidationError({"quantity": "You do not own enough units to sell."})
        realized = money((price - position.average_entry_price) * quantity - fee)
        _write_ledger(
            wallet,
            LedgerEntry.Kind.SELL,
            gross - fee,
            f"Sold {quantity} {asset.symbol}",
            f"trade:{idempotency_key}",
        )
        position.quantity -= quantity
        position.realized_pnl += realized
        if position.quantity == 0:
            position.average_entry_price = Decimal("0.00")

    position.save()
    trade = Trade.objects.create(
        user=user,
        asset=asset,
        side=side,
        quantity=quantity,
        price=price,
        gross_amount=gross,
        fee=fee,
        realized_pnl=realized,
        idempotency_key=idempotency_key,
    )
    _advance_missions(user, asset, side)
    awarded = _award_trade_achievements(user, trade)
    AuditEvent.objects.create(
        actor=user,
        action=f"trade.{side}",
        object_type="Trade",
        object_id=str(trade.pk),
        details={"symbol": asset.symbol, "quantity": str(quantity), "price": str(price)},
    )
    market_value = sum(
        (
            money(row.quantity * row.asset.current_price)
            for row in Position.objects.filter(user=user, quantity__gt=0).select_related("asset")
        ),
        Decimal("0.00"),
    )
    from .models import PortfolioSnapshot

    PortfolioSnapshot.objects.create(
        user=user,
        cash_balance=wallet.balance,
        market_value=market_value,
        equity=money(wallet.balance + market_value),
    )
    transaction.on_commit(
        lambda: _publish(
            f"satta_user_{user.pk.hex}",
            {
                "type": "trade.confirmation",
                "trade_id": str(trade.pk),
                "symbol": asset.symbol,
                "side": side,
                "quantity": str(quantity),
                "price": str(price),
                "wallet_balance": str(wallet.balance),
            },
        )
    )
    portfolio_payload = {
        "type": "portfolio.update",
        "cash_balance": str(wallet.balance),
        "market_value": str(market_value),
        "equity": str(money(wallet.balance + market_value)),
    }
    transaction.on_commit(lambda: _publish(f"satta_user_{user.pk.hex}", portfolio_payload))
    for achievement in awarded:
        achievement_payload = {
            "type": "achievement.unlocked",
            "code": achievement.code,
            "name": achievement.name,
            "xp_reward": achievement.xp_reward,
        }
        transaction.on_commit(
            lambda payload=achievement_payload: _publish(f"satta_user_{user.pk.hex}", payload)
        )
    return trade


def _award_trade_achievements(user, trade):
    from .models import Achievement, UserAchievement

    completed_trades = Trade.objects.filter(user=user).count()
    codes = []
    if completed_trades >= 1:
        codes.append("first-trade")
    if completed_trades >= 5:
        codes.append("five-trades")
    if trade.side == Trade.Side.SELL and trade.realized_pnl > 0:
        codes.append("first-profit")
    awarded = []
    for achievement in Achievement.objects.filter(code__in=codes):
        _, created = UserAchievement.objects.get_or_create(user=user, achievement=achievement)
        if created:
            awarded.append(achievement)
    return awarded


def _advance_missions(user, asset, side):
    now = timezone.now()
    from .models import Mission

    active_missions = Mission.objects.filter(
        is_active=True, active_from__lte=now, active_until__gt=now
    )
    for mission in active_missions:
        if mission.trigger == Mission.Trigger.BUY_ASSET and (
            side != Trade.Side.BUY or mission.target_symbol != asset.symbol
        ):
            continue
        UserMission.objects.get_or_create(user=user, mission=mission)
    missions = UserMission.objects.select_for_update().filter(
        user=user,
        claimed_at__isnull=True,
        mission__is_active=True,
        mission__active_from__lte=now,
        mission__active_until__gt=now,
        mission__trigger=Mission.Trigger.TRADE,
        progress__lt=F("mission__target"),
    )
    for assignment in missions:
        assignment.progress = min(assignment.progress + 1, assignment.mission.target)
        assignment.save(update_fields=["progress"])
    if side == Trade.Side.BUY:
        for assignment in UserMission.objects.select_for_update().filter(
            user=user,
            mission__trigger=Mission.Trigger.BUY_ASSET,
            mission__target_symbol=asset.symbol,
            claimed_at__isnull=True,
            mission__is_active=True,
            mission__active_from__lte=now,
            mission__active_until__gt=now,
            progress__lt=F("mission__target"),
        ):
            assignment.progress = min(assignment.progress + 1, assignment.mission.target)
            assignment.save(update_fields=["progress"])


@transaction.atomic
def claim_daily_reward(user):
    wallet = _lock_wallet(user)
    claim_date = timezone.localdate()
    existing = (
        DailyRewardClaim.objects.filter(wallet=wallet, claim_date=claim_date)
        .select_related("ledger_entry")
        .first()
    )
    if existing:
        return existing, False
    reward = money(MarketSettings.current().daily_reward)
    entry = _write_ledger(
        wallet,
        LedgerEntry.Kind.DAILY_REWARD,
        reward,
        "Daily login reward",
        f"daily:{claim_date.isoformat()}",
    )
    try:
        with transaction.atomic():
            claim = DailyRewardClaim.objects.create(
                wallet=wallet, claim_date=claim_date, ledger_entry=entry
            )
    except IntegrityError:
        claim = DailyRewardClaim.objects.select_related("ledger_entry").get(
            wallet=wallet, claim_date=claim_date
        )
        return claim, False
    transaction.on_commit(
        lambda: _publish(
            f"satta_user_{user.pk.hex}",
            {
                "type": "reward.claimed",
                "kind": "daily",
                "amount": str(reward),
                "balance": str(wallet.balance),
            },
        )
    )
    return claim, True


@transaction.atomic
def adjust_wallet(actor, wallet_id, amount, reason):
    if not actor.is_staff:
        raise ValidationError("Only staff can make wallet adjustments.")
    if not reason or not reason.strip():
        raise ValidationError("An adjustment reason is required.")
    try:
        delta = money(amount)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError("Enter a valid adjustment amount.") from exc
    if not delta:
        raise ValidationError("Adjustment amount cannot be zero.")
    wallet = Wallet.objects.select_for_update().get(pk=wallet_id)
    entry = _write_ledger(
        wallet,
        LedgerEntry.Kind.ADMIN_ADJUSTMENT,
        delta,
        reason.strip()[:200],
    )
    adjustment = WalletAdjustment.objects.create(
        wallet=wallet,
        ledger_entry=entry,
        adjusted_by=actor,
        reason=reason.strip(),
    )
    AuditEvent.objects.create(
        actor=actor,
        action="wallet.adjust",
        object_type="Wallet",
        object_id=str(wallet.pk),
        details={"delta": str(delta), "reason": reason.strip()},
    )
    return adjustment


@transaction.atomic
def update_market(seed=None, at=None, include_persistent=True):
    settings_row = MarketSettings.objects.select_for_update().filter(pk=1).first()
    if settings_row and settings_row.paused:
        return []
    settings_row = settings_row or MarketSettings.current()
    rng = random.Random(seed)
    at = at or timezone.now()
    updated = _update_persistent_market(settings_row, rng, at) if include_persistent else []
    round_messages = []
    active_rounds = GameRound.objects.filter(
        status=GameRound.Status.ACTIVE, starts_at__lte=at, ends_at__gt=at
    )
    for game_round in active_rounds:
        round_events = list(game_round.events.filter(starts_at__lte=at, ends_at__gt=at))
        round_effects = {}
        for event in round_events:
            for symbol, fraction in event.effects.items():
                round_effects[symbol] = round_effects.get(symbol, Decimal("0")) + Decimal(
                    str(fraction)
                )
        states = (
            RoundAssetState.objects.select_for_update()
            .filter(round=game_round, asset__is_active=True)
            .select_related("asset")
        )
        changed = []
        for state in states:
            effect = round_effects.get(state.asset.symbol, Decimal("0"))
            effect *= state.asset.event_sensitivity
            draw = Decimal(str(rng.uniform(-1, 1))) * state.asset.volatility
            cap = settings_row.max_movement_fraction
            movement = max(-cap, min(cap, draw + effect))
            price = money(state.current_price * (Decimal("1") + movement))
            price = min(state.asset.max_price, max(state.asset.min_price, price))
            if price == state.current_price:
                continue
            state.current_price = price
            state.version += 1
            state.save(update_fields=["current_price", "version", "updated_at"])
            RoundPriceSnapshot.objects.create(state=state, price=price, version=state.version)
            changed.append(
                {"symbol": state.asset.symbol, "price": str(price), "version": state.version}
            )
        if changed:
            round_messages.append(
                {
                    "type": "round.prices",
                    "round_id": str(game_round.pk),
                    "prices": changed,
                    "updated_at": at.isoformat(),
                }
            )
    for payload in round_messages:
        transaction.on_commit(lambda message=payload: _publish("satta_round_status", message))

    events_to_announce = list(
        MarketEvent.objects.select_for_update()
        .filter(starts_at__lte=at, ends_at__gt=at, broadcast_at__isnull=True)
        .select_related("template")
    )
    for event in events_to_announce:
        event.broadcast_at = at
        event.save(update_fields=["broadcast_at"])
        payload = {
            "type": "market.event",
            "event": {
                "id": event.pk,
                "name": event.template.name,
                "commentary": event.template.commentary,
                "effects": event.effects,
                "starts_at": event.starts_at.isoformat(),
                "ends_at": event.ends_at.isoformat(),
                "round_id": str(event.round_id) if event.round_id else None,
            },
        }
        transaction.on_commit(lambda message=payload: _publish("satta_market_events", message))
    return updated


def _update_persistent_market(settings_row, rng, at):
    active_events = list(
        MarketEvent.objects.filter(
            starts_at__lte=at, ends_at__gt=at, round__isnull=True
        ).select_related("template")
    )
    updated = []
    assets = Asset.objects.select_for_update().filter(is_active=True).order_by("id")
    for asset in assets:
        effect = Decimal("0")
        for event in active_events:
            fraction = event.effects.get(asset.symbol, 0)
            effect += Decimal(str(fraction)) * asset.event_sensitivity
        draw = Decimal(str(rng.uniform(-1, 1))) * asset.volatility
        cap = settings_row.max_movement_fraction
        movement = max(-cap, min(cap, draw + effect))
        price = money(asset.current_price * (Decimal("1") + movement))
        price = min(asset.max_price, max(asset.min_price, price))
        if price == asset.current_price:
            continue
        asset.current_price = price
        asset.version += 1
        asset.save(update_fields=["current_price", "version", "updated_at"])
        PriceSnapshot.objects.create(asset=asset, price=price, version=asset.version)
        updated.append(asset)
    if updated:
        message = {
            "type": "market.prices",
            "prices": [
                {
                    "symbol": asset.symbol,
                    "price": str(asset.current_price),
                    "version": asset.version,
                }
                for asset in updated
            ],
            "updated_at": at.isoformat(),
        }
        transaction.on_commit(lambda: _publish("satta_market_prices", message))
    return updated


@transaction.atomic
def transition_rounds(at=None):
    at = at or timezone.now()
    started_ids = list(
        GameRound.objects.select_for_update()
        .filter(status=GameRound.Status.SCHEDULED, starts_at__lte=at)
        .values_list("pk", flat=True)
    )
    GameRound.objects.filter(pk__in=started_ids).update(status=GameRound.Status.ACTIVE)
    if started_ids:
        started_rounds = GameRound.objects.filter(pk__in=started_ids).select_related("mode")
        assets = list(Asset.objects.filter(is_active=True))
        templates = list(MarketEventTemplate.objects.filter(is_active=True).order_by("pk"))
        for game_round in started_rounds:
            RoundAssetState.objects.bulk_create(
                [
                    RoundAssetState(
                        round=game_round,
                        asset=asset,
                        current_price=asset.current_price,
                    )
                    for asset in assets
                ],
                ignore_conflicts=True,
            )
            eligible = [
                template
                for template in templates
                if not game_round.mode.family_events_only or template.family_themed
            ]
            requested = game_round.mode.scheduled_events
            if eligible and requested:
                for index in range(requested):
                    template = eligible[index % len(eligible)]
                    event_at = game_round.starts_at + timedelta(
                        seconds=int(
                            game_round.mode.duration_seconds * (index + 1) / (requested + 1)
                        )
                    )
                    duration_end = min(
                        game_round.ends_at,
                        event_at + timedelta(minutes=template.duration_minutes),
                    )
                    if duration_end <= event_at:
                        continue
                    proposed_symbols = set(template.effects)
                    overlaps = False
                    scheduled = game_round.events.filter(
                        starts_at__lt=duration_end,
                        ends_at__gt=event_at,
                    )
                    for existing in scheduled:
                        if proposed_symbols.intersection(existing.effects):
                            overlaps = True
                            break
                    if not overlaps:
                        MarketEvent.objects.create(
                            template=template,
                            starts_at=event_at,
                            ends_at=duration_end,
                            effects=template.effects,
                            round=game_round,
                        )
        transaction.on_commit(
            lambda: _publish(
                "satta_round_status",
                {"type": "round.started", "round_ids": [str(value) for value in started_ids]},
            )
        )
    due = list(
        GameRound.objects.select_for_update().filter(
            status=GameRound.Status.ACTIVE, ends_at__lte=at
        )
    )
    for game_round in due:
        game_round.status = GameRound.Status.COMPLETED
        from .humor import choose_roast

        game_round.summary = (
            f"{game_round.mode.name} has ended. {choose_roast('round', seed=str(game_round.pk))}"
        )
        game_round.save(update_fields=["status", "summary"])
    for game_round in due:
        transaction.on_commit(
            lambda round_id=str(game_round.pk): _publish(
                "satta_round_status",
                {"type": "round.completed", "round_id": round_id},
            )
        )
    return due


@transaction.atomic
def capture_daily_portfolios(at=None):
    from .models import PortfolioSnapshot

    at = at or timezone.now()
    snapshot_date = timezone.localdate(at)
    captured = []
    for wallet in Wallet.objects.select_related("user").order_by("user_id"):
        market_value = sum(
            (
                money(position.quantity * position.asset.current_price)
                for position in Position.objects.filter(
                    user=wallet.user, quantity__gt=0
                ).select_related("asset")
            ),
            Decimal("0.00"),
        )
        snapshot, created = PortfolioSnapshot.objects.get_or_create(
            user=wallet.user,
            snapshot_date=snapshot_date,
            defaults={
                "cash_balance": wallet.balance,
                "market_value": market_value,
                "equity": money(wallet.balance + market_value),
            },
        )
        if created:
            captured.append(snapshot)
    return captured


def reconcile_wallet(wallet):
    wallet.refresh_from_db(fields=["balance"])
    entries = list(wallet.ledger.order_by("created_at", "pk").values_list("delta", "balance_after"))
    balance = Decimal("0.00")
    for delta, balance_after in entries:
        balance = money(balance + delta)
        if balance != balance_after:
            return False
    return balance == wallet.balance


def calculate_portfolio(user):
    positions = Position.objects.filter(user=user, quantity__gt=0).select_related("asset")
    items = []
    market_value = Decimal("0.00")
    unrealized = Decimal("0.00")
    for position in positions:
        value = money(position.quantity * position.asset.current_price)
        pnl = money(value - position.quantity * position.average_entry_price)
        market_value += value
        unrealized += pnl
        items.append(
            {
                "symbol": position.asset.symbol,
                "name": position.asset.name,
                "quantity": position.quantity,
                "average_entry_price": position.average_entry_price,
                "current_price": position.asset.current_price,
                "market_value": value,
                "unrealized_pnl": pnl,
                "realized_pnl": position.realized_pnl,
            }
        )
    wallet = Wallet.objects.get(user=user)
    return {
        "cash_balance": wallet.balance,
        "positions": items,
        "market_value": money(market_value),
        "equity": money(wallet.balance + market_value),
        "realized_pnl": money(
            sum((item.realized_pnl for item in Position.objects.filter(user=user)), Decimal("0"))
        ),
        "unrealized_pnl": money(unrealized),
    }


def apply_event(template, round_instance=None, at=None):
    validate_event_effects(template.effects)
    at = at or timezone.now()
    active_symbols = set(Asset.objects.filter(is_active=True).values_list("symbol", flat=True))
    unknown = set(template.effects) - active_symbols
    if unknown:
        raise ValidationError(
            f"Event references unknown or inactive assets: {', '.join(sorted(unknown))}."
        )
    ends_at = at + timedelta(minutes=template.duration_minutes)
    conflicts = MarketEvent.objects.filter(
        ends_at__gt=at,
        starts_at__lt=ends_at,
        round=round_instance,
    )
    conflicting_symbols = set()
    for occurrence in conflicts:
        conflicting_symbols.update(occurrence.effects.keys())
    overlap = conflicting_symbols.intersection(template.effects)
    if overlap:
        raise ValidationError(
            f"Conflicting active event effects for: {', '.join(sorted(overlap))}."
        )
    occurrence = MarketEvent.objects.create(
        template=template,
        starts_at=at,
        ends_at=ends_at,
        effects=template.effects,
        round=round_instance,
    )
    return occurrence
