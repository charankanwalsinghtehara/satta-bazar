from django.urls import path

from . import views

app_name = "game"

urlpatterns = [
    path("auth/csrf/", views.csrf_cookie, name="csrf"),
    path("auth/register/", views.register, name="register"),
    path("auth/login/", views.session_login, name="login"),
    path("auth/logout/", views.session_logout, name="logout"),
    path("auth/password-reset/", views.password_reset, name="password-reset"),
    path(
        "auth/password-reset/confirm/",
        views.password_reset_confirm,
        name="password-reset-confirm",
    ),
    path("auth/me/", views.me, name="me"),
    path("assets/", views.assets, name="assets"),
    path("assets/<str:symbol>/", views.asset_detail, name="asset-detail"),
    path("assets/<str:symbol>/history/", views.asset_history, name="asset-history"),
    path("market/overview/", views.market_overview, name="market-overview"),
    path("market/movers/", views.market_movers, name="market-movers"),
    path("market/events/", views.market_events, name="market-events"),
    path("market/news/", views.market_news, name="market-news"),
    path("wallet/", views.wallet_detail, name="wallet"),
    path("wallet/ledger/", views.wallet_ledger, name="wallet-ledger"),
    path("portfolio/", views.portfolio, name="portfolio"),
    path("portfolio/positions/", views.portfolio_positions, name="portfolio-positions"),
    path("portfolio/history/", views.portfolio_history, name="portfolio-history"),
    path("trades/buy/", views.trade_buy, name="trade-buy"),
    path("trades/sell/", views.trade_sell, name="trade-sell"),
    path("trades/", views.trades, name="trades"),
    path("trades/<uuid:trade_id>/", views.trade_detail, name="trade-detail"),
    path("game-modes/", views.game_modes, name="game-modes"),
    path("rounds/", views.rounds, name="rounds"),
    path("rounds/start/", views.start_round, name="round-start"),
    path("rounds/<uuid:round_id>/", views.round_detail, name="round-detail"),
    path("rounds/<uuid:round_id>/events/", views.round_events, name="round-events"),
    path("rounds/<uuid:round_id>/results/", views.round_results, name="round-results"),
    path("achievements/", views.achievements, name="achievements"),
    path("users/me/achievements/", views.my_achievements, name="my-achievements"),
    path("missions/", views.missions, name="missions"),
    path("missions/<int:mission_id>/claim/", views.mission_claim, name="mission-claim"),
    path("rewards/daily-claim/", views.reward_daily, name="daily-claim"),
    path("leaderboards/", views.leaderboard, name="leaderboards"),
    path("users/<str:username>/", views.public_profile, name="public-profile"),
]
