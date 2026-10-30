
import Swal from "sweetalert2";
import { playTradeSound } from "../utils/tradeSounds";

const MEME_API = "https://meme-api.com/gimme";

function escapeHtml(value = "") {
  return String(value).replace(/[&<>"']/g, (char) => {
    const entities = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };

    return entities[char];
  });
}

async function fetchMeme() {
  const response = await fetch(MEME_API);

  if (!response.ok) {
    throw new Error("Could not load a meme.");
  }

  const data = await response.json();

  if (!data.url || !/\.(jpg|jpeg|png|gif|webp)(\?.*)?$/i.test(data.url)) {
    throw new Error("No suitable meme found.");
  }

  return {
    url: data.url,
    title: data.title || "Market ka haal 😂",
    subreddit: data.subreddit || "memes",
  };
}

async function loadAndRenderMeme() {
  const memeContainer = document.getElementById("satta-meme-container");
  const titleContainer = document.getElementById("satta-meme-title");
  const sourceContainer = document.getElementById("satta-meme-source");
  const nextButton = document.getElementById("satta-next-meme");

  if (!memeContainer) return;

  memeContainer.innerHTML =
    '<p style="color:#a1a1aa;padding:20px;">Meme loading... 😂</p>';

  if (nextButton) {
    nextButton.disabled = true;
    nextButton.textContent = "Loading...";
  }

  try {
    const meme = await fetchMeme();

    // The popup might have closed while the request was in progress.
    if (!document.getElementById("satta-meme-container")) return;

    memeContainer.innerHTML = `
      <img
        src="${escapeHtml(meme.url)}"
        alt="${escapeHtml(meme.title)}"
        style="
          display:block;
          max-width:100%;
          max-height:280px;
          object-fit:contain;
          margin:0 auto;
          border-radius:12px;
        "
      />
    `;

    if (titleContainer) {
      titleContainer.textContent = meme.title;
    }

    if (sourceContainer) {
      sourceContainer.textContent = `r/${meme.subreddit}`;
    }
  } catch {
    if (memeContainer.isConnected) {
      memeContainer.innerHTML = `
        <div style="padding:24px;text-align:center;color:#fbbf24;">
          <div style="font-size:42px;">🤡📉</div>
          <p>Meme server bhi loss mein hai!</p>
          <p style="font-size:13px;color:#a1a1aa;">
            Try loading another meme.
          </p>
        </div>
      `;
    }
  } finally {
    if (nextButton?.isConnected) {
      nextButton.disabled = false;
      nextButton.textContent = "Next Meme 😂";
    }
  }
}

export function showTradePopup(type, message) {
  const isBuy = type === "buy";

  const heading = isBuy
    ? "BUY KAR DIYA! 🚀"
    : "SELL KAR DIYA! 💸";

  const accentColor = isBuy ? "#4ade80" : "#fb7185";

  Swal.fire({
    title: heading,
    html: `
      <div style="text-align:center;">
        <p style="
          color:#e4e4e7;
          font-size:15px;
          line-height:1.6;
          margin:0 0 18px;
        ">
          ${escapeHtml(message)}
        </p>

        <div style="
          border:1px solid #27272a;
          background:#09090b;
          border-radius:14px;
          padding:14px;
          margin-top:12px;
        ">
          <div style="
            display:flex;
            align-items:center;
            justify-content:space-between;
            gap:10px;
            margin-bottom:12px;
          ">
            <strong style="color:#fafafa;font-size:14px;">
              Market ka reality check 🤡
            </strong>

            <span id="satta-meme-source" style="
              color:#a1a1aa;
              font-size:11px;
            ">
              Loading...
            </span>
          </div>

          <div id="satta-meme-container" style="
            min-height:100px;
            display:flex;
            justify-content:center;
            align-items:center;
            overflow:hidden;
          ">
            <p style="color:#a1a1aa;">Meme loading... 😂</p>
          </div>

          <p id="satta-meme-title" style="
            color:#d4d4d8;
            font-size:12px;
            line-height:1.5;
            margin:12px 0 0;
          "></p>

          <button
            id="satta-next-meme"
            type="button"
            style="
              width:100%;
              margin-top:14px;
              padding:10px 14px;
              border:1px solid #3f3f46;
              border-radius:9px;
              background:#18181b;
              color:#fafafa;
              font-weight:600;
              cursor:pointer;
            "
          >
            Next Meme 😂
          </button>
        </div>

        <p style="
          color:#71717a;
          font-size:11px;
          margin:14px 0 0;
        ">
          Virtual money only. Asli zindagi mein soch samajh ke! 😭
        </p>
      </div>
    `,

    background: "#18181b",
    color: "#fafafa",
    confirmButtonText: "Samajh Gaya 😂",
    confirmButtonColor: accentColor,
    customClass: {
      popup: "satta-trade-popup",
      confirmButton: "satta-trade-confirm",
    },

    buttonsStyling: true,
    showCloseButton: true,
    allowOutsideClick: true,
    width: 480,

    didOpen: () => {
      // Sound plays only after the trade popup has opened.
      // Do not call playTradeSound from the Buy/Sell button handler.
      void playTradeSound(type);

      const nextButton = document.getElementById("satta-next-meme");

      if (nextButton) {
        nextButton.onclick = () => {
          void loadAndRenderMeme();
        };
      }

      void loadAndRenderMeme();
    },
  });
}
