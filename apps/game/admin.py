from django.contrib import admin

from .models import (
    Achievement,
    Asset,
    AuditEvent,
    DailyRewardClaim,
    GameMode,
    GameRound,
    LedgerEntry,
    MarketEvent,
    MarketEventTemplate,
    MarketSettings,
    Mission,
    Position,
    PriceSnapshot,
    RoundPriceSnapshot,
    Trade,
    UserAchievement,
    UserMission,
    Wallet,
    WalletAdjustment,
)


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("symbol", "name", "category", "current_price", "is_active", "version")
    list_filter = ("category", "is_active")
    search_fields = ("symbol", "name")
    readonly_fields = ("current_price", "version", "updated_at")


@admin.register(MarketSettings)
class MarketSettingsAdmin(admin.ModelAdmin):
    list_display = ("paused", "price_update_interval_seconds", "trade_fee_fraction")

    def has_add_permission(self, request):
        return not MarketSettings.objects.exists() and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "updated_at")
    search_fields = ("user__username",)
    readonly_fields = ("user", "balance", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LedgerEntry)
class ImmutableAdmin(admin.ModelAdmin):
    list_display = ("wallet", "kind", "delta", "balance_after", "created_at")
    readonly_fields = tuple(field.name for field in LedgerEntry._meta.fields)
    list_filter = ("kind", "created_at")
    search_fields = ("wallet__user__username", "reason")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "asset", "side", "quantity", "price", "realized_pnl")
    list_filter = ("side", "created_at")
    readonly_fields = tuple(field.name for field in Trade._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(
    PriceSnapshot,
    RoundPriceSnapshot,
    Position,
    WalletAdjustment,
    DailyRewardClaim,
    AuditEvent,
)
class ReadOnlyGameAdmin(admin.ModelAdmin):
    list_per_page = 50

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(
    (
        MarketEventTemplate,
        GameMode,
        GameRound,
        Achievement,
        UserAchievement,
        Mission,
        UserMission,
    )
)


@admin.register(MarketEvent)
class MarketEventAdmin(ReadOnlyGameAdmin):
    list_display = ("template", "round", "starts_at", "ends_at")
    list_filter = ("starts_at", "ends_at")
