"""Ikkita haqiqiy WebSocket klienti bilan uchdan-uchga sinov.

DEV rejimida ishlaydi: initData o'rniga `dev_user` beriladi, shunda test
uchun bot token kerak emas. Tekshiruvning o'zi test_auth.py da sinaladi.
"""

import os

import pytest

os.environ["CHIZTOP_DEV"] = "1"
os.environ.setdefault("BOT_TOKEN", "123456:TEST")

from fastapi.testclient import TestClient  # noqa: E402  (env dan keyin)

from server.main import ROOMS, SOCKETS, app  # noqa: E402


@pytest.fixture
def client():
    ROOMS.clear()
    SOCKETS.clear()
    with TestClient(app) as c:
        yield c


def until(ws, kind, limit=40):
    """Kerakli turdagi xabar kelguncha o'qiydi; taymer xabarlarini tashlaydi."""
    for _ in range(limit):
        msg = ws.receive_json()
        if msg.get("type") == kind:
            return msg
    raise AssertionError("%r xabari kelmadi" % kind)


def join(ws, dev_user, room=None):
    payload = {"type": "join", "dev_user": dev_user}
    if room:
        payload["room"] = room
    ws.send_json(payload)
    return until(ws, "joined")


def test_two_players_join_and_the_game_starts(client):
    with client.websocket_connect("/ws") as a:
        code = join(a, 1)["code"]
        with client.websocket_connect("/ws") as b:
            join(b, 2, code)
            sa, sb = until(a, "state"), until(b, "state")
            while sa["phase"] != "drawing":
                sa = until(a, "state")
            while sb["phase"] != "drawing":
                sb = until(b, "state")
            assert {sa["you"], sb["you"]} == {1, 2}
            assert sa["drawer"] == sb["drawer"]
            assert sa["total_rounds"] == 6


def test_the_guesser_never_receives_the_word(client):
    with client.websocket_connect("/ws") as a:
        code = join(a, 1)["code"]
        with client.websocket_connect("/ws") as b:
            join(b, 2, code)
            views = {}
            for sock, who in ((a, 1), (b, 2)):
                s = until(sock, "state")
                while s["phase"] != "drawing":
                    s = until(sock, "state")
                views[who] = s
            drawer = views[1]["drawer"]
            guesser = 2 if drawer == 1 else 1
            assert "word" in views[drawer]
            assert "word" not in views[guesser]
            assert "mask" in views[guesser]
            assert views[drawer]["word"] not in str(views[guesser])


def test_a_correct_guess_ends_the_round_and_scores(client):
    with client.websocket_connect("/ws") as a:
        code = join(a, 1)["code"]
        with client.websocket_connect("/ws") as b:
            join(b, 2, code)
            views = {}
            for sock, who in ((a, 1), (b, 2)):
                s = until(sock, "state")
                while s["phase"] != "drawing":
                    s = until(sock, "state")
                views[who] = s
            drawer = views[1]["drawer"]
            word = views[drawer]["word"]
            guesser_sock = b if drawer == 1 else a
            guesser_sock.send_json({"type": "guess", "text": word})
            end = until(guesser_sock, "round_end")
            assert end["word"] == word
            assert max(end["scores"].values()) > 0


def test_a_wrong_guess_keeps_the_round_going(client):
    with client.websocket_connect("/ws") as a:
        code = join(a, 1)["code"]
        with client.websocket_connect("/ws") as b:
            join(b, 2, code)
            views = {}
            for sock, who in ((a, 1), (b, 2)):
                s = until(sock, "state")
                while s["phase"] != "drawing":
                    s = until(sock, "state")
                views[who] = s
            drawer = views[1]["drawer"]
            guesser_sock = b if drawer == 1 else a
            guesser_sock.send_json({"type": "guess", "text": "zzz-yo'q-bunday-so'z"})
            msg = until(guesser_sock, "guess")
            assert msg["correct"] is False


def test_strokes_travel_from_the_drawer_to_the_guesser(client):
    with client.websocket_connect("/ws") as a:
        code = join(a, 1)["code"]
        with client.websocket_connect("/ws") as b:
            join(b, 2, code)
            views = {}
            for sock, who in ((a, 1), (b, 2)):
                s = until(sock, "state")
                while s["phase"] != "drawing":
                    s = until(sock, "state")
                views[who] = s
            drawer = views[1]["drawer"]
            ds, gs = (a, b) if drawer == 1 else (b, a)
            ds.send_json({"type": "stroke",
                          "stroke": {"id": "x1", "c": "#000", "w": 4, "p": [[0.1, 0.2]]}})
            got = until(gs, "stroke")
            assert got["stroke"]["p"] == [[0.1, 0.2]]


def test_the_guesser_cannot_draw(client):
    with client.websocket_connect("/ws") as a:
        code = join(a, 1)["code"]
        with client.websocket_connect("/ws") as b:
            join(b, 2, code)
            views = {}
            for sock, who in ((a, 1), (b, 2)):
                s = until(sock, "state")
                while s["phase"] != "drawing":
                    s = until(sock, "state")
                views[who] = s
            drawer = views[1]["drawer"]
            gs = b if drawer == 1 else a
            gs.send_json({"type": "stroke",
                          "stroke": {"id": "nope", "p": [[0.5, 0.5]]}})
            assert ROOMS[code].strokes == []


def test_a_third_player_is_turned_away(client):
    with client.websocket_connect("/ws") as a:
        code = join(a, 1)["code"]
        with client.websocket_connect("/ws") as b:
            join(b, 2, code)
            with client.websocket_connect("/ws") as c:
                c.send_json({"type": "join", "dev_user": 3, "room": code})
                assert "to'la" in until(c, "error")["error"]


def test_an_unknown_room_code_is_refused(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join", "dev_user": 1, "room": "zzzz"})
        assert "topilmadi" in until(ws, "error")["error"]


def test_a_rejoining_player_gets_the_drawing_back(client):
    with client.websocket_connect("/ws") as a:
        code = join(a, 1)["code"]
        with client.websocket_connect("/ws") as b:
            join(b, 2, code)
            for sock in (a, b):
                s = until(sock, "state")
                while s["phase"] != "drawing":
                    s = until(sock, "state")
            ROOMS[code].strokes = [{"id": "s1", "p": [[0.3, 0.3]]}]
        with client.websocket_connect("/ws") as b2:
            join(b2, 2, code)
            assert until(b2, "replay_strokes")["strokes"][0]["id"] == "s1"


def test_health_reports_the_room_count(client):
    assert client.get("/health").json()["ok"] is True


# -- taklif tugmasi -------------------------------------------------------
#
# Telegram'ga haqiqiy so'rov yubormaymiz: _tg_call almashtiriladi. Shunday
# qilib tugmaning ichidagi havola to'g'ri yasalayotgani ham tekshiriladi.

def test_share_prepares_a_message_with_a_button(client, monkeypatch):
    import json

    import server.main as main

    captured = {}

    def fake_call(method, params):
        captured["method"] = method
        captured["params"] = params
        return {"ok": True, "result": {"id": "prep-123"}}

    monkeypatch.setattr(main, "_tg_call", fake_call)

    with client.websocket_connect("/ws") as a:
        code = join(a, 1)["code"]
        a.send_json({"type": "share"})
        assert until(a, "share_ready")["id"] == "prep-123"

    assert captured["method"] == "savePreparedInlineMessage"
    result = json.loads(captured["params"]["result"])
    button = result["reply_markup"]["inline_keyboard"][0][0]
    assert button["url"].endswith("?startapp=" + code)
    assert button["text"]                      # bo'sh tugma bo'lmasin

    # Xabar rasm bo'lib ketadi, quruq matn emas.
    assert result["type"] == "photo"
    assert result["photo_url"].endswith("/invite-uz.jpg")
    assert result["thumbnail_url"]             # Telegram buni talab qiladi
    assert result["caption"]


def test_invite_card_exists_for_every_language():
    """photo_url mavjud faylga ishora qilsin -- Telegram uni yuklab oladi,
    topa olmasa butun taklif xabari yasalmay qoladi."""
    import os

    import server.main as main

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for lang in main.INVITE_TEXT:
        path = os.path.join(root, "web", "invite-%s.jpg" % lang)
        assert os.path.exists(path), "yo'q: %s (tools/make_invite.py)" % path
        assert os.path.getsize(path) > 1024


def test_share_reports_failure_instead_of_hanging(client, monkeypatch):
    """Telegram javob bermasa klient eski usulga tushishi kerak."""
    import server.main as main

    def boom(method, params):
        raise OSError("tarmoq yo'q")

    monkeypatch.setattr(main, "_tg_call", boom)

    with client.websocket_connect("/ws") as a:
        join(a, 1)
        a.send_json({"type": "share"})
        assert until(a, "share_failed")["type"] == "share_failed"
