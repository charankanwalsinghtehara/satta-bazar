
import { useEffect, useState } from "react";
import {
  Activity,
  ArrowLeftRight,
  LayoutDashboard,
  Trophy,
  Zap,
  Menu,
  X,
  Coffee,
  TrendingUp,
} from "lucide-react";

import Navbar from "./components/Navbar";
import Dashboard from "./pages/Dashboard";
import Markets from "./pages/Markets";
import Leaderboard from "./pages/Leaderboard";

import {
  ApiError,
  buyAsset,
  getLeaderboard,
  getMarketMovers,
  getMarketOverview,
  getAssetHistory,
  getMe,
  getWallet,
  login,
  logout,
  register,
  sellAsset,
} from "../services/api";

import "./App.css";
import { showTradePopup } from "./components/TradePopup";

const assetStyles = {
  food: { emoji: "☕", color: "#c98b57" },
  tech: { emoji: "🌀", color: "#38bdf8" },
  family: { emoji: "🕵️", color: "#4ade80" },
  transport: { emoji: "🛺", color: "#fb7185" },
  entertainment: { emoji: "🎭", color: "#a78bfa" },
  life: { emoji: "✨", color: "#fbbf24" },
};

const navigation = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "markets", label: "Markets", icon: TrendingUp },
  { id: "leaderboard", label: "Leaderboard", icon: Trophy },
];

export default function App() {
  const [page, setPage] = useState("dashboard");
  const [balance, setBalance] = useState(0);
  const [assets, setAssets] = useState([]);
  const [events, setEvents] = useState([]);
  const [marketPaused, setMarketPaused] = useState(false);
  const [rankings, setRankings] = useState([]);
  const [marketData, setMarketData] = useState([]);
  const [user, setUser] = useState(null);
  const [notice, setNotice] = useState("");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [authMode, setAuthMode] = useState("");
  const [authBusy, setAuthBusy] = useState(false);
  const [authError, setAuthError] = useState("");

  const [authForm, setAuthForm] = useState({
    username: "",
    email: "",
    password: "",
  });

  async function loadMarket() {
    const [overview, movers, leaderboard] = await Promise.all([
      getMarketOverview(),
      getMarketMovers(),
      getLeaderboard(),
    ]);

    const changes = new Map(
      movers.movers.map((mover) => [
        mover.symbol,
        Number(mover.change_percent),
      ]),
    );

    const assets = overview.assets.map((asset) => ({
      ...asset,
      price: Number(asset.current_price),
      change: changes.get(asset.symbol) || 0,
      joke: asset.description,
      ...(assetStyles[asset.category] || assetStyles.life),
    }));

    let historyData = [];

    if (assets.length) {
      const chartAsset =
        assets.find(
          (asset) => asset.symbol === movers.movers[0]?.symbol,
        ) || assets[0];

      const history = await getAssetHistory(chartAsset.symbol);

      historyData = history.results
        .slice()
        .reverse()
        .map((snapshot) => ({
          time: new Date(snapshot.created_at).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
          value: Number(snapshot.price),
        }));
    }

    return {
      assets,
      events: overview.active_events,
      marketPaused: overview.paused,
      rankings: leaderboard.rankings,
      marketData: historyData,
    };
  }

  function applyMarketData(data) {
    setAssets(data.assets);
    setEvents(data.events);
    setMarketPaused(data.marketPaused);
    setRankings(data.rankings);
    setMarketData(data.marketData);
  }

  async function refreshMarket() {
    applyMarketData(await loadMarket());
  }

  useEffect(() => {
    let active = true;

    loadMarket()
      .then((data) => {
        if (active) {
          applyMarketData(data);
        }
      })
      .catch((error) => {
        if (active) {
          setNotice(`Could not load market data: ${error.message}`);
        }
      });

    getMe()
      .then(async (profile) => {
        if (!active) return;

        setUser(profile);

        const wallet = await getWallet();

        if (active) {
          setBalance(Number(wallet.balance));
        }
      })
      .catch((error) => {
        if (!active && error instanceof ApiError) return;

        if (
          error instanceof ApiError &&
          [401, 403].includes(error.status)
        ) {
          if (active) {
            setUser(null);
            setBalance(0);
          }

          return;
        }

        if (active) {
          setNotice(`Could not load account: ${error.message}`);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  async function handleTrade(asset, side) {
    if (!user) {
      setAuthMode("login");
      setNotice("Log in to trade with your virtual wallet.");
      return;
    }

    let result;

    try {
      const tradeAction = side === "buy" ? buyAsset : sellAsset;

      result = await tradeAction({
        symbol: asset.symbol,
        quantity: "1",
        idempotency_key: crypto.randomUUID(),
        language: "hinglish",
      });
    } catch (error) {
      setNotice(`Trade failed: ${error.message}`);
      return;
    }

    // Update the virtual wallet balance after successful trade.
    setBalance(Number(result.portfolio.cash_balance));

    // Show the centered popup only after Django confirms success.
    // It stays open until the user clicks the close button.
    showTradePopup(
      side,
      result.roast ||
        (side === "buy"
          ? `🚀 Bought ${asset.name} successfully!`
          : `💸 Sold ${asset.name} successfully!`),
    );

    // Refresh market data without hiding the trade popup.
    try {
      await refreshMarket();
    } catch (error) {
      setNotice(
        `Trade completed, but market refresh failed: ${error.message}`,
      );
    }
  }

  function navigate(id) {
    setPage(id);
    setMobileOpen(false);
    setNotice("");
  }

  async function handleAuthSubmit(event) {
    event.preventDefault();

    setAuthBusy(true);
    setAuthError("");

    try {
      const response =
        authMode === "register"
          ? await register(authForm)
          : await login({
              username: authForm.username,
              password: authForm.password,
            });

      const profile = response.user || response;

      setUser(profile);

      const wallet = response.wallet || (await getWallet());

      setBalance(Number(wallet.balance));
      setAuthMode("");
      setAuthForm({
        username: "",
        email: "",
        password: "",
      });

      setNotice(
        `Welcome, ${profile.username}! Your virtual wallet is ready.`,
      );
    } catch (error) {
      setAuthError(error.message);
    } finally {
      setAuthBusy(false);
    }
  }

  async function handleLogout() {
    try {
      await logout();

      setUser(null);
      setBalance(0);
      setNotice("You have been logged out.");
    } catch (error) {
      setNotice(`Could not log out: ${error.message}`);
    }
  }

  return (
    <div className="app-shell">
      {mobileOpen && (
        <button
          className="mobile-overlay"
          aria-label="Close navigation"
          onClick={() => setMobileOpen(false)}
        />
      )}

      <aside
        className={`sidebar ${mobileOpen ? "sidebar-open" : ""}`}
      >
        <div className="brand">
          <div className="brand-mark">
            <Coffee size={23} />
          </div>

          <div>
            <strong>SATTA BAZAR</strong>
            <span>THE CHAOS EXCHANGE</span>
          </div>

          <button
            className="icon-button close-sidebar"
            aria-label="Close menu"
            onClick={() => setMobileOpen(false)}
          >
            <X size={19} />
          </button>
        </div>

        <div className="sidebar-label">PLAYGROUND</div>

        <nav className="side-nav">
          {navigation.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              className={`nav-item ${page === id ? "active" : ""}`}
              onClick={() => navigate(id)}
            >
              <Icon size={19} />
              <span>{label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-label">GAME MODES</div>

        <button
          className="nav-item"
          onClick={() => setNotice("YOLO mode is coming soon.")}
        >
          <Zap size={19} />
          <span>YOLO Mode</span>
          <span className="coming-tag">SOON</span>
        </button>

        <button
          className="nav-item"
          onClick={() =>
            setNotice("Trade history is available through the Django API.")
          }
        >
          <ArrowLeftRight size={19} />
          <span>Trade History</span>
        </button>

        <div className="sidebar-spacer" />

        <div className="sidebar-footer">
          <div className="footer-status">
            <span className="live-dot" />
            Demo system online
          </div>

          <p>Zero real money. Maximum bakchodi.</p>
          <span className="version-label">
            SATTA BAZAR · DEMO V1
          </span>
        </div>
      </aside>

      <div className="main-column">
        <div className="mobile-toolbar">
          <button
            className="icon-button"
            aria-label="Open navigation"
            onClick={() => setMobileOpen(true)}
          >
            <Menu size={21} />
          </button>

          <span>
            <Coffee size={17} /> SATTA BAZAR
          </span>

          <Activity size={18} />
        </div>

        <Navbar
          balance={balance}
          user={user}
          onNavigate={navigate}
          onLogin={() => {
            setAuthMode("login");
            setAuthError("");
          }}
          onLogout={handleLogout}
        />

        <main className="main-content">
          {notice && (
            <div className="notice-banner" role="status">
              <span>{notice}</span>

              <button
                className="notice-close"
                onClick={() => setNotice("")}
                aria-label="Dismiss notification"
              >
                <X size={16} />
              </button>
            </div>
          )}

          {authMode && (
            <form
              className="panel auth-panel"
              onSubmit={handleAuthSubmit}
            >
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">YOUR VIRTUAL ACCOUNT</p>
                  <h2>
                    {authMode === "register"
                      ? "Create account"
                      : "Log in"}
                  </h2>
                </div>

                <button
                  type="button"
                  className="button button-sell"
                  onClick={() => setAuthMode("")}
                >
                  Close
                </button>
              </div>

              <div className="auth-fields">
                <label>
                  Username
                  <input
                    autoComplete="username"
                    required
                    value={authForm.username}
                    onChange={(event) =>
                      setAuthForm({
                        ...authForm,
                        username: event.target.value,
                      })
                    }
                  />
                </label>

                {authMode === "register" && (
                  <label>
                    Email
                    <input
                      type="email"
                      autoComplete="email"
                      required
                      value={authForm.email}
                      onChange={(event) =>
                        setAuthForm({
                          ...authForm,
                          email: event.target.value,
                        })
                      }
                    />
                  </label>
                )}

                <label>
                  Password
                  <input
                    type="password"
                    autoComplete={
                      authMode === "register"
                        ? "new-password"
                        : "current-password"
                    }
                    required
                    value={authForm.password}
                    onChange={(event) =>
                      setAuthForm({
                        ...authForm,
                        password: event.target.value,
                      })
                    }
                  />
                </label>
              </div>

              {authError && (
                <p className="auth-error" role="alert">
                  {authError}
                </p>
              )}

              <div className="auth-actions">
                <button
                  className="button button-buy"
                  disabled={authBusy}
                >
                  {authBusy
                    ? "Please wait..."
                    : authMode === "register"
                      ? "Create account"
                      : "Log in"}
                </button>

                <button
                  type="button"
                  className="auth-switch"
                  onClick={() => {
                    setAuthMode(
                      authMode === "register" ? "login" : "register",
                    );
                    setAuthError("");
                  }}
                >
                  {authMode === "register"
                    ? "Already have an account? Log in"
                    : "New here? Create an account"}
                </button>
              </div>
            </form>
          )}

          {page === "dashboard" && (
            <Dashboard
              balance={balance}
              assets={assets}
              events={events}
              marketData={marketData}
              marketPaused={marketPaused}
              rank={
                rankings.findIndex(
                  (entry) => entry.username === user?.username,
                ) + 1
              }
              onTrade={handleTrade}
            />
          )}

          {page === "markets" && (
            <Markets assets={assets} onTrade={handleTrade} />
          )}

          {page === "leaderboard" && (
            <Leaderboard rankings={rankings} />
          )}
        </main>
      </div>
    </div>
  );
}
