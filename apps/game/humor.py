import random

from .models import HumourLine

FALLBACKS = {
    "buy": {
        "hinglish": "Bhai ne buy button dabaya. Ab market ko bhi bata dena.",
        "en": "You bought the dip. The dip has scheduled another dip.",
    },
    "profit": {
        "hinglish": "Profit hua hai. Please abhi financial podcast mat shuru karna.",
        "en": "A profit! Please resist starting a financial podcast.",
    },
    "loss": {
        "hinglish": "Bhai, tu investor nahi, market ka donation box hai.",
        "en": "Your portfolio is buffering harder than your Wi-Fi.",
    },
    "reward": {
        "hinglish": "Daily BB aa gaye. Ab sensible trade karna… ya mat karna.",
        "en": "Virtual daily bucks claimed. Spend them like the pixels they are.",
    },
    "achievement": {
        "hinglish": "Achievement unlocked. Ghar pe batana optional hai.",
        "en": "Achievement unlocked. Your spreadsheet is mildly impressed.",
    },
    "round": {
        "hinglish": "Round khatam. Wallet aur positions safe—drama alag baat hai.",
        "en": "Round over. Your wallet and positions are still yours.",
    },
    "crash": {
        "hinglish": "Portfolio ICU mein hai. Doctor bhi virtual hai.",
        "en": "Portfolio ICU. The doctor is also virtual.",
    },
}


def choose_roast(category, language="hinglish", seed=None):
    if category not in FALLBACKS:
        raise ValueError(f"Unknown humour category: {category}")
    language = language if language in {"hinglish", "en"} else "hinglish"
    lines = list(HumourLine.objects.filter(category=category, language=language, is_active=True))
    if not lines:
        return FALLBACKS[category][language]
    return random.Random(seed).choice(lines).text


def trade_humour(trade, language="hinglish"):
    category = "buy" if trade.side == "buy" else "profit" if trade.realized_pnl > 0 else "loss"
    return choose_roast(category, language=language, seed=str(trade.pk))
