from datetime import timedelta
from decimal import Decimal

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from config.asgi import application

from .models import (
    Asset,
    DailyRewardClaim,
    GameMode,
    GameRound,
    LedgerEntry,
    MarketEventTemplate,
    MarketSettings,
    Position,
    RoundAssetState,
    Trade,
    Wallet,
)
from .services import (
    apply_event,
    calculate_portfolio,
    claim_daily_reward,
    execute_trade,
    reconcile_wallet,
    transition_rounds,
    update_market,
)

User = get_user_model()


class GameServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="player-one", password="safe-password-123")
        cls.asset = Asset.objects.create(
            symbol="TEST",
            name="Test Asset",
            description="A test asset.",
            category=Asset.Category.FOOD,
            base_price=Decimal("10.00"),
            current_price=Decimal("10.00"),
            volatility=Decimal("0.05"),
            min_price=Decimal("1.00"),
            max_price=Decimal("100.00"),
        )

    def test_new_user_wallet_has_ledger_backed_starting_balance(self):
        wallet = self.user.wallet
        self.assertEqual(wallet.balance, Decimal("10000.00"))
        entry = wallet.ledger.get(kind=LedgerEntry.Kind.STARTING_BALANCE)
        self.assertEqual(entry.balance_after, wallet.balance)
        self.assertTrue(reconcile_wallet(wallet))

    def test_trade_is_idempotent_and_uses_server_price(self):
        first = execute_trade(self.user, "TEST", Trade.Side.BUY, "10", "same-order")
        second = execute_trade(self.user, "TEST", Trade.Side.BUY, "10", "same-order")

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Trade.objects.filter(user=self.user).count(), 1)
        self.assertEqual(first.price, Decimal("10.00"))
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("9900.00"))
        self.assertTrue(reconcile_wallet(self.user.wallet))

    def test_reusing_idempotency_key_for_different_trade_is_rejected(self):
        execute_trade(self.user, "TEST", Trade.Side.BUY, "1", "same-order")
        with self.assertRaises(ValidationError):
            execute_trade(self.user, "TEST", Trade.Side.BUY, "2", "same-order")

    def test_insufficient_funds_rolls_back_trade_and_ledger(self):
        original_balance = self.user.wallet.balance
        with self.assertRaises(ValidationError):
            execute_trade(self.user, "TEST", Trade.Side.BUY, "1001", "too-expensive")

        self.assertEqual(self.user.wallet.balance, original_balance)
        self.assertFalse(Trade.objects.filter(user=self.user).exists())
        self.assertEqual(self.user.wallet.ledger.count(), 1)

    def test_partial_sale_tracks_realized_profit_and_keeps_cost_basis(self):
        execute_trade(self.user, "TEST", Trade.Side.BUY, "10", "buy-test")
        Asset.objects.filter(pk=self.asset.pk).update(current_price=Decimal("15.00"))
        sold = execute_trade(self.user, "TEST", Trade.Side.SELL, "4", "sell-test")
        position = Position.objects.get(user=self.user, asset=self.asset)

        self.assertEqual(sold.realized_pnl, Decimal("20.00"))
        self.assertEqual(position.quantity, Decimal("6.0000"))
        self.assertEqual(position.average_entry_price, Decimal("10.00"))
        self.assertEqual(position.realized_pnl, Decimal("20.00"))
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("9960.00"))
        self.assertTrue(reconcile_wallet(self.user.wallet))
        self.assertEqual(calculate_portfolio(self.user)["unrealized_pnl"], Decimal("30.00"))

    def test_cannot_sell_more_than_position(self):
        execute_trade(self.user, "TEST", Trade.Side.BUY, "1", "buy-one")
        with self.assertRaises(ValidationError):
            execute_trade(self.user, "TEST", Trade.Side.SELL, "2", "sell-two")

    def test_daily_reward_claim_is_once_per_day(self):
        first, created = claim_daily_reward(self.user)
        second, created_again = claim_daily_reward(self.user)

        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(DailyRewardClaim.objects.filter(wallet=self.user.wallet).count(), 1)
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("10250.00"))
        self.assertTrue(reconcile_wallet(self.user.wallet))

    def test_market_updates_are_seeded_and_stay_inside_asset_bounds(self):
        first_run = update_market(seed=19)[0].current_price
        Asset.objects.filter(pk=self.asset.pk).update(current_price=Decimal("10.00"))
        second_run = update_market(seed=19)[0].current_price

        self.assertEqual(first_run, second_run)
        self.assertGreaterEqual(second_run, self.asset.min_price)
        self.assertLessEqual(second_run, self.asset.max_price)

    def test_market_pause_prevents_price_changes(self):
        settings_row = MarketSettings.current()
        settings_row.paused = True
        settings_row.save()
        before = self.asset.current_price

        self.assertEqual(update_market(seed=2), [])
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.current_price, before)

    def test_events_reject_invalid_effects_and_conflicting_assets(self):
        template = MarketEventTemplate.objects.create(
            name="Test event",
            commentary="The test market has feelings.",
            effects={"TEST": "0.10"},
            duration_minutes=5,
        )
        occurrence = apply_event(template)
        self.assertEqual(occurrence.effects, {"TEST": "0.10"})
        with self.assertRaises(ValidationError):
            apply_event(template)

        template.effects = {"TEST": "0.90"}
        with self.assertRaises(ValidationError):
            apply_event(template)

    def test_round_transitions_are_deterministic_and_do_not_touch_wallet(self):
        mode = GameMode.objects.create(
            slug="quick-test",
            name="Quick Test",
            duration_seconds=10,
            description="A test round.",
        )
        now = timezone.now()
        game_round = GameRound.objects.create(
            mode=mode,
            starts_at=now - timedelta(seconds=20),
            ends_at=now - timedelta(seconds=1),
        )
        balance = self.user.wallet.balance

        completed = transition_rounds(at=now)
        game_round.refresh_from_db()
        self.assertEqual(game_round.status, GameRound.Status.COMPLETED)
        self.assertEqual(completed, [game_round])
        self.assertEqual(self.user.wallet.balance, balance)

    def test_round_market_tick_is_isolated_from_persistent_market(self):
        mode = GameMode.objects.create(
            slug="isolated-test",
            name="Isolated Test",
            duration_seconds=10,
            description="Round prices stay independent.",
        )
        now = timezone.now()
        game_round = GameRound.objects.create(
            mode=mode,
            status=GameRound.Status.ACTIVE,
            starts_at=now - timedelta(seconds=1),
            ends_at=now + timedelta(seconds=30),
        )
        state = RoundAssetState.objects.create(
            round=game_round,
            asset=self.asset,
            current_price=Decimal("10.00"),
        )
        persistent_price = Asset.objects.get(pk=self.asset.pk).current_price

        update_market(seed=19, at=now, include_persistent=False)
        state.refresh_from_db()

        self.assertNotEqual(state.current_price, Decimal("10.00"))
        self.assertEqual(Asset.objects.get(pk=self.asset.pk).current_price, persistent_price)
        self.assertEqual(state.history.count(), 1)


class GameApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="api-player", password="safe-password-123")
        cls.asset = Asset.objects.create(
            symbol="API",
            name="API Asset",
            description="For API tests.",
            category=Asset.Category.TECH,
            base_price=Decimal("20.00"),
            current_price=Decimal("20.00"),
            volatility=Decimal("0.05"),
            min_price=Decimal("1.00"),
            max_price=Decimal("200.00"),
        )

    def setUp(self):
        self.client = APIClient()

    def test_asset_catalog_is_public(self):
        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["symbol"], "API")

    def test_openapi_schema_endpoint_is_available(self):
        response = self.client.get("/api/schema/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("/api/v1/trades/buy/", response.data["paths"])

    def test_wallet_requires_login(self):
        response = self.client.get("/api/v1/wallet/")
        self.assertEqual(response.status_code, 403)

    def test_public_profile_does_not_expose_email_or_wallet_balance(self):
        response = self.client.get("/api/v1/users/api-player/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data["user"]), {"username", "date_joined"})
        self.assertNotIn("balance", response.data)

    def test_session_login_and_private_wallet_api(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"username": "api-player", "password": "safe-password-123"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        wallet_response = self.client.get("/api/v1/wallet/")
        self.assertEqual(wallet_response.status_code, 200)
        self.assertEqual(wallet_response.data["balance"], Decimal("10000.00"))

    def test_trade_endpoint_uses_session_auth_and_idempotency(self):
        self.client.force_login(self.user)
        payload = {"symbol": "API", "quantity": "2", "idempotency_key": "api-trade-1"}
        first = self.client.post("/api/v1/trades/buy/", payload, format="json")
        replay = self.client.post("/api/v1/trades/buy/", payload, format="json")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(Trade.objects.filter(user=self.user).count(), 1)

    def test_login_does_not_issue_jwt_tokens(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"username": "api-player", "password": "safe-password-123"},
            format="json",
        )
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)

    def test_player_can_start_a_round_without_changing_persistent_wallet(self):
        GameMode.objects.create(
            slug="yolo",
            name="YOLO Mode",
            duration_seconds=10,
            description="A short round.",
        )
        self.client.force_login(self.user)
        response = self.client.post("/api/v1/rounds/start/", {"mode": "yolo"}, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], GameRound.Status.SCHEDULED)
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("10000.00"))

    def test_registration_requires_csrf_token(self):
        client = APIClient(enforce_csrf_checks=True)
        client.get("/api/v1/auth/csrf/")
        response = client.post(
            "/api/v1/auth/register/",
            {
                "username": "csrf-player",
                "email": "csrf@example.test",
                "password": "safe-password-123",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)


class WebSocketTests(TestCase):
    def test_public_feed_requires_explicit_valid_subscription(self):
        async_to_sync(self._test_public_feed)()

    async def _test_public_feed(self):
        communicator = WebsocketCommunicator(
            application,
            "/ws/market/",
            headers=[(b"origin", b"http://localhost")],
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        greeting = await communicator.receive_json_from()
        self.assertEqual(greeting["type"], "connected")
        await communicator.send_json_to({"action": "subscribe", "topics": ["prices"]})
        subscribed = await communicator.receive_json_from()
        self.assertEqual(subscribed["topics"], ["prices"])
        await get_channel_layer().group_send(
            "satta_market_prices",
            {"type": "market.message", "payload": {"type": "market.prices", "prices": []}},
        )
        message = await communicator.receive_json_from()
        self.assertEqual(message["type"], "market.prices")
        await communicator.disconnect()

    def test_private_feed_rejects_anonymous_connection(self):
        async_to_sync(self._test_private_feed)()

    async def _test_private_feed(self):
        communicator = WebsocketCommunicator(
            application,
            "/ws/private/",
            headers=[(b"origin", b"http://localhost")],
        )
        connected, _ = await communicator.connect()
        self.assertFalse(connected)
