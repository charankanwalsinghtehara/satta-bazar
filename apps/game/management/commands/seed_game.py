from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.game.models import (
    Achievement,
    Asset,
    GameMode,
    HumourLine,
    MarketEventTemplate,
    MarketSettings,
    Mission,
)

ASSETS = [
    (
        "BILI",
        "BilliCoin",
        "Every lost remote is a bullish signal; every found remote is a rug pull.",
        "life",
        "48.00",
        ".08",
        "5.00",
        "500.00",
        "1.0",
    ),
    (
        "CHAI",
        "Chai Futures",
        "Powered by cutting chai, office gossip, and one suspiciously strong elaichi.",
        "food",
        "120.00",
        ".05",
        "10.00",
        "1000.00",
        "1.1",
    ),
    (
        "SAMOSA",
        "Samosa Securities",
        "Triangular asset. Diversification is also triangular, somehow.",
        "food",
        "75.00",
        ".07",
        "5.00",
        "750.00",
        "1.4",
    ),
    (
        "AUNTY",
        "Aunty Intelligence Network",
        "Insider information arrives before the Wi-Fi password does.",
        "family",
        "200.00",
        ".09",
        "10.00",
        "2000.00",
        "1.5",
    ),
    (
        "CHAPPAL",
        "Chappal Index",
        "A high-velocity footwear index. Please do not stand under it.",
        "life",
        "90.00",
        ".12",
        "5.00",
        "900.00",
        "1.4",
    ),
    (
        "MOSQ",
        "Mosquito Airlines",
        "Zero baggage fees, unlimited midnight departures around your ear.",
        "transport",
        "33.00",
        ".11",
        "2.00",
        "330.00",
        "1.5",
    ),
    (
        "SOCK",
        "Missing Sock Exchange",
        "One sock always moons while its pair remains in witness protection.",
        "life",
        "64.00",
        ".10",
        "3.00",
        "640.00",
        "1.3",
    ),
    (
        "BUFFER",
        "Buffering Capital",
        "A diversified portfolio currently loading at 99 percent.",
        "tech",
        "150.00",
        ".13",
        "5.00",
        "1500.00",
        "1.5",
    ),
    (
        "BUREAU",
        "Bureaucracy Ltd.",
        "Forms available in triplicate; approval expected sometime next fiscal year.",
        "life",
        "310.00",
        ".04",
        "25.00",
        "2500.00",
        ".8",
    ),
    (
        "LIGHT",
        "Lightbill Futures",
        "The only bill that arrives faster than your salary.",
        "life",
        "180.00",
        ".08",
        "10.00",
        "1800.00",
        "1.2",
    ),
    (
        "KABOOTAR",
        "Kabootar Holdings",
        "A low-latency, high-cooing neighborhood delivery network.",
        "transport",
        "82.00",
        ".07",
        "5.00",
        "820.00",
        ".9",
    ),
    (
        "BACKBENCH",
        "Backbenchers Ltd.",
        "Quietly disruptive; loudly asking, 'attendance kitni hai?'",
        "entertainment",
        "99.00",
        ".10",
        "5.00",
        "990.00",
        "1.1",
    ),
    (
        "UNCLE",
        "UncleJi Enterprises",
        "A diversified conglomerate of unsolicited advice and lawn chairs.",
        "family",
        "215.00",
        ".06",
        "10.00",
        "2150.00",
        "1.2",
    ),
    (
        "AUTO",
        "Auto-Raja Industries",
        "Meter runs on vibes; route optimisation remains a family secret.",
        "transport",
        "135.00",
        ".09",
        "5.00",
        "1350.00",
        "1.2",
    ),
    (
        "GAREEBI",
        "Gareebi Index",
        "Tracks the distance from payday to the last Parle-G biscuit.",
        "life",
        "41.00",
        ".14",
        "2.00",
        "410.00",
        "1.2",
    ),
    (
        "INFLU",
        "InfluencerCoin",
        "Backed by ring lights, affiliate links, and a rented sports car.",
        "tech",
        "275.00",
        ".15",
        "5.00",
        "2750.00",
        "1.5",
    ),
    (
        "CRICKET",
        "Cricket Kalesh Index",
        "Moves with every no-ball debate and every uncle's replay analysis.",
        "entertainment",
        "222.00",
        ".12",
        "5.00",
        "2220.00",
        "1.5",
    ),
    (
        "EXYAAD",
        "ExKiYaad Technologies",
        "An AI-powered notification that arrives exactly at 2:17 a.m.",
        "tech",
        "160.00",
        ".12",
        "5.00",
        "1600.00",
        "1.3",
    ),
    (
        "GROUPCHAT",
        "GroupChat Braincell Corp.",
        "One brain cell, 86 unread messages, and zero useful plans.",
        "tech",
        "115.00",
        ".14",
        "4.00",
        "1150.00",
        "1.5",
    ),
    (
        "PAPA",
        "Papa Approval Index",
        "Historically correlated with report cards and the electricity bill.",
        "family",
        "330.00",
        ".05",
        "20.00",
        "3300.00",
        "1.4",
    ),
    (
        "TUPPER",
        "Tupperware Lid Futures",
        "The lid exists. The matching dabba is currently untraceable.",
        "life",
        "125.00",
        ".09",
        "5.00",
        "1250.00",
        "1.2",
    ),
    (
        "LASTSAM",
        "Last Samosa Holdings",
        "Scarcity premium spikes when someone says, 'main nahi khaunga.'",
        "food",
        "190.00",
        ".13",
        "5.00",
        "1900.00",
        "1.5",
    ),
    (
        "FIVEMIN",
        "FiveMinuteAway Ltd.",
        "A timekeeping startup where five minutes equals an undisclosed hour.",
        "life",
        "57.00",
        ".12",
        "3.00",
        "570.00",
        "1.3",
    ),
    (
        "SHARMA",
        "SharmaJi Industries",
        "A performance benchmark nobody asked for, but everyone gets compared to.",
        "family",
        "440.00",
        ".07",
        "20.00",
        "4400.00",
        "1.4",
    ),
    (
        "GOVWEB",
        "Government Website Technologies",
        "Works on Tuesdays, unless it is a Tuesday.",
        "tech",
        "88.00",
        ".16",
        "2.00",
        "880.00",
        "1.5",
    ),
]

EVENTS = [
    (
        "Mummy Found Your Search History.",
        "Beta, explain this portfolio before I call the family group.",
        {"AUNTY": "-.10", "EXYAAD": "-.08", "PAPA": "-.06"},
    ),
    (
        "Wi-Fi Has Chosen Violence.",
        "The router is blinking like it knows what you did.",
        {"BUFFER": "-.16", "GROUPCHAT": "-.10", "GOVWEB": "-.08"},
    ),
    (
        "Sharma Ji's Son Got an Internship.",
        "Benchmark panic detected across the mohalla.",
        {"SHARMA": ".18", "BACKBENCH": "-.08", "PAPA": "-.05"},
    ),
    (
        "Aunty Spotted Something Suspicious.",
        "No evidence, full confidence, market-moving gossip.",
        {"AUNTY": ".16", "GROUPCHAT": "-.07", "UNCLE": ".05"},
    ),
    (
        "Government Website Is Down Again.",
        "Please refresh. The page has been loading since 2014.",
        {"GOVWEB": "-.20", "BUREAU": ".04", "BUFFER": "-.05"},
    ),
    (
        "One Samosa Remains at the Wedding.",
        "The room has gone quiet. Every investor for themselves.",
        {"SAMOSA": ".16", "LASTSAM": ".22", "CHAI": ".08"},
    ),
    (
        "Mosquito Entered Stealth Mode.",
        "Radar lost contact. Your sleep portfolio is down.",
        {"MOSQ": ".15", "CHAI": "-.03"},
    ),
    (
        "Friend Says Five Minutes Away.",
        "Satellite imagery confirms they are still at home.",
        {"FIVEMIN": ".18", "AUTO": ".06"},
    ),
    (
        "Papa Asked to Check the Electricity Bill.",
        "All speculative activity paused for a family review.",
        {"PAPA": "-.12", "LIGHT": ".15", "INFLU": "-.08"},
    ),
    (
        "Group Chat Lost Its Last Brain Cell.",
        "The 247th good morning image broke the exchange.",
        {"GROUPCHAT": "-.18", "BUFFER": "-.06"},
    ),
    (
        "Missing Sock Located.",
        "It was behind the washing machine. Nobody knows how.",
        {"SOCK": ".20", "BILI": ".08"},
    ),
    (
        "Uncle Took Control of the DJ.",
        "The playlist has entered a Kishore Kumar bull market.",
        {"UNCLE": ".12", "CRICKET": ".06", "BACKBENCH": ".05"},
    ),
    (
        "Chappal Detected in the Air.",
        "Please secure all fragile assets and younger siblings.",
        {"CHAPPAL": ".18", "AUNTY": ".05", "PAPA": ".06"},
    ),
    (
        "Exam Postponed.",
        "The classroom is euphoric; the syllabus remains undefeated.",
        {"BACKBENCH": ".18", "CHAI": ".08", "PAPA": "-.05"},
    ),
    (
        "Buffering at 99%.",
        "One percent away from greatness since yesterday.",
        {"BUFFER": "-.18", "GROUPCHAT": "-.05"},
    ),
    (
        "Unexpected Relative Arrived.",
        "The spare mattress and snack reserves are under pressure.",
        {"UNCLE": ".10", "SAMOSA": ".07", "GAREEBI": "-.04"},
    ),
    (
        "Last Tupperware Lid Disappeared.",
        "The container market has entered an existential crisis.",
        {"TUPPER": "-.18", "GAREEBI": "-.03"},
    ),
    (
        "Auto Driver Refused the Fare.",
        "The negotiation has been referred to the Supreme Court.",
        {"AUTO": "-.16", "FIVEMIN": ".04"},
    ),
    (
        "Cat Video Went Viral.",
        "The cat has more followers than your entire brokerage.",
        {"INFLU": ".12", "GROUPCHAT": ".08"},
    ),
    (
        "Chai Tapri Closed.",
        "The office productivity index has collapsed to zero.",
        {"CHAI": "-.18", "BACKBENCH": "-.05"},
    ),
    (
        "Electricity Bill Arrived.",
        "The AC usage audit has entered the chat.",
        {"LIGHT": ".20", "PAPA": "-.07", "INFLU": "-.06"},
    ),
    (
        "The Wi-Fi Router Is Being Restarted.",
        "Nobody touch anything for 30 seconds. Nobody.",
        {"BUFFER": "-.08", "GOVWEB": ".04"},
    ),
    (
        "The Wedding DJ Has Lost Power.",
        "Dance floor liquidity has dried up.",
        {"UNCLE": "-.12", "CRICKET": "-.04"},
    ),
    (
        "Internet Comment Section Exploded.",
        "Experts are arguing in all caps. Volatility is up.",
        {"GROUPCHAT": ".10", "INFLU": ".08", "CRICKET": ".06"},
    ),
    (
        "The Government Website Is Working for Five Minutes.",
        "Take a screenshot; this may never happen again.",
        {"GOVWEB": ".24", "BUREAU": "-.06", "BUFFER": ".05"},
    ),
]

HUMOUR = [
    ("buy", "hinglish", "Bhai ne buy button dabaya. Ab market ko bhi bata dena."),
    ("buy", "hinglish", "Buy high, cry higher. At least yahan paisa virtual hai."),
    ("buy", "en", "You bought the dip. The dip has scheduled another dip."),
    ("buy", "en", "Trade confirmed. Your confidence has been added to the balance sheet."),
    ("profit", "hinglish", "Profit hua hai. Please abhi financial podcast mat shuru karna."),
    ("profit", "hinglish", "Mount Everest bhi sharma gaya. Profit booked!"),
    ("profit", "en", "A profit! Please resist starting a financial podcast."),
    ("profit", "en", "Green numbers. Take a screenshot before they get shy."),
    ("loss", "hinglish", "Bhai, tu investor nahi, market ka donation box hai."),
    ("loss", "hinglish", "Bhai ne peak pe entry maari. Classic."),
    ("loss", "en", "Your portfolio is buffering harder than your Wi-Fi."),
    ("loss", "en", "A learning experience, sponsored by imaginary money."),
    ("reward", "hinglish", "Daily BB aa gaye. Ab sensible trade karna… ya mat karna."),
    ("reward", "en", "Virtual daily bucks claimed. Spend them like the pixels they are."),
    ("achievement", "hinglish", "Achievement unlocked. Ghar pe batana optional hai."),
    ("achievement", "en", "Achievement unlocked. Your spreadsheet is mildly impressed."),
    ("round", "hinglish", "Round khatam. Wallet aur positions safe—drama alag baat hai."),
    ("round", "en", "Round over. Your wallet and positions are still yours."),
    ("crash", "hinglish", "Portfolio ICU mein hai. Doctor bhi virtual hai."),
    ("crash", "en", "Portfolio ICU. The doctor is also virtual."),
]


class Command(BaseCommand):
    help = "Seed the fictional Satta Bazar assets, events, modes, and game rewards."

    def handle(self, *args, **options):
        created_assets = 0
        for (
            symbol,
            name,
            description,
            category,
            price,
            volatility,
            low,
            high,
            sensitivity,
        ) in ASSETS:
            defaults = {
                "name": name,
                "description": description,
                "category": category,
                "base_price": price,
                "current_price": price,
                "volatility": volatility,
                "min_price": low,
                "max_price": high,
                "event_sensitivity": sensitivity,
                "is_active": True,
            }
            asset, created = Asset.objects.get_or_create(symbol=symbol, defaults=defaults)
            if created:
                created_assets += 1
            else:
                for field, value in defaults.items():
                    if field != "current_price":
                        setattr(asset, field, value)
                asset.save()

        for name, commentary, effects in EVENTS:
            MarketEventTemplate.objects.get_or_create(
                name=name,
                defaults={
                    "commentary": commentary,
                    "effects": effects,
                    "duration_minutes": 5,
                    "rarity": 50,
                    "is_active": True,
                    "family_themed": any(
                        token in name.lower()
                        for token in ("mummy", "aunty", "sharma", "papa", "uncle")
                    ),
                },
            )

        for slug, name, duration, description, family, count in [
            (
                "yolo",
                "YOLO Mode",
                10,
                "A ten-second roller coaster. No actual yolo required.",
                False,
                0,
            ),
            (
                "papa-ki-pari",
                "Papa Ki Pari Mode",
                30,
                "Family-themed chaos with a strict virtual budget.",
                True,
                1,
            ),
            (
                "market-ka-postmortem",
                "Market Ka Postmortem",
                120,
                "A two-minute autopsy of questionable market decisions.",
                False,
                3,
            ),
        ]:
            GameMode.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "duration_seconds": duration,
                    "description": description,
                    "family_events_only": family,
                    "scheduled_events": count,
                    "is_active": True,
                },
            )

        for code, name, description, xp in [
            (
                "first-trade",
                "First Trade, First Regret",
                "You pressed buy. The market noticed.",
                10,
            ),
            (
                "five-trades",
                "Overthinking in Public",
                "Five trades completed. Maybe take a chai break.",
                20,
            ),
            (
                "first-profit",
                "Green Is a Feeling",
                "Closed a position above its average entry price.",
                15,
            ),
        ]:
            Achievement.objects.get_or_create(
                code=code,
                defaults={"name": name, "description": description, "xp_reward": xp},
            )

        now = timezone.now()
        for code, name, description, target, reward in [
            ("daily-trader", "Market Mein Hain", "Complete three virtual trades.", 3, "100.00"),
            ("try-the-chai", "Chai Pe Charcha", "Buy at least one unit of CHAI.", 1, "50.00"),
        ]:
            Mission.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "description": description,
                    "target": target,
                    "reward": reward,
                    "trigger": "buy_asset" if code == "try-the-chai" else "trade",
                    "target_symbol": "CHAI" if code == "try-the-chai" else "",
                    "active_from": now,
                    "active_until": now + timedelta(days=365),
                    "is_active": True,
                },
            )

        for category, language, text in HUMOUR:
            HumourLine.objects.get_or_create(category=category, language=language, text=text)

        MarketSettings.current()
        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete. {len(ASSETS)} assets and {len(EVENTS)} event templates available "
                f"({created_assets} assets created this run)."
            )
        )
