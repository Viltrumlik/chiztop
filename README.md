# Chiz va Top

Telegram Mini App: ikki kishilik chizish va topish o'yini. Biri chizadi,
ikkinchisi topadi, keyin navbat almashadi. O'zbekcha, inglizcha va ruscha
so'zlar.

Baza yo'q — xonalar xotirada yashaydi va o'yin tugashi bilan o'chadi.

## Qanday ishlaydi

```
A o'yinni ochadi     →  xona yaratiladi (kod: 7f2c)
A havolani yuboradi  →  t.me/<bot>/<app>?startapp=7f2c
B havolani bosadi    →  start_param o'qiladi, o'sha xonaga tushadi
                     →  ikkalasi WebSocket orqali ulanadi, o'yin boshlanadi
```

6 raund, har biri 60 soniya. Topuvchi tezligiga qarab 20–100 ball, chizuvchi
so'zi topilsa 50 ball. Vaqt o'tgani sari yordam harflari ochiladi.

## Mahalliy ishga tushirish

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
CHIZTOP_DEV=1 .venv/bin/python -m uvicorn server.main:app --port 8077
```

Keyin ikkita oynada oching — `CHIZTOP_DEV=1` initData tekshiruvini chetlab
o'tadi, shuning uchun Telegramsiz ham sinash mumkin:

```
http://localhost:8077/?dev_user=1          ← "Yangi o'yin", kodni oling
http://localhost:8077/?dev_user=2&room=XXXX
```

`CHIZTOP_DEV` faqat localhost uchun. Serverda hech qachon yoqmang.

## Telegramga ulash

1. [@BotFather](https://t.me/BotFather) da bot yarating → `BOT_TOKEN` ni oling
2. `/newapp` bilan mini-app qo'shing, URL sifatida saytingiz manzilini bering
3. `web/app.js` dagi `APP_LINK` ni to'ldiring:
   ```js
   const APP_LINK = "https://t.me/sizning_bot/play";
   ```
4. Serverda `BOT_TOKEN` ni o'rnating (`CHIZTOP_DEV` ni emas)

## Testlar

```bash
.venv/bin/python -m pytest tests/ -q
```

| Fayl | Nimani sinaydi |
|---|---|
| `test_auth.py` | initData imzosi — buzilgan, eskirgan, boshqa token |
| `test_rooms.py` | ball, javob taqqoslash, raundlar, so'z sirligi |
| `test_ws.py` | ikkita haqiqiy WebSocket klienti bilan to'liq o'yin |

## Tuzilishi

```
server/
  main.py      FastAPI, WebSocket, xonalar reyestri, umumiy taymer
  rooms.py     o'yin mantiqi — tarmoqni bilmaydi, vaqt tashqaridan keladi
  auth.py      Telegram initData imzosini tekshirish
  words.py     so'z ro'yxatlari
  words/       uz.txt, en.txt, ru.txt
web/
  index.html, style.css, app.js
```

## Ikki narsa, ataylab qilingan

**So'z hech qachon topuvchiga yuborilmaydi.** Serverda `state_for()` har
o'yinchiga alohida holat tayyorlaydi: chizuvchi so'zni ko'radi, topuvchi
faqat niqobni. Aks holda javobni tarmoq trafigidan o'qish mumkin bo'lardi.

**Koordinatalar 0..1 oralig'ida.** Piksel emas — telefon ekranlari har xil,
piksel yuborilsa rasm raqibda siljib ketadi.

## Joylashtirish

Bepul tariflar jimlikdan keyin serverni uxlatadi. Do'stingiz havolani
bosganda 50 soniya kutishi o'yinni o'ldiradi. Uxlamaydigan kichik VPS
(oyiga ~$4–5) bu o'yin uchun ishonchliroq.
