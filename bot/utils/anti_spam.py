import time
import re

BANNED_EMOJIS = [
    "🔞", "🖕", "💣", "🔪", "💊", "🎰", "🃏",
]

BANNED_KEYWORDS = [
    "casino", "18+", "seks", "nude", "xxx",
    "profilimda", "profilimga", "profilemga",
    "issiq lahzalar", "issiq lahzalarim",
    "hoziroq kiring", "hozir kiring",
    "tezda kiring",
    "sext", "erotic", "erotika",
    "intim", "intimate", "naked", "nudes",
    "onlyfans", "fansly", "linktr",
    "sikis", "porn", "hentai", "hentay",
    "chatrandom", "ome.tv", "chatspin",
]

SPAM_EMOJI_PAIRS = [
    ("💦", "💋"),
    ("💦", "🍑"),
    ("💦", "🍆"),
    ("💋", "🍑"),
    ("💋", "🍆"),
    ("🔥", "💦"),
    ("🔥", "💋"),
    ("😏", "💦"),
    ("😏", "💋"),
    ("😏", "🍑"),
    ("😏", "🍆"),
]

WARN_EXPIRY = 6 * 3600
MAX_WARNINGS = 3

SPAM_PATTERNS = [
    r"profil\w*\s*(da|ga|ta)\s*\w*\s*(kiring|bosing|tashrif|tezda)",
    r"issiq\s*lahzalar\w*\s*(profil|profile)\w*",
    r"(hozir|hoziroq|tezda|teran)\s*(kiring|bosing|qarang|tashrif)",
    r"eng\s*issiq\s*lahzalar",
    r"profilimda\s*(kiring|bosing|qarang|tashrif)",
    r"\b(sex|sexy|seks|porn|porno|hentai|hentay|erotic|erotica|intim|nude|naked|nudes)\w*\b",
    r"\b(casino|poker|jackpot|onlyfans|fansly)\b",
    r"(telegram\.me|t\.me)/\+\w+",
    r"(linktr\.ee|linktree)",
]

_spam_re = [re.compile(p) for p in SPAM_PATTERNS]


def is_spam(text: str) -> bool:
    if not text:
        return False

    for emoji in BANNED_EMOJIS:
        if emoji in text:
            return True

    for e1, e2 in SPAM_EMOJI_PAIRS:
        if e1 in text and e2 in text:
            return True

    lower_text = text.lower()
    for keyword in BANNED_KEYWORDS:
        if re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", lower_text):
            return True

    for pattern in _spam_re:
        if pattern.search(lower_text):
            return True

    return False
