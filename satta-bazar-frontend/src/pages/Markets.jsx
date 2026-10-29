
import { Search } from "lucide-react";
import { useState } from "react";
import AssetCard from "../components/AssetCard";

export default function Markets({ assets, onTrade }) {
  const [query, setQuery] = useState("");

  const filtered = assets.filter((asset) =>
    `${asset.name} ${asset.symbol}`.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div className="page-stack">
      <section className="welcome-row">
        <div>
          <p className="eyebrow">THE EXCHANGE OF NONSENSE</p>
          <h1>All <span>markets.</span> 📊</h1>
          <p className="muted">Research optional. Chai mandatory.</p>
        </div>
      </section>

      <label className="market-search">
        <Search size={18} />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search Chai, Billi, Chappal..."
        />
      </label>

      {filtered.length ? (
        <div className="assets-grid">
          {filtered.map((asset) => (
            <AssetCard
              key={asset.symbol}
              asset={asset}
              onTrade={onTrade}
            />
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <span>🕵️</span>
          <h3>Asset nahi mila, detective ji.</h3>
          <p>Try another search.</p>
        </div>
      )}
    </div>
  );
}
