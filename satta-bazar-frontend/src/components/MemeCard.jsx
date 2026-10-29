import { useCallback, useEffect, useState } from "react";

export default function MemeCard() {
  const [meme, setMeme] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchMeme = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const response = await fetch("https://meme-api.com/gimme");

      if (!response.ok) {
        throw new Error("Could not fetch a meme. Try again!");
      }

      const data = await response.json();

      if (!data.url || data.nsfw || data.spoiler) {
        throw new Error("This meme is unavailable. Try another!");
      }

      setMeme(data);
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMeme();
  }, [fetchMeme]);

  return (
    <section className="meme-card">
      <div className="meme-header">
        <div>
          <h2>Market Memes 😂</h2>
          <p>Because trading without drama is impossible.</p>
        </div>

        <span className="meme-badge">MEME ZONE</span>
      </div>

      <div className="meme-content">
        {loading ? (
          <div className="meme-message">
            <span className="meme-emoji">🤡</span>
            <p>Finding your next market meltdown...</p>
          </div>
        ) : error ? (
          <div className="meme-message">
            <span className="meme-emoji">📉</span>
            <p>{error}</p>
            <button
              className="meme-button"
              onClick={fetchMeme}
            >
              Try Again
            </button>
          </div>
        ) : meme ? (
          <>
            <h3 className="meme-title">{meme.title}</h3>

            <img
              className="meme-image"
              src={meme.url}
              alt={meme.title || "Random meme"}
              loading="lazy"
              onError={() => {
                setMeme(null);
                setError("This image could not load. Try another meme!");
              }}
            />

            <div className="meme-meta">
              {meme.subreddit && (
                <span>From r/{meme.subreddit}</span>
              )}

              {meme.postLink && (
                <a
                  href={meme.postLink}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Original post ↗
                </a>
              )}
            </div>
          </>
        ) : null}
      </div>

      <button
        className="meme-button"
        onClick={fetchMeme}
        disabled={loading}
      >
        {loading ? "Loading..." : "Next Meme 😂"}
      </button>

      <p className="meme-footer">
        Virtual losses. Real emotions. 💀
      </p>
    </section>
  );
}
