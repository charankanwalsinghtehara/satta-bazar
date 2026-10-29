
import { Search, Wallet } from "lucide-react";

export default function Navbar({ balance, user, onNavigate, onLogin, onLogout }) {
  return (
    <header className="topbar">
      <button
        className="mobile-brand"
        onClick={() => onNavigate("dashboard")}
      >
        <span className="brand-mark">₹</span>
        Satta Bazar
      </button>

      <div className="search-box">
        <Search size={17} />
        <input
          aria-label="Search markets"
          placeholder="Search assets, memes, markets..."
        />
        <kbd>⌘ K</kbd>
      </div>

      <div className="topbar-actions">
        <div className="wallet-pill">
          <Wallet size={17} />
          <span>{balance.toLocaleString("en-IN")} coins</span>
        </div>
        {user ? (
          <>
            <span className="account-name">{user.username}</span>
            <button className="account-button" onClick={onLogout}>
              Log out
            </button>
          </>
        ) : (
          <button className="account-button" onClick={onLogin}>
            Log in
          </button>
        )}
        <div className="avatar" title={user?.username || "Guest"}>
          {user?.username?.charAt(0).toUpperCase() || "?"}
        </div>
      </div>
    </header>
  );
}
