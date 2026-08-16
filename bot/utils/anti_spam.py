import time
import re
from collections import defaultdict

BANNED_EMOJIS = [
    "🔞", "🖕", "💣", "🔪", "💊", "🎰", "🃏",
]

BANNED_KEYWORDS = [
    "casino", "18+", "seks", "nude", "xxx",
    "profilimda", "profilimga", "profilemga",
    "issiq lahzalar", "issiq lahzalarim",
    "hoziroq kiring", "hozir kiring",
    "tezda kiring",
    "sext", "sex", "erotic", "erotika",
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

warnings_cache = defaultdict(lambda: {"count": 0, "first_warn": 0, "last_warn": 0})


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
        if keyword.lower() in lower_text:
            return True

    spam_phrases = [
        r"profil\w*\s*(da|ga|ta)\s*\w*\s*(kiring|bosing|tashrif|tezda)",
        r"issiq\s*lahzalar\w*\s*(profil|profile)\w*",
        r"(hozir|hoziroq|tezda|teran)\s*(kiring|bosing|qarang|tashrif)",
        r"eng\s*issiq\s*lahzalar",
        r"profilimda\s*(kiring|bosing|qarang|tashrif)",
        r"(sek|sex|erotic|erotica|intim)\w+",
        r"(nude|naked|nudes)\w*",
        r"(casino|bet|poker|slot|jackpot)\w+",
        r"(telegram\.me|t\.me)/\+\w+",
        r"(onlyfans|fansly|linktr\.ee|linktree)",
    ]

    for pattern in spam_phrases:
        if re.search(pattern, lower_text):
            return True

    return False


def add_warning(user_id: int, group_id: int) -> int:
    key = f"{user_id}:{group_id}"
    now = time.time()

    data = warnings_cache[key]

    if data["first_warn"] > 0 and (now - data["first_warn"]) > WARN_EXPIRY:
        warnings_cache[key] = {"count": 0, "first_warn": 0, "last_warn": 0}
        data = warnings_cache[key]

    data["count"] += 1
    data["last_warn"] = now

    if data["first_warn"] == 0:
        data["first_warn"] = now

    return data["count"]


def get_warning_count(user_id: int, group_id: int) -> int:
    key = f"{user_id}:{group_id}"
    now = time.time()
    data = warnings_cache[key]

    if data["first_warn"] > 0 and (now - data["first_warn"]) > WARN_EXPIRY:
        warnings_cache[key] = {"count": 0, "first_warn": 0, "last_warn": 0}
        return 0

    return data["count"]


def reset_warnings(user_id: int, group_id: int):
    key = f"{user_id}:{group_id}"
    warnings_cache[key] = {"count": 0, "first_warn": 0, "last_warn": 0}


def cleanup_expired():
    now = time.time()
    expired_keys = []
    for key, data in warnings_cache.items():
        if data["first_warn"] > 0 and (now - data["first_warn"]) > WARN_EXPIRY:
            expired_keys.append(key)

    for key in expired_keys:
        del warnings_cache[key]

    return len(expired_keys)
