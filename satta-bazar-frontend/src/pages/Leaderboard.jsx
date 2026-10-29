
import { Trophy } from "lucide-react";

export default function Leaderboard({ rankings }) {
  return (
    <div className="page-stack">
      <section className="welcome-row">
        <div>
          <p className="eyebrow">FLEX KARNE KA TIME</p>
          <h1>Hall of <span>legends.</span> 🏆</h1>
          <p className="muted">Some are skilled. Some are just suspiciously lucky.</p>
        </div>
      </section>

      <section className="panel leaderboard-panel">
        <div className="panel-heading">
          <h2><Trophy size={20} /> Top virtual traders</h2>
          <span className="session-chip">LIVE RANKINGS</span>
        </div>

        {rankings.slice(0, 20).map((player, index) => (
          <div
            className="leader-row"
            key={player.username}
          >
            <span className="leader-rank">
              {index < 3 ? ["🥇", "🥈", "🥉"][index] : `#${index + 1}`}
            </span>
            <span className="leader-avatar">{player.username.charAt(0).toUpperCase()}</span>
            <strong>{player.username}</strong>
            <span className="leader-coins">
              {Number(player.score).toLocaleString("en-IN")} coins
            </span>
          </div>
        ))}
        {!rankings.length && (
          <p className="muted small">No leaderboard entries are available yet.</p>
        )}
      </section>
    </div>
  );
}
