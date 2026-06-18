"""Normalização de telefones para o formato exigido pela Z-API.

A Z-API espera o número como DDI+DDD+número (ex.: ``5517999999999``), sem
``+``, espaços ou traços. Usamos ``phonenumbers`` para validar e formatar em
E.164 (que cuida do nono dígito brasileiro) e então removemos o ``+``.
"""

from __future__ import annotations

import phonenumbers


class InvalidPhoneNumberError(ValueError):
    """O telefone não pôde ser interpretado ou não é um número válido."""


def normalize_phone(raw: str, region: str = "BR") -> str:
    """Normaliza um telefone "cru" para E.164 sem o prefixo ``+``.

    Args:
        raw: telefone como veio do banco (pode ter máscara, espaços, ``+`` etc.).
        region: região padrão usada quando o número não traz o DDI (``BR``).

    Returns:
        O número em E.164 sem ``+`` (ex.: ``5517999999999``).

    Raises:
        InvalidPhoneNumberError: se o número for vazio ou inválido.
    """
    if not raw or not raw.strip():
        raise InvalidPhoneNumberError("Telefone vazio.")

    try:
        parsed = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException as exc:
        raise InvalidPhoneNumberError(
            f"Não foi possível interpretar o telefone {raw!r}: {exc}"
        ) from exc

    if not phonenumbers.is_valid_number(parsed):
        raise InvalidPhoneNumberError(f"Telefone inválido para a região {region!r}: {raw!r}")

    e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    return e164.removeprefix("+")
