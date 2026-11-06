"""Telegram Mini App initData tekshiruvi.

Telegram mini-appga `initData` qatorini beradi va uni bot token bilan
imzolaydi. Serverda imzoni tekshirmasak, har kim o'zini boshqa odam deb
ko'rsata oladi -- shuning uchun bu fayl butun autentifikatsiyaning asosi.

Imzo algoritmi (Web Apps uchun):
    secret = HMAC_SHA256(key="WebAppData", msg=bot_token)
    check  = "\\n".join("k=v" sorted, "hash" dan tashqari)
    hash   = HMAC_SHA256(key=secret, msg=check)

Diqqat: Login Widget boshqa kalit ishlatadi (SHA256(bot_token)). Ularni
almashtirib yuborish -- keng tarqalgan xato.
"""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

MAX_AGE = 24 * 60 * 60  # initData shuncha vaqtdan keyin eskirgan hisoblanadi


class AuthError(Exception):
    """initData ishonchsiz: imzo noto'g'ri, eskirgan yoki buzilgan."""


def _check_string(pairs):
    return "\n".join("%s=%s" % (k, v) for k, v in sorted(pairs) if k != "hash")


def verify(init_data, bot_token, now=None, max_age=MAX_AGE):
    """initData ni tekshirib, ichidagi `user` lug'atini qaytaradi.

    Hech narsaga ishonmaydi: imzo mos kelmasa yoki vaqt eskirgan bo'lsa
    AuthError ko'tariladi. Qaytgan user faqat Telegram imzolagan ma'lumot.
    """
    if not init_data:
        raise AuthError("initData bo'sh")
    if not bot_token:
        raise AuthError("BOT_TOKEN sozlanmagan")

    pairs = parse_qsl(init_data, keep_blank_values=True)
    data = dict(pairs)
    given = data.get("hash")
    if not given:
        raise AuthError("hash yo'q")

    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, _check_string(pairs).encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, given):
        raise AuthError("imzo mos kelmadi")

    try:
        auth_date = int(data.get("auth_date", "0"))
    except ValueError:
        raise AuthError("auth_date son emas")
    age = (time.time() if now is None else now) - auth_date
    if age > max_age:
        raise AuthError("initData eskirgan (%d soniya)" % int(age))
    if age < -60:
        raise AuthError("auth_date kelajakda")

    try:
        user = json.loads(data.get("user", "null"))
    except ValueError:
        raise AuthError("user JSON emas")
    if not isinstance(user, dict) or "id" not in user:
        raise AuthError("user yo'q")
    return user


def display_name(user):
    """Ekranda ko'rsatiladigan nom. Telegram first_name ni doim beradi."""
    name = " ".join(x for x in (user.get("first_name"), user.get("last_name")) if x)
    return (name or user.get("username") or "O'yinchi").strip()[:32]


def sign_for_test(fields, bot_token):
    """Test uchun: berilgan maydonlardan haqiqiy imzoli initData yasaydi."""
    from urllib.parse import urlencode

    pairs = sorted(fields.items())
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    h = hmac.new(secret, _check_string(pairs).encode(), hashlib.sha256).hexdigest()
    return urlencode(list(pairs) + [("hash", h)])
