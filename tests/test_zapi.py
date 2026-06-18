"""Testes do cliente Z-API com a API mockada via respx (nunca chama a API real)."""

import json

import httpx
import pytest
import respx

from dispatch.zapi import PermanentZApiError, ZApiClient

BASE_URL = "https://api.z-api.io"
SEND_URL = f"{BASE_URL}/instances/inst/token/tok/send-text"


def make_client(**kwargs: object) -> ZApiClient:
    # backoff_base=0 -> retries imediatos, sem deixar o teste lento.
    return ZApiClient("inst", "tok", "secret-token", BASE_URL, backoff_base=0, **kwargs)


@respx.mock
def test_send_text_returns_message_id() -> None:
    route = respx.post(SEND_URL).mock(return_value=httpx.Response(200, json={"zaapId": "MSG123"}))
    assert make_client().send_text("5511999999999", "oi") == "MSG123"
    assert route.called


@respx.mock
def test_send_text_includes_client_token_header_and_clean_phone() -> None:
    route = respx.post(SEND_URL).mock(return_value=httpx.Response(200, json={"messageId": "X"}))
    make_client().send_text("+5511999999999", "Olá")

    request = route.calls.last.request
    assert request.headers["Client-Token"] == "secret-token"
    assert json.loads(request.content) == {"phone": "5511999999999", "message": "Olá"}


@respx.mock
def test_send_text_retries_on_5xx_then_succeeds() -> None:
    route = respx.post(SEND_URL).mock(
        side_effect=[httpx.Response(500), httpx.Response(200, json={"id": "OK"})]
    )
    assert make_client(max_attempts=3).send_text("5511999999999", "oi") == "OK"
    assert route.call_count == 2


@respx.mock
def test_send_text_does_not_retry_on_4xx() -> None:
    route = respx.post(SEND_URL).mock(return_value=httpx.Response(400, text="bad request"))
    with pytest.raises(PermanentZApiError):
        make_client(max_attempts=3).send_text("5511999999999", "oi")
    assert route.call_count == 1
