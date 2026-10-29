import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Asset(models.Model):
    class Category(models.TextChoices):
        FOOD = "food", "Food & Chai"
        TECH = "tech", "Technology"
        FAMILY = "family", "Family"
        TRANSPORT = "transport", "Transport"
        ENTERTAINMENT = "entertainment", "Entertainment"
        LIFE = "life", "Everyday Life"

    symbol = models.CharField(max_length=12, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=Category.choices)
    base_price = models.DecimalField(max_digits=14, decimal_places=2)
    current_price = models.DecimalField(max_digits=14, decimal_places=2)
    volatility = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("0.25"))],
    )
    min_price = models.DecimalField(max_digits=14, decimal_places=2)
    max_price = models.DecimalField(max_digits=14, decimal_places=2)
    event_sensitivity = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=1,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("5"))],
    )
    is_active = models.BooleanField(default=True)
    version = models.PositiveBigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["symbol"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(base_price__gt=0), name="asset_base_price_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(min_price__gt=0), name="asset_min_price_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(max_price__gt=models.F("min_price")),
                name="asset_max_above_min",
            ),
            models.CheckConstraint(
                condition=models.Q(current_price__gte=models.F("min_price"))
                & models.Q(current_price__lte=models.F("max_price")),
                name="asset_price_within_limits",
            ),
        ]

    def __str__(self):
        return f"{self.symbol} — {self.name}"


class PriceSnapshot(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="history")
    price = models.DecimalField(max_digits=14, decimal_places=2)
    version = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["asset", "version"], name="unique_asset_price_version")
        ]


class MarketSettings(models.Model):
    paused = models.BooleanField(default=False)
    price_update_interval_seconds = models.PositiveSmallIntegerField(
        default=15, validators=[MinValueValidator(1)]
    )
    max_movement_fraction = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=0.05,
        validators=[MinValueValidator(Decimal("0.001")), MaxValueValidator(Decimal("0.25"))],
    )
    trade_fee_fraction = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=0,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("0.1"))],
    )
    starting_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal(settings.STARTING_BALANCE),
        validators=[MinValueValidator(Decimal("0"))],
    )
    daily_reward = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=250,
        validators=[MinValueValidator(Decimal("0"))],
    )
    max_trade_quantity = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=10000,
        validators=[MinValueValidator(Decimal("0.0001"))],
    )
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def current(cls):
        return cls.objects.get_or_create(pk=1)[0]

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)


class Wallet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet"
    )
    balance = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(balance__gte=0), name="wallet_balance_nonnegative"
            )
        ]

    def __str__(self):
        return f"{self.user}: {self.balance} BB"


class LedgerEntry(models.Model):
    class Kind(models.TextChoices):
        STARTING_BALANCE = "starting_balance", "Starting balance"
        BUY = "buy", "Trade purchase"
        SELL = "sell", "Trade sale"
        DAILY_REWARD = "daily_reward", "Daily reward"
        MISSION_REWARD = "mission_reward", "Mission reward"
        ADMIN_ADJUSTMENT = "admin_adjustment", "Admin adjustment"

    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="ledger")
    kind = models.CharField(max_length=30, choices=Kind.choices)
    delta = models.DecimalField(max_digits=16, decimal_places=2)
    balance_after = models.DecimalField(max_digits=16, decimal_places=2)
    reason = models.CharField(max_length=200)
    idempotency_key = models.CharField(max_length=110, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["wallet", "idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="unique_wallet_ledger_idempotency",
            )
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValueError("Ledger entries are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Ledger entries cannot be deleted.")


class WalletAdjustment(models.Model):
    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="adjustments")
    ledger_entry = models.OneToOneField(
        LedgerEntry, on_delete=models.PROTECT, related_name="adjustment"
    )
    adjusted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class DailyRewardClaim(models.Model):
    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="daily_claims")
    claim_date = models.DateField()
    ledger_entry = models.OneToOneField(LedgerEntry, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["wallet", "claim_date"], name="unique_wallet_daily_reward"
            )
        ]


class Trade(models.Model):
    class Side(models.TextChoices):
        BUY = "buy", "Buy"
        SELL = "sell", "Sell"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT)
    side = models.CharField(max_length=4, choices=Side.choices)
    quantity = models.DecimalField(max_digits=14, decimal_places=4)
    price = models.DecimalField(max_digits=14, decimal_places=2)
    gross_amount = models.DecimalField(max_digits=16, decimal_places=2)
    fee = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    realized_pnl = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    idempotency_key = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "idempotency_key"], name="unique_user_trade_idempotency"
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="trade_quantity_positive"
            ),
        ]


class Position(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    average_entry_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    realized_pnl = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "asset"], name="unique_user_asset_position"),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0), name="position_quantity_nonnegative"
            ),
        ]


class PortfolioSnapshot(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="portfolio_history"
    )
    cash_balance = models.DecimalField(max_digits=16, decimal_places=2)
    market_value = models.DecimalField(max_digits=16, decimal_places=2)
    equity = models.DecimalField(max_digits=16, decimal_places=2)
    snapshot_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "snapshot_date"],
                condition=models.Q(snapshot_date__isnull=False),
                name="unique_user_daily_portfolio_snapshot",
            )
        ]


class MarketEventTemplate(models.Model):
    name = models.CharField(max_length=160, unique=True)
    commentary = models.CharField(max_length=240)
    effects = models.JSONField(default=dict)
    duration_minutes = models.PositiveSmallIntegerField(default=5)
    rarity = models.PositiveSmallIntegerField(
        default=50, validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    is_active = models.BooleanField(default=True)
    family_themed = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(duration_minutes__gt=0),
                name="event_template_duration_positive",
            )
        ]

    def clean(self):
        from .services import validate_event_effects

        validate_event_effects(self.effects)

    def __str__(self):
        return self.name


class MarketEvent(models.Model):
    template = models.ForeignKey(
        MarketEventTemplate, on_delete=models.PROTECT, related_name="occurrences"
    )
    starts_at = models.DateTimeField(default=timezone.now, db_index=True)
    ends_at = models.DateTimeField(db_index=True)
    effects = models.JSONField(default=dict)
    broadcast_at = models.DateTimeField(null=True, blank=True)
    round = models.ForeignKey(
        "GameRound", on_delete=models.CASCADE, related_name="events", null=True, blank=True
    )

    class Meta:
        ordering = ["-starts_at"]


class GameMode(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    duration_seconds = models.PositiveSmallIntegerField()
    description = models.TextField()
    family_events_only = models.BooleanField(default=False)
    scheduled_events = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(duration_seconds__gt=0),
                name="game_mode_duration_positive",
            )
        ]

    def __str__(self):
        return self.name


class GameRound(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mode = models.ForeignKey(GameMode, on_delete=models.PROTECT, related_name="rounds")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SCHEDULED)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True
    )
    summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-starts_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at")),
                name="round_ends_after_start",
            )
        ]


class RoundAssetState(models.Model):
    round = models.ForeignKey(GameRound, on_delete=models.CASCADE, related_name="asset_states")
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT)
    current_price = models.DecimalField(max_digits=14, decimal_places=2)
    version = models.PositiveBigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["round", "asset"], name="unique_round_asset_state"),
            models.CheckConstraint(
                condition=models.Q(current_price__gt=0), name="round_asset_price_positive"
            ),
        ]


class RoundPriceSnapshot(models.Model):
    state = models.ForeignKey(RoundAssetState, on_delete=models.CASCADE, related_name="history")
    price = models.DecimalField(max_digits=14, decimal_places=2)
    version = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["state", "version"], name="unique_round_price_version")
        ]


class Achievement(models.Model):
    code = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=240)
    xp_reward = models.PositiveSmallIntegerField(default=0)


class UserAchievement(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    achievement = models.ForeignKey(Achievement, on_delete=models.PROTECT)
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "achievement"], name="unique_user_achievement")
        ]


class Mission(models.Model):
    class Trigger(models.TextChoices):
        TRADE = "trade", "Any trade"
        BUY_ASSET = "buy_asset", "Buy a specific asset"

    code = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=240)
    target = models.PositiveSmallIntegerField(default=1)
    reward = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0"))],
    )
    trigger = models.CharField(max_length=20, choices=Trigger.choices, default=Trigger.TRADE)
    target_symbol = models.CharField(max_length=12, blank=True)
    active_from = models.DateTimeField(default=timezone.now)
    active_until = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(target__gt=0), name="mission_target_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(active_until__gt=models.F("active_from")),
                name="mission_ends_after_start",
            ),
        ]


class UserMission(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    mission = models.ForeignKey(Mission, on_delete=models.PROTECT)
    progress = models.PositiveSmallIntegerField(default=0)
    claimed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "mission"], name="unique_user_mission")
        ]


class AuditEvent(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True
    )
    action = models.CharField(max_length=80)
    object_type = models.CharField(max_length=80)
    object_id = models.CharField(max_length=80)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class HumourLine(models.Model):
    class Category(models.TextChoices):
        BUY = "buy", "Buy"
        PROFIT = "profit", "Profit"
        LOSS = "loss", "Loss"
        REWARD = "reward", "Daily reward"
        ACHIEVEMENT = "achievement", "Achievement"
        ROUND = "round", "Round summary"
        CRASH = "crash", "Market crash"

    class Language(models.TextChoices):
        HINGLISH = "hinglish", "Hinglish"
        ENGLISH = "en", "English"

    category = models.CharField(max_length=20, choices=Category.choices)
    language = models.CharField(max_length=10, choices=Language.choices)
    text = models.CharField(max_length=240)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["category", "language", "text"], name="unique_humour_line"
            )
        ]
