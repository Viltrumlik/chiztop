"""initData tekshiruvi: imzoga ishonmaydigan yagona joy shu, shuning uchun
har bir buzilish turi alohida sinaladi."""

import json
import time

import pytest

from server.auth import AuthError, display_name, sign_for_test, verify

TOKEN = "123456:TEST-TOKEN-abcdef"
USER = {"id": 7721, "first_name": "Alisher", "username": "viltrumlik"}


def make(token=TOKEN, user=USER, auth_date=None, **extra):
    fields = {
        "auth_date": str(int(auth_date if auth_date is not None else time.time())),
        "query_id": "AAEx",
        "user": json.dumps(user, separators=(",", ":")),
    }
    fields.update(extra)
    return sign_for_test(fields, token)


def test_valid_init_data_returns_the_user():
    assert verify(make(), TOKEN)["id"] == 7721


def test_a_tampered_field_is_refused():
    data = make()
    bad = data.replace("Alisher", "Someone")
    assert bad != data
    with pytest.raises(AuthError):
        verify(bad, TOKEN)


def test_another_bots_token_does_not_validate():
    with pytest.raises(AuthError):
        verify(make(), "999999:OTHER-TOKEN")


def test_missing_hash_is_refused():
    with pytest.raises(AuthError):
        verify("auth_date=1&user=%7B%22id%22%3A1%7D", TOKEN)


def test_empty_init_data_is_refused():
    with pytest.raises(AuthError):
        verify("", TOKEN)


def test_unset_bot_token_is_refused():
    with pytest.raises(AuthError):
        verify(make(), "")


def test_old_init_data_is_refused():
    old = time.time() - (25 * 60 * 60)
    with pytest.raises(AuthError):
        verify(make(auth_date=old), TOKEN)


def test_init_data_from_the_future_is_refused():
    with pytest.raises(AuthError):
        verify(make(auth_date=time.time() + 600), TOKEN)


def test_init_data_without_a_user_is_refused():
    fields = {"auth_date": str(int(time.time())), "query_id": "AAEx"}
    with pytest.raises(AuthError):
        verify(sign_for_test(fields, TOKEN), TOKEN)


def test_extra_signed_fields_do_not_break_verification():
    data = make(start_param="7f2c", chat_type="private")
    assert verify(data, TOKEN)["id"] == 7721


def test_display_name_prefers_the_full_name():
    assert display_name({"first_name": "Alisher", "last_name": "M"}) == "Alisher M"
    assert display_name({"username": "viltrumlik"}) == "viltrumlik"
    assert display_name({}) == "O'yinchi"
