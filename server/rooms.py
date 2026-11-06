"""O'yin mantiqi: xona, raundlar, ball, javobni tekshirish.

Bu fayl tarmoq haqida hech narsa bilmaydi -- na WebSocket, na asyncio.
Vaqt har doim tashqaridan `now` bo'lib kiradi, shuning uchun testlar
kutib o'tirmaydi va natija barqaror. Uzatish va taymer `main.py` da.
"""

import random
import string
import unicodedata

from . import words

LOBBY, DRAWING, ROUND_END, GAME_END = "lobby", "drawing", "round_end", "game_end"

MAX_PLAYERS = 2
TOTAL_ROUNDS = 6
ROUND_SECONDS = 60
GRACE_SECONDS = 30          # uzilgan o'yinchi joyi shuncha ushlab turiladi
DRAWER_POINTS = 50          # so'zi topilsa chizuvchiga
MIN_GUESS_POINTS = 20
MAX_GUESS_POINTS = 100

# O'zbekcha apostrof variantlari: oʻ, o', o` -- hammasi bir xil hisoblanadi.
_APOSTROPHES = "'‘’ʻʼ`´"


def normalize(text):
    """Javobni taqqoslash uchun soddalashtiradi.

    Kichik harf, apostroflar olib tashlanadi, harf va raqamdan boshqa
    hamma narsa tushib qoladi. Shunda "Ko'prik", "koprik" va "ko prik"
    bir xil javob bo'ladi.
    """
    text = unicodedata.normalize("NFC", text or "").casefold()
    text = "".join(ch for ch in text if ch not in _APOSTROPHES)
    return "".join(ch for ch in text if ch.isalnum())


def _distance(a, b, limit=1):
    """Levenshtein masofasi, `limit` dan oshsa darrov to'xtaydi."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > limit:
            return limit + 1
        prev = cur
    return prev[-1]


def is_correct(guess, word):
    return bool(normalize(guess)) and normalize(guess) == normalize(word)


def is_close(guess, word):
    """Bitta harf xato -- "yaqin!" deb aytamiz, lekin to'g'ri deb emas."""
    g, w = normalize(guess), normalize(word)
    return bool(g) and g != w and len(w) > 3 and _distance(g, w) <= 1


def mask(word, revealed):
    """Topuvchi ko'radigan niqob: "q _ _ _ _ h"."""
    out = []
    for i, ch in enumerate(word):
        if not ch.isalnum():
            out.append(ch)
        else:
            out.append(ch if i in revealed else "_")
    return " ".join(out)


def guess_points(remaining, duration=ROUND_SECONDS):
    """Tez topgan ko'p ball oladi, lekin kech topgan ham quruq qolmaydi."""
    share = max(0.0, min(1.0, remaining / float(duration)))
    span = MAX_GUESS_POINTS - MIN_GUESS_POINTS
    return MIN_GUESS_POINTS + int(round(span * share))


def new_code(rng=random):
    return "".join(rng.choice(string.ascii_lowercase + string.digits) for _ in range(4))


class Player:
    def __init__(self, user_id, name):
        self.user_id = user_id
        self.name = name
        self.connected = True
        self.left_at = None

    def __repr__(self):
        return "<Player %s %r>" % (self.user_id, self.name)


class Room:
    """Bitta o'yin. Metodlar nima o'zgarganini lug'at bo'lib qaytaradi,
    chaqiruvchi (main.py) uni o'yinchilarga uzatadi."""

    def __init__(self, code, lang="uz", total_rounds=TOTAL_ROUNDS,
                 duration=ROUND_SECONDS, rng=None):
        if lang not in words.LANGS:
            raise ValueError("noma'lum til: %r" % lang)
        self.code = code
        self.lang = lang
        self.total_rounds = total_rounds
        self.duration = duration
        self.rng = rng or random.Random()
        self.players = {}
        self.order = []
        self.scores = {}
        self.phase = LOBBY
        self.round_no = 0
        self.drawer_id = None
        self.word = None
        self.revealed = set()
        self.used_words = set()
        self.strokes = []
        self.deadline = None
        self.winner_id = None

    # -- o'yinchilar ----------------------------------------------------

    @property
    def guesser_id(self):
        if self.drawer_id is None:
            return None
        others = [p for p in self.order if p != self.drawer_id]
        return others[0] if others else None

    def active_players(self):
        return [self.players[p] for p in self.order if self.players[p].connected]

    def add_player(self, user_id, name, now=0.0):
        """Xonaga qo'shadi yoki uzilgan o'yinchini qaytaradi."""
        if user_id in self.players:
            player = self.players[user_id]
            player.connected = True
            player.left_at = None
            player.name = name
            return player
        if len(self.players) >= MAX_PLAYERS:
            return None
        player = Player(user_id, name)
        self.players[user_id] = player
        self.order.append(user_id)
        self.scores.setdefault(user_id, 0)
        return player

    def disconnect(self, user_id, now=0.0):
        player = self.players.get(user_id)
        if player:
            player.connected = False
            player.left_at = now

    def is_abandoned(self, now):
        """Hamma ketgan va muhlat o'tgan bo'lsa, xonani o'chirsa bo'ladi."""
        if not self.players:
            return True
        return all(
            not p.connected and p.left_at is not None and now - p.left_at > GRACE_SECONDS
            for p in self.players.values()
        )

    def waiting_for_rejoin(self, now):
        """Kimdir uzilgan, lekin muhlati hali tugamagan."""
        return any(
            not p.connected and p.left_at is not None and now - p.left_at <= GRACE_SECONDS
            for p in self.players.values()
        )

    # -- raundlar -------------------------------------------------------

    def can_start(self):
        return self.phase == LOBBY and len(self.active_players()) == MAX_PLAYERS

    def start_round(self, now):
        """Keyingi raundni boshlaydi. Chizuvchi har raundda almashadi."""
        self.round_no += 1
        self.drawer_id = self.order[(self.round_no - 1) % len(self.order)]
        self.word = words.pick(self.lang, self.round_no, self.total_rounds,
                               self.used_words, self.rng)
        self.used_words.add(self.word)
        self.revealed = set()
        self.strokes = []
        self.phase = DRAWING
        self.deadline = now + self.duration
        return {"round": self.round_no, "drawer": self.drawer_id}

    def remaining(self, now):
        if self.deadline is None:
            return 0.0
        return max(0.0, self.deadline - now)

    def _letter_positions(self):
        return [i for i, ch in enumerate(self.word or "") if ch.isalnum()]

    def tick(self, now):
        """Vaqt o'tgani bilan nima o'zgarganini qaytaradi: yangi ochilgan
        harflar va raund tugaganini."""
        if self.phase != DRAWING:
            return {}
        changed = {}
        share = self.remaining(now) / float(self.duration)
        want = 0 if share > 0.5 else (1 if share > 0.25 else 2)
        positions = self._letter_positions()
        want = min(want, max(0, len(positions) - 2))  # hammasini ochib yubormaymiz
        while len(self.revealed) < want:
            hidden = [i for i in positions if i not in self.revealed]
            if not hidden:
                break
            self.revealed.add(self.rng.choice(hidden))
            changed["mask"] = self.masked()
        if self.remaining(now) <= 0:
            changed.update(self.end_round(now, guessed_by=None))
        return changed

    def masked(self):
        return mask(self.word or "", self.revealed)

    def submit_guess(self, user_id, text, now):
        """Topuvchining javobi. Natijani lug'at bo'lib qaytaradi."""
        if self.phase != DRAWING:
            return {"ok": False, "reason": "raund ketmayapti"}
        if user_id == self.drawer_id:
            return {"ok": False, "reason": "chizuvchi javob bera olmaydi"}
        if user_id not in self.players:
            return {"ok": False, "reason": "xonada yo'q"}
        if is_correct(text, self.word):
            points = guess_points(self.remaining(now), self.duration)
            self.scores[user_id] += points
            self.scores[self.drawer_id] += DRAWER_POINTS
            result = {"ok": True, "correct": True, "points": points,
                      "drawer_points": DRAWER_POINTS}
            result.update(self.end_round(now, guessed_by=user_id))
            return result
        return {"ok": True, "correct": False, "close": is_close(text, self.word)}

    def end_round(self, now, guessed_by=None):
        self.phase = ROUND_END
        self.deadline = None
        out = {"round_end": True, "word": self.word, "guessed_by": guessed_by,
               "scores": dict(self.scores)}
        if self.round_no >= self.total_rounds:
            out.update(self.end_game())
        return out

    def end_game(self):
        self.phase = GAME_END
        best = max(self.scores.values()) if self.scores else 0
        leaders = [p for p, s in self.scores.items() if s == best]
        self.winner_id = leaders[0] if len(leaders) == 1 else None
        return {"game_end": True, "winner": self.winner_id, "draw": self.winner_id is None,
                "scores": dict(self.scores)}

    def reset(self):
        """"Qayta o'ynash": ballar nolga tushadi, o'yinchilar qoladi."""
        self.phase = LOBBY
        self.round_no = 0
        self.drawer_id = None
        self.word = None
        self.revealed = set()
        self.used_words = set()
        self.strokes = []
        self.deadline = None
        self.winner_id = None
        self.scores = {p: 0 for p in self.players}

    # -- chizish --------------------------------------------------------

    def add_stroke(self, user_id, stroke):
        """Chiziqni saqlaydi, qayta ulangan o'yinchiga qaytadan chizish uchun."""
        if self.phase != DRAWING or user_id != self.drawer_id:
            return False
        if not isinstance(stroke, dict) or not stroke.get("p"):
            return False
        self.strokes.append(stroke)
        return True

    def undo_stroke(self, user_id):
        """Oxirgi chiziqni olib tashlaydi.

        Bitta chiziq tarmoqqa bir nechta bo'lak bo'lib chiqadi, hammasi
        bir xil `id` bilan -- shuning uchun bitta "Orqaga" butun chiziqni
        o'chiradi, uning oxirgi bo'lagini emas.
        """
        if self.phase != DRAWING or user_id != self.drawer_id or not self.strokes:
            return False
        last = self.strokes[-1].get("id")
        if last is None:
            self.strokes.pop()
            return True
        while self.strokes and self.strokes[-1].get("id") == last:
            self.strokes.pop()
        return True

    def clear_canvas(self, user_id):
        if self.phase != DRAWING or user_id != self.drawer_id:
            return False
        self.strokes = []
        return True

    # -- klientga yuboriladigan holat ------------------------------------

    def state_for(self, user_id, now):
        """Shu o'yinchi ko'rishi mumkin bo'lgan holat.

        So'z faqat chizuvchiga boradi. Topuvchiga niqob. Bu shart --
        aks holda topuvchi tarmoq trafigidan so'zni o'qiydi.
        """
        state = {
            "type": "state",
            "code": self.code,
            "lang": self.lang,
            "phase": self.phase,
            "round": self.round_no,
            "total_rounds": self.total_rounds,
            "you": user_id,
            "drawer": self.drawer_id,
            "remaining": round(self.remaining(now), 1),
            "scores": dict(self.scores),
            "players": [
                {"id": p.user_id, "name": p.name, "connected": p.connected}
                for p in (self.players[i] for i in self.order)
            ],
        }
        if self.phase == DRAWING:
            if user_id == self.drawer_id:
                state["word"] = self.word
            else:
                state["mask"] = self.masked()
                state["length"] = len(self._letter_positions())
        elif self.phase in (ROUND_END, GAME_END):
            state["word"] = self.word
            state["winner"] = self.winner_id
        return state
