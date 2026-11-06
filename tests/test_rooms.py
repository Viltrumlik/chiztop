"""O'yin mantiqi testlari. Vaqt qo'lda beriladi, shuning uchun hech qayerda
kutib o'tirilmaydi."""

import random

import pytest

from server import rooms
from server.rooms import DRAWING, GAME_END, LOBBY, ROUND_END, Room

A, B, C = 101, 202, 303


def room(**kw):
    kw.setdefault("rng", random.Random(7))
    r = Room("test", **kw)
    r.add_player(A, "Alisher")
    r.add_player(B, "Bobur")
    return r


# -- javobni taqqoslash --------------------------------------------------

@pytest.mark.parametrize("guess,word", [
    ("olma", "olma"),
    ("Olma", "olma"),
    ("  olma  ", "olma"),
    ("ko'prik", "koʻprik"),      # o' va oʻ bir xil
    ("koprik", "koʻprik"),       # apostrofsiz ham
    ("KO`PRIK", "koʻprik"),
    ("muz qaymoq", "muzqaymoq"),      # bo'shliq ahamiyatsiz
])
def test_these_count_as_correct(guess, word):
    assert rooms.is_correct(guess, word)


@pytest.mark.parametrize("guess,word", [
    ("olmalar", "olma"),
    ("", "olma"),
    ("   ", "olma"),
    ("quyosh", "olma"),
])
def test_these_do_not(guess, word):
    assert not rooms.is_correct(guess, word)


def test_one_letter_off_is_close_but_not_correct():
    assert rooms.is_close("kuyosh", "quyosh")
    assert not rooms.is_correct("kuyosh", "quyosh")


def test_short_words_have_no_close_match():
    # "uy" uchun bir harf xato -- bu butunlay boshqa so'z
    assert not rooms.is_close("oy", "uy")


def test_mask_hides_everything_until_letters_are_revealed():
    assert rooms.mask("olma", set()) == "_ _ _ _"
    assert rooms.mask("olma", {0, 3}) == "o _ _ a"


def test_faster_guesses_score_higher():
    assert rooms.guess_points(60, 60) == rooms.MAX_GUESS_POINTS
    assert rooms.guess_points(0, 60) == rooms.MIN_GUESS_POINTS
    assert rooms.guess_points(30, 60) == 60


# -- xona ----------------------------------------------------------------

def test_a_third_player_cannot_join():
    r = room()
    assert r.add_player(C, "Dilnoza") is None
    assert len(r.players) == 2


def test_rejoining_restores_the_same_player():
    r = room()
    r.disconnect(A, now=0)
    assert not r.players[A].connected
    again = r.add_player(A, "Alisher")
    assert again.connected and len(r.players) == 2


def test_the_game_starts_only_with_two_connected_players():
    r = Room("x", rng=random.Random(1))
    r.add_player(A, "Alisher")
    assert not r.can_start()
    r.add_player(B, "Bobur")
    assert r.can_start()


def test_the_drawer_alternates_each_round():
    r = room()
    drawers = []
    now = 0.0
    for _ in range(4):
        r.start_round(now)
        drawers.append(r.drawer_id)
        r.end_round(now)
    assert drawers == [A, B, A, B]


def test_a_correct_guess_scores_both_players_and_ends_the_round():
    r = room()
    r.start_round(0.0)
    out = r.submit_guess(r.guesser_id, r.word, now=0.0)
    assert out["correct"] and out["round_end"]
    assert r.scores[r.guesser_id] == rooms.MAX_GUESS_POINTS
    assert r.scores[r.drawer_id] == rooms.DRAWER_POINTS
    assert r.phase == ROUND_END


def test_a_wrong_guess_changes_nothing():
    r = room()
    r.start_round(0.0)
    out = r.submit_guess(r.guesser_id, "butunlay-boshqa-narsa", now=0.0)
    assert out["ok"] and not out["correct"]
    assert r.phase == DRAWING
    assert set(r.scores.values()) == {0}


def test_the_drawer_cannot_guess_its_own_word():
    r = room()
    r.start_round(0.0)
    out = r.submit_guess(r.drawer_id, r.word, now=0.0)
    assert not out["ok"]
    assert set(r.scores.values()) == {0}


def test_time_running_out_ends_the_round_with_no_points():
    r = room()
    r.start_round(0.0)
    changed = r.tick(now=61.0)
    assert changed["round_end"] and changed["guessed_by"] is None
    assert set(r.scores.values()) == {0}


def test_letters_are_revealed_as_time_passes():
    r = room(duration=60)
    r.start_round(0.0)
    assert len(r.revealed) == 0
    r.tick(now=31.0)          # yarmidan oshdi
    assert len(r.revealed) == 1
    r.tick(now=46.0)          # chorakdan kamroq qoldi
    assert len(r.revealed) == 2


def test_a_short_word_never_becomes_fully_revealed():
    r = room(duration=60)
    r.start_round(0.0)
    r.word, r.revealed = "uy", set()
    r.tick(now=59.0)
    assert len(r.revealed) == 0   # 2 harfli so'zdan harf ochilmaydi


def test_the_game_ends_after_the_last_round_and_names_a_winner():
    r = room(total_rounds=2)
    r.start_round(0.0)
    r.submit_guess(r.guesser_id, r.word, now=0.0)
    r.start_round(100.0)
    out = r.submit_guess(r.guesser_id, "xato", now=100.0)
    assert not out.get("game_end")
    out = r.tick(now=161.0)
    assert out["game_end"] and r.phase == GAME_END
    # 1-raund: A chizdi (+50), B darrov topdi (+100). 2-raund: hech kim topmadi.
    assert r.scores == {A: rooms.DRAWER_POINTS, B: rooms.MAX_GUESS_POINTS}
    assert r.winner_id == B


def test_equal_scores_are_a_draw():
    r = room(total_rounds=2)
    r.scores = {A: 70, B: 70}
    out = r.end_game()
    assert out["draw"] and out["winner"] is None


def test_replay_clears_the_scores_but_keeps_the_players():
    r = room()
    r.start_round(0.0)
    r.submit_guess(r.guesser_id, r.word, now=0.0)
    r.reset()
    assert r.phase == LOBBY and r.round_no == 0
    assert set(r.scores.values()) == {0}
    assert len(r.players) == 2


def test_words_do_not_repeat_within_a_game():
    r = room(total_rounds=6)
    seen = []
    for i in range(6):
        r.start_round(i * 100.0)
        seen.append(r.word)
        r.end_round(i * 100.0)
    assert len(set(seen)) == 6


# -- chizish --------------------------------------------------------------

def test_only_the_drawer_can_draw():
    r = room()
    r.start_round(0.0)
    assert r.add_stroke(r.drawer_id, {"p": [[0.1, 0.1]]})
    assert not r.add_stroke(r.guesser_id, {"p": [[0.2, 0.2]]})
    assert len(r.strokes) == 1


def test_strokes_are_dropped_at_the_start_of_each_round():
    r = room()
    r.start_round(0.0)
    r.add_stroke(r.drawer_id, {"p": [[0.1, 0.1]]})
    r.end_round(0.0)
    r.start_round(100.0)
    assert r.strokes == []


# -- eng muhim test: so'z sirligi -----------------------------------------

def test_the_word_never_reaches_the_guesser():
    r = room()
    r.start_round(0.0)
    guesser_view = r.state_for(r.guesser_id, now=0.0)
    assert "word" not in guesser_view
    assert "mask" in guesser_view
    assert r.word not in repr(guesser_view)
    drawer_view = r.state_for(r.drawer_id, now=0.0)
    assert drawer_view["word"] == r.word


def test_the_word_is_shown_to_both_once_the_round_is_over():
    r = room()
    r.start_round(0.0)
    word = r.word
    r.end_round(0.0)
    assert r.state_for(r.guesser_id, now=0.0)["word"] == word


# -- uzilish --------------------------------------------------------------

def test_a_briefly_disconnected_player_keeps_their_seat():
    r = room()
    r.disconnect(A, now=0.0)
    assert r.waiting_for_rejoin(now=10.0)
    assert not r.is_abandoned(now=10.0)


def test_a_room_everyone_left_is_collectable():
    r = room()
    r.disconnect(A, now=0.0)
    r.disconnect(B, now=0.0)
    assert not r.is_abandoned(now=10.0)
    assert r.is_abandoned(now=rooms.GRACE_SECONDS + 1.0)


# -- orqaga qaytarish -----------------------------------------------------

def test_undo_removes_the_whole_stroke_not_one_segment():
    r = room()
    r.start_round(0.0)
    d = r.drawer_id
    # bitta chiziq uchta bo'lak bo'lib keldi
    for seg in range(3):
        r.add_stroke(d, {"id": "a", "p": [[0.1 * seg, 0.1]]})
    r.add_stroke(d, {"id": "b", "p": [[0.9, 0.9]]})
    assert len(r.strokes) == 4
    assert r.undo_stroke(d)
    assert [s["id"] for s in r.strokes] == ["a", "a", "a"]
    assert r.undo_stroke(d)
    assert r.strokes == []


def test_only_the_drawer_can_undo():
    r = room()
    r.start_round(0.0)
    r.add_stroke(r.drawer_id, {"id": "a", "p": [[0.1, 0.1]]})
    assert not r.undo_stroke(r.guesser_id)
    assert len(r.strokes) == 1


def test_undo_on_an_empty_canvas_is_harmless():
    r = room()
    r.start_round(0.0)
    assert not r.undo_stroke(r.drawer_id)


def test_a_stroke_without_points_is_rejected():
    r = room()
    r.start_round(0.0)
    assert not r.add_stroke(r.drawer_id, {"id": "a", "p": []})
    assert not r.add_stroke(r.drawer_id, "nonsense")
    assert r.strokes == []
