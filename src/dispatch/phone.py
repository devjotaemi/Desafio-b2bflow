"""Formatando os números de telefone para a notação exigida pela Z-API.

Para a Z-API, o número precisa ser dado na notação DDI + DDD + número (por
exemplo, ``5517999999999``), sem ``+``, espaços e hífens. Nós usamos
``phonenumbers`` para validação e formatação em E.164 (que cuida do nono
dígito do celular brasileiro) e então removemos o ``+``.
"""

from __future__ import annotations

import phonenumbers


class InvalidPhoneNumberError(ValueError):
    """O telefone não pôde ser interpretado ou não é um número válido."""


def normalize_phone(raw: str, region: str = "BR") -> str:
    """Normaliza um telefone para E.164 sem o prefixo ``+``.

    Args:
        raw: telefone como veio do banco (pode ter espaços, ``+`` etc.).
        region: região padrão usada quando o número não traz o DDD (``BR``).

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
