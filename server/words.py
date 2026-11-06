"""So'z ro'yxatlari.

Format: har qatorda "daraja so'z", daraja 1 (oson) dan 3 (qiyin) gacha.
`#` bilan boshlangan qatorlar izoh.
"""

import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
LANGS = ("uz", "en", "ru")
_cache = {}


def load(lang):
    """Tilning so'zlarini {daraja: [so'z, ...]} ko'rinishida qaytaradi."""
    if lang not in LANGS:
        raise ValueError("noma'lum til: %r" % lang)
    if lang not in _cache:
        tiers = {1: [], 2: [], 3: []}
        path = os.path.join(HERE, "words", lang + ".txt")
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                tier, _, word = line.partition(" ")
                if word and tier.isdigit() and int(tier) in tiers:
                    tiers[int(tier)].append(word.strip())
        _cache[lang] = tiers
    return _cache[lang]


def tier_for_round(round_no, total_rounds):
    """Raundlar o'tgani sari so'zlar qiyinlashadi."""
    if total_rounds <= 1:
        return 1
    share = (round_no - 1) / (total_rounds - 1)
    return 1 if share < 0.34 else (2 if share < 0.67 else 3)


def pick(lang, round_no, total_rounds, used=(), rng=random):
    """Shu raund uchun so'z tanlaydi, allaqachon ishlatilganini qaytarmaydi."""
    tiers = load(lang)
    wanted = tier_for_round(round_no, total_rounds)
    for tier in (wanted, 2, 1, 3):  # kerakli daraja tugasa, qo'shnisidan olinadi
        pool = [w for w in tiers[tier] if w not in used]
        if pool:
            return rng.choice(pool)
    return rng.choice(tiers[1])
