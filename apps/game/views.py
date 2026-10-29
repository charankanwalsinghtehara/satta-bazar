from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError, connection, transaction
from django.db.models import Sum
from django.middleware.csrf import CsrfViewMiddleware
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .humor import choose_roast, trade_humour
from .models import (
    Achievement,
    Asset,
    GameMode,
    GameRound,
    LedgerEntry,
    MarketEvent,
    MarketSettings,
    Position,
    PriceSnapshot,
    Trade,
    UserAchievement,
    UserMission,
    Wallet,
)
from .serializers import (
    AchievementSerializer,
    AssetSerializer,
    EventSerializer,
    GameModeSerializer,
    LedgerSerializer,
    MissionSerializer,
    PriceSnapshotSerializer,
    ProfileSerializer,
    PublicProfileSerializer,
    RegisterSerializer,
    RoundSerializer,
    TradeRequestSerializer,
    TradeSerializer,
    UserAchievementSerializer,
    active_missions,
)
from .services import (
    calculate_portfolio,
    claim_daily_reward,
    execute_trade,
    money,
    reconcile_wallet,
)

User = get_user_model()


def home(request):
    return render(request, "game/index.html")


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    try:
        connection.ensure_connection()
    except DatabaseError:
        import logging

        logging.getLogger(__name__).exception("Database health check failed")
        return Response(
            {"status": "unhealthy", "database": "unavailable"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return Response({"status": "ok", "database": "ok"})


def _page(request, queryset, serializer_class, context=None):
    paginator = PageNumberPagination()
    paginator.page_size = 25
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response(
        serializer_class(page, many=True, context=context or {}).data
    )


def _service_error(exc):
    detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
    return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)


def _csrf_failure(request):
    django_request = request._request
    django_request.csrf_processing_done = False
    middleware = CsrfViewMiddleware(lambda current_request: None)
    return middleware.process_view(django_request, lambda current_request: None, (), {})


@api_view(["GET"])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def csrf_cookie(request):
    return Response({"detail": "CSRF cookie set."})


@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    if _csrf_failure(request):
        return Response({"detail": "CSRF verification failed."}, status=403)
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    login(request, user)
    return Response(
        {
            "user": ProfileSerializer(user).data,
            "wallet": {"balance": user.wallet.balance, "currency": "BB"},
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def session_login(request):
    if _csrf_failure(request):
        return Response({"detail": "CSRF verification failed."}, status=403)
    username = request.data.get("username", "")
    password = request.data.get("password", "")
    if not isinstance(username, str) or not isinstance(password, str):
        return Response({"detail": "Invalid credentials."}, status=status.HTTP_400_BAD_REQUEST)
    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response(
            {"detail": "Invalid username or password."}, status=status.HTTP_400_BAD_REQUEST
        )
    login(request, user)
    return Response({"user": ProfileSerializer(user).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def session_logout(request):
    logout(request)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset(request):
    form = PasswordResetForm(data={"email": request.data.get("email", "")})
    if form.is_valid():
        form.save(
            request=request,
            use_https=request.is_secure(),
            email_template_name="registration/password_reset_email.txt",
        )
    return Response(
        {"detail": "If that email belongs to an account, password reset instructions will be sent."}
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_confirm(request):
    if _csrf_failure(request):
        return Response({"detail": "CSRF verification failed."}, status=403)
    try:
        user_id = force_str(urlsafe_base64_decode(request.data.get("uid", "")))
        user = User.objects.get(pk=user_id, is_active=True)
    except (ValueError, TypeError, User.DoesNotExist):
        return Response({"detail": "Invalid or expired reset link."}, status=400)
    from django.contrib.auth.tokens import default_token_generator

    token = request.data.get("token", "")
    if not isinstance(token, str) or not default_token_generator.check_token(user, token):
        return Response({"detail": "Invalid or expired reset link."}, status=400)
    form = SetPasswordForm(user, request.data)
    if not form.is_valid():
        return Response({"detail": form.errors}, status=400)
    form.save()
    return Response({"detail": "Password updated. Log in with your new password."})


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def me(request):
    if request.method == "PATCH":
        serializer = ProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    return Response(ProfileSerializer(request.user).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def assets(request):
    query = Asset.objects.filter(is_active=True)
    category = request.query_params.get("category")
    if category:
        query = query.filter(category=category)
    search = request.query_params.get("search")
    if search:
        query = query.filter(name__icontains=search)
    return _page(request, query, AssetSerializer)


@api_view(["GET"])
@permission_classes([AllowAny])
def asset_detail(request, symbol):
    asset = get_object_or_404(Asset, symbol=symbol.upper(), is_active=True)
    return Response(AssetSerializer(asset).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def asset_history(request, symbol):
    asset = get_object_or_404(Asset, symbol=symbol.upper(), is_active=True)
    query = PriceSnapshot.objects.filter(asset=asset)
    return _page(request, query, PriceSnapshotSerializer)


@api_view(["GET"])
@permission_classes([AllowAny])
def market_overview(request):
    settings_row = MarketSettings.current()
    assets_query = Asset.objects.filter(is_active=True)
    return Response(
        {
            "paused": settings_row.paused,
            "asset_count": assets_query.count(),
            "active_events": EventSerializer(
                MarketEvent.objects.filter(
                    starts_at__lte=timezone.now(), ends_at__gt=timezone.now()
                ).select_related("template"),
                many=True,
            ).data,
            "assets": AssetSerializer(assets_query, many=True).data,
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def market_movers(request):
    movers = []
    for asset in Asset.objects.filter(is_active=True):
        prior = (
            PriceSnapshot.objects.filter(asset=asset)
            .order_by("-created_at")
            .values_list("price", flat=True)[1:2]
        )
        prior_price = next(iter(prior), asset.base_price)
        change = asset.current_price - prior_price
        percent = (change / prior_price * Decimal("100")) if prior_price else Decimal("0")
        movers.append(
            {
                "symbol": asset.symbol,
                "name": asset.name,
                "price": asset.current_price,
                "change": change,
                "change_percent": percent.quantize(Decimal("0.01")),
            }
        )
    movers.sort(key=lambda item: abs(item["change_percent"]), reverse=True)
    return Response({"movers": movers[:20]})


@api_view(["GET"])
@permission_classes([AllowAny])
def market_events(request):
    now = timezone.now()
    query = MarketEvent.objects.filter(ends_at__gt=now).select_related("template")
    return _page(request, query, EventSerializer)


@api_view(["GET"])
@permission_classes([AllowAny])
def market_news(request):
    query = MarketEvent.objects.select_related("template")
    return _page(request, query, EventSerializer)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def wallet_detail(request):
    wallet = request.user.wallet
    return Response(
        {
            "balance": wallet.balance,
            "currency": "BB",
            "ledger_reconciled": reconcile_wallet(wallet),
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def wallet_ledger(request):
    return _page(request, request.user.wallet.ledger.all(), LedgerSerializer)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def portfolio(request):
    return Response(calculate_portfolio(request.user))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def portfolio_positions(request):
    query = Position.objects.filter(user=request.user, quantity__gt=0).select_related("asset")
    return Response(
        [
            {
                "symbol": row.asset.symbol,
                "name": row.asset.name,
                "quantity": row.quantity,
                "average_entry_price": row.average_entry_price,
                "current_price": row.asset.current_price,
                "market_value": money(row.quantity * row.asset.current_price),
                "unrealized_pnl": money(
                    (row.asset.current_price - row.average_entry_price) * row.quantity
                ),
                "realized_pnl": row.realized_pnl,
            }
            for row in query
        ]
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def portfolio_history(request):
    query = request.user.portfolio_history.all()
    return _page(request, query, _PortfolioSnapshotSerializer)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def trade_buy(request):
    return _trade(request, Trade.Side.BUY)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def trade_sell(request):
    return _trade(request, Trade.Side.SELL)


def _trade(request, side):
    serializer = TradeRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    was_replay = Trade.objects.filter(
        user=request.user,
        idempotency_key=serializer.validated_data["idempotency_key"],
    ).exists()
    try:
        trade = execute_trade(
            request.user,
            serializer.validated_data["symbol"],
            side,
            serializer.validated_data["quantity"],
            serializer.validated_data["idempotency_key"],
        )
    except DjangoValidationError as exc:
        return _service_error(exc)
    return Response(
        {
            "trade": TradeSerializer(trade).data,
            "portfolio": calculate_portfolio(request.user),
            "roast": trade_humour(trade, serializer.validated_data["language"]),
        },
        status=status.HTTP_200_OK if was_replay else status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def trades(request):
    return _page(
        request,
        Trade.objects.filter(user=request.user).select_related("asset"),
        TradeSerializer,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def trade_detail(request, trade_id):
    trade = get_object_or_404(Trade.objects.select_related("asset"), pk=trade_id, user=request.user)
    return Response(TradeSerializer(trade).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def daily_reward_claim(request):
    try:
        claim, created = claim_daily_reward(request.user)
    except DjangoValidationError as exc:
        return _service_error(exc)
    request.user.wallet.refresh_from_db(fields=["balance"])
    return Response(
        {
            "claimed": created,
            "amount": claim.ledger_entry.delta,
            "claimed_at": claim.created_at,
            "wallet_balance": request.user.wallet.balance,
            "message": choose_roast("reward"),
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def game_modes(request):
    return Response(GameModeSerializer(GameMode.objects.filter(is_active=True), many=True).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def rounds(request):
    return _page(request, GameRound.objects.select_related("mode"), RoundSerializer)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def start_round(request):
    slug = request.data.get("mode")
    if not isinstance(slug, str):
        return Response({"detail": "A game mode slug is required."}, status=400)
    created = False
    with transaction.atomic():
        mode = GameMode.objects.select_for_update().filter(slug=slug, is_active=True).first()
        if mode is None:
            return Response({"detail": "Game mode not found."}, status=404)
        game_round = (
            GameRound.objects.select_for_update()
            .filter(
                mode=mode,
                status__in=[GameRound.Status.SCHEDULED, GameRound.Status.ACTIVE],
            )
            .first()
        )
        if game_round is None:
            starts_at = timezone.now() + timedelta(seconds=2)
            game_round = GameRound.objects.create(
                mode=mode,
                status=GameRound.Status.SCHEDULED,
                starts_at=starts_at,
                ends_at=starts_at + timedelta(seconds=mode.duration_seconds),
                created_by=request.user,
            )
            created = True
    return Response(
        RoundSerializer(game_round).data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def round_detail(request, round_id):
    game_round = get_object_or_404(GameRound.objects.select_related("mode"), pk=round_id)
    return Response(RoundSerializer(game_round).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def round_events(request, round_id):
    game_round = get_object_or_404(GameRound, pk=round_id)
    return _page(
        request,
        MarketEvent.objects.filter(round=game_round).select_related("template"),
        EventSerializer,
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def round_results(request, round_id):
    game_round = get_object_or_404(GameRound.objects.select_related("mode"), pk=round_id)
    return Response(
        {
            "round": RoundSerializer(game_round).data,
            "summary": game_round.summary or choose_roast("round"),
            "wallets_preserved": True,
            "events": EventSerializer(game_round.events.select_related("template"), many=True).data,
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def achievements(request):
    return Response(AchievementSerializer(Achievement.objects.all(), many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_achievements(request):
    query = UserAchievement.objects.filter(user=request.user).select_related("achievement")
    return Response(UserAchievementSerializer(query, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def missions(request):
    return Response(
        MissionSerializer(active_missions(), many=True, context={"request": request}).data
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mission_claim(request, mission_id):
    now = timezone.now()
    mission = get_object_or_404(active_missions().filter(pk=mission_id))
    try:
        with transaction.atomic():
            assignment, _ = UserMission.objects.select_for_update().get_or_create(
                user=request.user, mission=mission
            )
            if assignment.claimed_at:
                return Response({"detail": "Mission reward already claimed."}, status=409)
            if assignment.progress < mission.target:
                return Response({"detail": "Mission is not complete yet."}, status=400)
            wallet = Wallet.objects.select_for_update().get(user=request.user)
            balance = money(wallet.balance + mission.reward)
            wallet.balance = balance
            wallet.save(update_fields=["balance", "updated_at"])
            entry = LedgerEntry.objects.create(
                wallet=wallet,
                kind=LedgerEntry.Kind.MISSION_REWARD,
                delta=mission.reward,
                balance_after=balance,
                reason=f"Mission reward: {mission.name}",
                idempotency_key=f"mission:{mission.pk}",
            )
            assignment.claimed_at = now
            assignment.save(update_fields=["claimed_at"])
    except DjangoValidationError as exc:
        return _service_error(exc)
    return Response({"claimed": True, "reward": entry.delta, "wallet_balance": balance})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def reward_daily(request):
    return daily_reward_claim(request)


@api_view(["GET"])
@permission_classes([AllowAny])
def leaderboard(request):
    kind = request.query_params.get("type", "equity")
    period = request.query_params.get("period", "all")
    users = User.objects.filter(is_active=True)
    cutoff = None
    if period == "weekly" and kind != "equity":
        cutoff = timezone.now() - timedelta(days=7)
        recent = Trade.objects.filter(created_at__gte=cutoff).values("user_id")
        users = users.filter(id__in=recent)
    elif period != "all":
        return Response(
            {"detail": "period must be 'all' or 'weekly'."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if kind not in {"equity", "realized_pnl", "best_trade", "trades"}:
        return Response(
            {"detail": ("type must be 'equity', 'realized_pnl', 'best_trade', or 'trades'.")},
            status=status.HTTP_400_BAD_REQUEST,
        )
    ranking = []
    for user in users:
        if kind == "realized_pnl":
            trades_query = Trade.objects.filter(user=user, side=Trade.Side.SELL)
            if cutoff:
                trades_query = trades_query.filter(created_at__gte=cutoff)
            value = trades_query.aggregate(total=Sum("realized_pnl"))["total"] or Decimal("0")
        elif kind == "best_trade":
            trades_query = Trade.objects.filter(user=user, side=Trade.Side.SELL)
            if cutoff:
                trades_query = trades_query.filter(created_at__gte=cutoff)
            value = trades_query.order_by("-realized_pnl").values_list(
                "realized_pnl", flat=True
            ).first() or Decimal("0")
        elif kind == "trades":
            trades_query = Trade.objects.filter(user=user)
            if cutoff:
                trades_query = trades_query.filter(created_at__gte=cutoff)
            value = trades_query.count()
        else:
            wallet = Wallet.objects.filter(user=user).first()
            if not wallet:
                continue
            market_value = sum(
                (
                    money(row.quantity * row.asset.current_price)
                    for row in Position.objects.filter(user=user, quantity__gt=0).select_related(
                        "asset"
                    )
                ),
                Decimal("0"),
            )
            value = money(wallet.balance + market_value)
            if cutoff:
                baseline = (
                    user.portfolio_history.filter(created_at__lte=cutoff)
                    .order_by("-created_at")
                    .values_list("equity", flat=True)
                    .first()
                )
                if baseline is not None:
                    value -= baseline
                elif period == "weekly":
                    continue
        ranking.append({"username": user.username, "score": value})
    ranking.sort(key=lambda row: row["score"], reverse=True)
    return Response(
        {
            "type": kind,
            "period": period,
            "rankings": [{"rank": index + 1, **entry} for index, entry in enumerate(ranking[:100])],
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def public_profile(request, username):
    user = get_object_or_404(User, username=username, is_active=True)
    return Response(
        {
            "user": PublicProfileSerializer(user).data,
            "achievement_count": UserAchievement.objects.filter(user=user).count(),
            "trade_count": Trade.objects.filter(user=user).count(),
        }
    )


class _PortfolioSnapshotSerializer(serializers.Serializer):
    cash_balance = serializers.DecimalField(max_digits=16, decimal_places=2)
    market_value = serializers.DecimalField(max_digits=16, decimal_places=2)
    equity = serializers.DecimalField(max_digits=16, decimal_places=2)
    created_at = serializers.DateTimeField()
