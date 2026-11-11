"""FastAPI server: WebSocket, xonalar reyestri va bitta umumiy taymer.

Xonalar xotirada yashaydi -- baza yo'q. O'yin tugaydi, xona o'chadi.
Butun o'yin mantiqi rooms.py da; bu fayl faqat uzatish bilan shug'ullanadi.
"""

import asyncio
import json
import os
import time
import urllib.parse
import urllib.request
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import rooms, words
from .auth import AuthError, display_name, verify

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, os.pardir, "web")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
DEV = os.environ.get("CHIZTOP_DEV") == "1"
TICK_SECONDS = 0.5

# Taklif tugmasi shu havolaga olib boradi. BotFather'dagi qisqa nom
# o'zgarsa, shu qator ham, web/app.js dagi APP_LINK ham yangilanishi kerak.
INVITE_LINK = os.environ.get("INVITE_LINK", "https://t.me/chiztop_bot/play")

# Taklif kartasi shu manzildan olinadi. Telegram rasmni o'zi yuklab oladi,
# ya'ni manzil tashqaridan ochiladigan bo'lishi shart.
PUBLIC_URL = os.environ.get("PUBLIC_URL", "https://chiz.viltrumlik.uz")

INVITE_TEXT = {
    "uz": {"title": "Chiz va Top",
           "desc": "Ikki kishilik chizish va topish o'yini",
           "body": "Chiz va Top o'ynaymizmi?",
           "button": "O'ynash"},
    "en": {"title": "Draw & Guess",
           "desc": "A two-player drawing and guessing game",
           "body": "Fancy a game of Draw & Guess?",
           "button": "Play"},
    "ru": {"title": "Рисуй и угадай",
           "desc": "Игра на двоих: рисуй и угадывай",
           "body": "Сыграем в «Рисуй и угадай»?",
           "button": "Играть"},
}

@asynccontextmanager
async def lifespan(_app):
    """Yagona fon taymerini ishga tushiradi va to'xtatadi."""
    task = asyncio.create_task(ticker())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(title="chiztop", lifespan=lifespan)

ROOMS = {}        # code -> Room
SOCKETS = {}      # code -> {user_id: WebSocket}


# -- taklif xabari --------------------------------------------------------

def _tg_call(method, params):
    """Telegram API ga so'rov. Bloklaydi -- faqat to_thread ichida chaqiriladi."""
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(
        "https://api.telegram.org/bot%s/%s" % (BOT_TOKEN, method), data=data)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


async def prepared_invite(user_id, code, lang="uz"):
    """Tayyor taklif xabarini yasaydi va uning id sini qaytaradi.

    Oddiy havola yuborilganda Telegram uni link-preview qilib ko'rsatadi --
    kartochka ichidagi "Launch" tugma emas, shunchaki rasm bir qismi. Bu
    yerda esa xabar inline_keyboard bilan oldindan tayyorlanadi, shuning
    uchun qabul qiluvchi haqiqiy bosiladigan tugma ko'radi.

    Klient qaytgan id ni Telegram.WebApp.shareMessage() ga beradi.
    Muvaffaqiyatsiz bo'lsa None qaytadi va klient eski usulga tushadi.
    """
    if not BOT_TOKEN:
        return None
    if lang not in INVITE_TEXT:
        lang = "uz"
    text = INVITE_TEXT[lang]
    photo = "%s/invite-%s.jpg" % (PUBLIC_URL, lang)
    # `photo` turi: xabar rasm bo'lib ketadi, matn esa caption bo'ladi.
    # `article` da faqat matn ketardi va suhbatda juda quruq ko'rinardi.
    result = {
        "type": "photo",
        "id": "inv-%s" % code,
        "photo_url": photo,
        "thumbnail_url": photo,
        "photo_width": 1280,
        "photo_height": 720,
        "title": text["title"],
        "description": text["desc"],
        "caption": text["body"],
        "reply_markup": {"inline_keyboard": [[
            {"text": text["button"],
             "url": "%s?startapp=%s" % (INVITE_LINK, code)},
        ]]},
    }
    try:
        resp = await asyncio.to_thread(_tg_call, "savePreparedInlineMessage", {
            "user_id": user_id,
            "result": json.dumps(result, ensure_ascii=False),
            "allow_user_chats": "true",
            "allow_group_chats": "true",
        })
    except Exception as exc:                      # tarmoq, timeout, JSON
        print("[share] %r" % exc)
        return None
    if not resp.get("ok"):
        print("[share] %s" % resp.get("description"))
        return None
    return resp["result"]["id"]


# -- uzatish --------------------------------------------------------------

async def send(ws, payload):
    try:
        await ws.send_json(payload)
    except (WebSocketDisconnect, RuntimeError):
        pass  # ulanish uzilgan; tozalash disconnect tarmog'ida bo'ladi


async def broadcast_state(room, now=None):
    """Har kimga o'ziga tegishli holatni yuboradi -- so'z faqat chizuvchiga."""
    now = time.time() if now is None else now
    for user_id, ws in list(SOCKETS.get(room.code, {}).items()):
        await send(ws, room.state_for(user_id, now))


async def broadcast(room, payload, skip=None):
    for user_id, ws in list(SOCKETS.get(room.code, {}).items()):
        if user_id != skip:
            await send(ws, payload)


# -- umumiy taymer --------------------------------------------------------

async def ticker():
    """Yagona fon vazifasi: vaqtni sanaydi, harf ochadi, bo'sh xonani o'chiradi.

    Har xonaga alohida task ochmaymiz -- bitta tsikl barchasini boshqaradi,
    shunda unutilgan task qolib ketmaydi.
    """
    while True:
        await asyncio.sleep(TICK_SECONDS)
        now = time.time()
        for code, room in list(ROOMS.items()):
            try:
                if room.is_abandoned(now):
                    ROOMS.pop(code, None)
                    SOCKETS.pop(code, None)
                    continue
                if room.due_for_next_round(now):
                    room.start_round(now)
                    await broadcast_state(room, now)
                    continue
                changed = room.tick(now)
                if changed.get("round_end"):
                    await broadcast(room, {"type": "round_end", **changed})
                    await broadcast_state(room, now)
                elif changed.get("mask"):
                    await broadcast(room, {"type": "mask", "mask": changed["mask"]},
                                    skip=room.drawer_id)
                elif room.phase == rooms.DRAWING:
                    await broadcast(room, {"type": "time",
                                           "remaining": round(room.remaining(now), 1)})
            except Exception as exc:  # bitta xona butun serverni yiqitmasin
                print("[ticker] %s: %r" % (code, exc))


# -- statik fayllar -------------------------------------------------------

@app.get("/health")
async def health():
    return {"ok": True, "rooms": len(ROOMS)}


# -- WebSocket ------------------------------------------------------------

def authenticate(message):
    """initData dan foydalanuvchini oladi. DEV rejimida soxta foydalanuvchi."""
    if DEV and message.get("dev_user"):
        uid = int(message["dev_user"])
        return {"id": uid, "first_name": "Dev%d" % uid}
    return verify(message.get("initData", ""), BOT_TOKEN)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    room = None
    user_id = None
    try:
        first = await ws.receive_json()
        if first.get("type") != "join":
            await send(ws, {"type": "error", "error": "avval join yuboring"})
            return await ws.close()

        try:
            user = authenticate(first)
        except AuthError as exc:
            await send(ws, {"type": "error", "error": "auth: %s" % exc})
            return await ws.close()
        user_id = int(user["id"])
        name = display_name(user)

        code = (first.get("room") or "").strip().lower()
        if code:
            room = ROOMS.get(code)
            if room is None:
                await send(ws, {"type": "error", "error": "xona topilmadi"})
                return await ws.close()
        else:
            lang = first.get("lang", "uz")
            if lang not in words.LANGS:
                lang = "uz"
            code = rooms.new_code()
            while code in ROOMS:
                code = rooms.new_code()
            room = rooms.Room(code, lang=lang)
            ROOMS[code] = room
            SOCKETS[code] = {}

        if room.add_player(user_id, name, time.time()) is None:
            await send(ws, {"type": "error", "error": "xona to'la"})
            return await ws.close()

        SOCKETS.setdefault(code, {})[user_id] = ws
        await send(ws, {"type": "joined", "code": code, "you": user_id})
        if room.strokes:
            await send(ws, {"type": "replay_strokes", "strokes": room.strokes})
        await broadcast_state(room)

        if room.can_start():
            room.start_round(time.time())
            await broadcast_state(room)

        async for message in _messages(ws):
            await handle(room, user_id, message)

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        print("[ws] %r" % exc)
    finally:
        if room is not None and user_id is not None:
            room.disconnect(user_id, time.time())
            SOCKETS.get(room.code, {}).pop(user_id, None)
            await broadcast_state(room)


async def _messages(ws):
    while True:
        yield await ws.receive_json()


async def handle(room, user_id, message):
    kind = message.get("type")

    if kind == "stroke":
        if room.add_stroke(user_id, message.get("stroke")):
            await broadcast(room, {"type": "stroke", "stroke": message["stroke"]},
                            skip=user_id)

    elif kind == "undo":
        if room.undo_stroke(user_id):
            # Nechta bo'lak o'chganini klient bilmaydi, shuning uchun
            # to'liq ro'yxatni qayta yuboramiz -- chiziqlar kichik.
            await broadcast(room, {"type": "replay_strokes", "strokes": room.strokes},
                            skip=user_id)

    elif kind == "clear":
        if room.clear_canvas(user_id):
            await broadcast(room, {"type": "clear"}, skip=user_id)

    elif kind == "guess":
        text = (message.get("text") or "")[:64]
        result = room.submit_guess(user_id, text, time.time())
        if not result.get("ok"):
            return
        await broadcast(room, {"type": "guess", "by": user_id, "text": text,
                               "correct": result["correct"],
                               "close": result.get("close", False)})
        if result.get("round_end"):
            # Keyingi raundni taymer boshlaydi, ROUND_GAP o'tgach.
            await broadcast(room, {"type": "round_end", **result})
            await broadcast_state(room)

    elif kind == "replay":
        if room.phase == rooms.GAME_END:
            room.reset()
            await broadcast_state(room)
            if room.can_start():
                room.start_round(time.time())
                await broadcast_state(room)

    elif kind == "share":
        # Javob faqat so'ragan o'yinchiga ketadi, broadcast emas.
        ws = SOCKETS.get(room.code, {}).get(user_id)
        if ws is None:
            return
        mid = await prepared_invite(user_id, room.code, room.lang)
        if mid:
            await send(ws, {"type": "share_ready", "id": mid})
        else:
            await send(ws, {"type": "share_failed"})


# Statik fayllar oxirida ulanadi, aks holda /ws va /health ni bosib ketadi.
if os.path.isdir(WEB):
    app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
