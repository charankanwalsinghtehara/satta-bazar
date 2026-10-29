
import Swal from "sweetalert2";

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
    throw new Error("Could not fetch meme");
  }

  const data = await response.json();

  if (
    data.nsfw ||
    data.spoiler ||
    !data.url ||
    !/\.(jpg|jpeg|png|gif|webp)(\?.*)?$/i.test(data.url)
  ) {
    throw new Error("Meme unavailable");
  }

  return {
    url: data.url,
    title: data.title || "Market ne aukaat dikha di 😂",
    subreddit: data.subreddit || "memes",
  };
}

export function showTradePopup(type, message) {
  const isBuy = type === "buy";

  let currentMeme = null;
  let loadingMeme = false;

  const memeContent = () => {
    if (!currentMeme) {
      return `
        <div class="satta-meme-loading">
          😂 Meme loading... market bhi soch raha hai
        </div>
      `;
    }

    return `
      <div class="satta-meme-wrap">
        <img
          class="satta-meme-image"
          src="${escapeHtml(currentMeme.url)}"
          alt="Funny trading meme"
        />
        <p class="satta-meme-title">
          ${escapeHtml(currentMeme.title)}
        </p>
        <p class="satta-meme-source">
          Meme source: r/${escapeHtml(currentMeme.subreddit)}
        </p>
      </div>
    `;
  };

  const renderContent = () => `
    <div class="satta-trade-message">
      ${escapeHtml(message || "Trade successful! 😎")}
    </div>

    <div id="satta-meme-area">
      ${memeContent()}
    </div>

    <button
      type="button"
      id="satta-next-meme"
      class="satta-next-meme"
      ${loadingMeme ? "disabled" : ""}
    >
      ${loadingMeme ? "Loading meme..." : "😂 Next Meme"}
    </button>
  `;

  async function loadAndRenderMeme() {
    if (loadingMeme) return;

    loadingMeme = true;

    const button = document.getElementById("satta-next-meme");

    if (button) {
      button.disabled = true;
      button.textContent = "Finding dank memes...";
    }

    try {
      currentMeme = await fetchMeme();
    } catch {
      currentMeme = null;
    } finally {
      loadingMeme = false;
    }

    if (!Swal.isVisible()) return;

    const area = document.getElementById("satta-meme-area");

    if (area) {
      area.innerHTML = currentMeme
        ? memeContent()
        : `
          <div class="satta-meme-loading">
            Meme market down 📉 Try again, bhai!
          </div>
        `;
    }

    const nextButton = document.getElementById("satta-next-meme");

    if (nextButton) {
      nextButton.disabled = false;
      nextButton.textContent = "😂 Next Meme";
      nextButton.onclick = loadAndRenderMeme;
    }
  }

  Swal.fire({
    title: isBuy ? "🚀 Stock Bought!" : "💸 Stock Sold!",
    html: renderContent(),
    showCloseButton: true,
    showConfirmButton: false,
    allowOutsideClick: false,
    allowEscapeKey: false,
    heightAuto: false,
    background: "#171720",
    color: "#ffffff",
    customClass: {
      popup: "satta-trade-popup",
      closeButton: "satta-popup-close",
      htmlContainer: "satta-popup-content",
    },
    didOpen: () => {
      const nextButton = document.getElementById("satta-next-meme");

      if (nextButton) {
        nextButton.onclick = loadAndRenderMeme;
      }

      loadAndRenderMeme();
    },
  });
}
