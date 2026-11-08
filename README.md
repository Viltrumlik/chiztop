# Chiz va Top

[O'zbekcha](README.uz.md) | English

A two-player "draw and guess" game that runs as a Telegram Mini App. One player
draws a word, the other guesses it, then they swap roles. Words come in Uzbek,
English and Russian. There is no database: rooms live in server memory and
disappear when the game ends.

## How it works

```
A opens the game      ->  a room is created (code: 7f2c)
A shares the link     ->  t.me/<bot>/<app>?startapp=7f2c
B taps the link       ->  start_param is read, B joins that room
                      ->  both connect over WebSocket and the game starts
```

- 6 rounds of 60 seconds; players alternate between drawing and guessing.
- The guesser earns 20–100 points depending on how fast they guess; the drawer
  earns 50 points when the word is guessed.
- Hint letters are revealed as time runs out (up to two).
- Guesses are compared ignoring case, spaces and Uzbek apostrophe variants
  (`o'`, `oʻ`, `o‘` ...); a guess one letter off is marked as "close".
- Drawing tools: five colours, three brush sizes, eraser, undo and clear canvas.
- A disconnected player keeps their seat for 30 seconds and gets the drawing
  replayed on reconnect.

## Features

- Telegram Mini App with server-side verification of the `initData` signature
- Real-time drawing over a single WebSocket per player (FastAPI)
- The secret word is never sent to the guesser: each player gets their own view
  of the game state
- Stroke coordinates are normalised to 0..1, so drawings look the same on any
  screen size
- Follows Telegram's light / dark theme
- Uzbek, English and Russian word lists
- `/health` endpoint for monitoring

## Tech stack

- Python 3, [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/), WebSockets
- Vanilla HTML / CSS / JavaScript with the [Telegram Web Apps](https://core.telegram.org/bots/webapps) script
- pytest for tests
- systemd + nginx for deployment

## Getting started

### Prerequisites

- Python 3 with `venv`
- For Telegram: a bot from [@BotFather](https://t.me/BotFather) and an HTTPS
  domain for the Mini App

### Run locally

```bash
git clone https://github.com/Viltrumlik/chiztop.git
cd chiztop
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
CHIZTOP_DEV=1 .venv/bin/python -m uvicorn server.main:app --port 8077
```

Open two browser windows. `CHIZTOP_DEV=1` skips the `initData` check, so you can
test without Telegram:

```
http://localhost:8077/?dev_user=1            <- "New game", copy the room code
http://localhost:8077/?dev_user=2&room=XXXX
```

`CHIZTOP_DEV` is for localhost only. Never enable it on a server: it disables
signature checking, so anyone could pretend to be anyone.

### Configuration

| Variable | Description |
|---|---|
| `BOT_TOKEN` | Token from @BotFather; used to verify the Mini App `initData` signature |
| `CHIZTOP_DEV` | `1` disables `initData` verification — local development only |

See [.env.example](.env.example). On a server the variables are read from
`/etc/chiztop.env` by the systemd unit ([deploy/chiztop.env.example](deploy/chiztop.env.example)).

### Connect to Telegram

1. Create a bot with [@BotFather](https://t.me/BotFather) (`/newbot`) and keep the token.
2. Add a Mini App with `/newapp`, using your site's HTTPS URL.
3. Set `APP_LINK` in `web/app.js` to the Mini App link:
   ```js
   const APP_LINK = "https://t.me/your_bot/play";
   ```
4. Set `BOT_TOKEN` on the server (and do not set `CHIZTOP_DEV`).

### Deploy

The server runs behind nginx as a systemd service on `127.0.0.1:8077`:

- [deploy/chiztop.service](deploy/chiztop.service) — systemd unit
- [deploy/nginx.conf](deploy/nginx.conf) — nginx site with WebSocket proxying
  (TLS is added by certbot); [deploy/nginx-subpath.conf](deploy/nginx-subpath.conf)
  serves the game under a path of an existing site instead
- [deploy/deploy.sh](deploy/deploy.sh) — rsync the code, install dependencies,
  restart and health-check: `./deploy/deploy.sh user@host`
- [deploy/README.md](deploy/README.md) — step-by-step guide (in Uzbek)

Rooms live in process memory, so the service must run with `--workers 1`, and
restarting it ends games in progress. Free hosting tiers that sleep when idle
make the first player wait for a cold start; a small always-on VPS works better.

## Tests

```bash
.venv/bin/pip install pytest httpx
.venv/bin/python -m pytest tests/ -q
```

| File | What it covers |
|---|---|
| `test_auth.py` | `initData` signature: tampered, expired, wrong token |
| `test_rooms.py` | scoring, answer matching, rounds, word secrecy |
| `test_ws.py` | a full game with two real WebSocket clients |

## Project structure

```
server/
  main.py      FastAPI app, WebSocket endpoint, room registry, shared timer
  rooms.py     game logic — no networking; time is passed in
  auth.py      Telegram initData signature verification
  words.py     word list loading
  words/       uz.txt, en.txt, ru.txt
web/
  index.html, style.css, app.js
tests/         pytest suite
deploy/        systemd unit, nginx configs, deploy script and guide
```

## License

[MIT](LICENSE) © Alisher Muhammadaliyev ([@Viltrumlik](https://github.com/Viltrumlik))
