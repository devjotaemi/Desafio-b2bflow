"""Testes de normalização de telefone para E.164 (sem ``+``)."""

import pytest

from dispatch.phone import InvalidPhoneNumberError, normalize_phone


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+55 17 99999-9999", "5517999999999"),  # com DDI e formatação
        ("(17) 99999-9999", "5517999999999"),  # máscara, sem DDI (região BR)
        ("17999999999", "5517999999999"),  # só dígitos, sem DDI
        ("5517999999999", "5517999999999"),  # já normalizado (idempotente)
        ("+5511987654321", "5511987654321"),  # outro DDD
    ],
)
def test_normalize_valid_numbers(raw: str, expected: str) -> None:
    assert normalize_phone(raw) == expected


def test_keeps_brazilian_ninth_digit() -> None:
    # Celular com nono dígito => DDI(2) + DDD(2) + 9 dígitos = 13 caracteres.
    normalized = normalize_phone("(17) 99999-9999")
    assert normalized == "5517999999999"
    assert len(normalized) == 13


def test_normalize_landline() -> None:
    assert normalize_phone("(11) 3333-4444") == "551133334444"


@pytest.mark.parametrize("bad", ["", "   ", "123", "abc", "999"])
def test_invalid_numbers_raise(bad: str) -> None:
    with pytest.raises(InvalidPhoneNumberError):
        normalize_phone(bad)
