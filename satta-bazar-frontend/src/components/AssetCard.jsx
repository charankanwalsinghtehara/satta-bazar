
import { ArrowDownRight, ArrowUpRight } from "lucide-react";

export default function AssetCard({ asset, onTrade }) {
  const rising = asset.change >= 0;

  return (
    <article className="asset-card">
      <div className="asset-card-top">
        <div
          className="asset-icon"
          style={{ "--asset-color": asset.color }}
        >
          {asset.emoji}
        </div>

        <span className={`change-chip ${rising ? "up" : "down"}`}>
          {rising ? (
            <ArrowUpRight size={14} />
          ) : (
            <ArrowDownRight size={14} />
          )}
          {Math.abs(asset.change).toFixed(2)}%
        </span>
      </div>

      <p className="asset-symbol">{asset.symbol}</p>
      <h3>{asset.name}</h3>

      <div className="asset-price">
        {asset.price.toLocaleString("en-IN")} <small>coins</small>
      </div>

      <p className="asset-joke">{asset.joke}</p>

      <div className="asset-actions">
        <button
          className="button button-buy"
          onClick={() => onTrade(asset, "buy")}
        >
          Buy
        </button>
        <button
          className="button button-sell"
          onClick={() => onTrade(asset, "sell")}
        >
          Sell
        </button>
      </div>
    </article>
  );
}
