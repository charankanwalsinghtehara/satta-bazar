
const SOUND_API = "https://sfxmint.com/api/v1/search";

const SOUND_SEARCHES = [
  "funny cartoon boing",
  "comical fail sound",
  "dramatic impact",
  "sad trombone",
  "cartoon slip",
  "funny spring bounce",
];

let lastSoundSlug = "";
let audioPlayer = null;
let soundCache = {};

function randomItem(items) {
  return items[Math.floor(Math.random() * items.length)];
}

async function getFunnySound() {
  // Try different sound categories so repeated trades can sound different.
  const searches = [...SOUND_SEARCHES].sort(() => Math.random() - 0.5);

  for (const query of searches) {
    try {
      let sounds = soundCache[query];

      if (!sounds) {
        const response = await fetch(
          `${SOUND_API}?q=${encodeURIComponent(query)}&limit=10`
        );

        if (!response.ok) continue;

        const data = await response.json();

        // The API's standard response is an array of sound objects.
        sounds = Array.isArray(data) ? data : data.results;

        if (!Array.isArray(sounds)) continue;

        soundCache[query] = sounds;
      }

      const playable = sounds.filter(
        (sound) => sound.mp3_url && sound.slug !== lastSoundSlug
      );

      if (playable.length > 0) {
        return randomItem(playable);
      }
    } catch (error) {
      console.warn(`Sound search failed for "${query}":`, error);
    }
  }

  return null;
}

export async function playTradeSound() {
  try {
    const sound = await getFunnySound();

    if (!sound?.mp3_url) {
      console.warn("No suitable sound found.");
      return;
    }

    lastSoundSlug = sound.slug || "";

    if (audioPlayer) {
      audioPlayer.pause();
      audioPlayer.currentTime = 0;
    }

    audioPlayer = new Audio(sound.mp3_url);
    audioPlayer.volume = 0.8;

    await audioPlayer.play();
  } catch (error) {
    console.warn("Could not play trade sound:", error);
  }
}
