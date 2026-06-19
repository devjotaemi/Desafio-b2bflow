# Cliente HTTP da Z-API com retry/backoff exponencial.
# Envie texto pelo endpoint "send-text" incluindo o header obrigatório
# "Client-Token". Erros temporários (timeout, conexão perdida, 5xx) são
# Tentativas com backoff exponencial utilizando "tenacity"; erros 4xx são gerenciados
# como se fossem permanentes (não vale a pena tentar novamente).


from __future__ import annotations

import httpx
import structlog
from tenacity import (
    RetryCallState,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from dispatch.models import ZApiResponse

log = structlog.get_logger()


class ZApiError(Exception):
    # Erro genérico ao falar com a Z-API.
    pass


class TransientZApiError(ZApiError):
    # Falha transitória (5xx) elegível a retry.
    pass


class PermanentZApiError(ZApiError):
    # Falha permanente (4xx) não adianta re-tentar.
    pass


_RETRYABLE = (httpx.TimeoutException, httpx.TransportError, TransientZApiError)


class ZApiClient:
    # Cliente de alto nível para a Z-API.

    def __init__(
        self,
        instance_id: str,
        instance_token: str,
        client_token: str,
        base_url: str = "https://api.z-api.io",
        *,
        timeout: float = 15.0,
        max_attempts: int = 3,
        backoff_base: float = 0.5,
        client: httpx.Client | None = None,
    ) -> None:
        self._instance_id = instance_id
        self._instance_token = instance_token
        self._client_token = client_token
        self._base_url = base_url.rstrip("/")
        self._max_attempts = max_attempts
        self._backoff_base = backoff_base
        self._client = client or httpx.Client(timeout=timeout)

    @property
    def send_text_url(self) -> str:
        return (
            f"{self._base_url}/instances/{self._instance_id}/token/{self._instance_token}/send-text"
        )

    @property
    def status_url(self) -> str:
        return f"{self._base_url}/instances/{self._instance_id}/token/{self._instance_token}/status"

    @property
    def _headers(self) -> dict[str, str]:
        return {"Client-Token": self._client_token, "Content-Type": "application/json"}

    def send_text(self, phone: str, message: str) -> str:
        #        Envia uma mensagem de texto e retorna o id da mensagem na Z-API.

        #        Re-tenta automaticamente em falhas transitórias (até "max_attempts").

        normalized = phone.removeprefix("+")
        retrying = Retrying(
            stop=stop_after_attempt(self._max_attempts),
            wait=wait_exponential(multiplier=self._backoff_base, max=10),
            retry=retry_if_exception_type(_RETRYABLE),
            before_sleep=self._log_retry,
            reraise=True,
        )
        return retrying(self._do_send_text, normalized, message)

    def check_connection(self) -> bool:
        """Consulta o status da instância (não envia mensagem). Usado pelo "validate"."""
        response = self._client.get(self.status_url, headers=self._headers)
        return response.status_code < 400

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ZApiClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _do_send_text(self, phone: str, message: str) -> str:
        log.info("zapi_send_text", phone=phone)
        response = self._client.post(
            self.send_text_url,
            headers=self._headers,
            json={"phone": phone, "message": message},
        )
        if response.status_code >= 500:
            raise TransientZApiError(f"Z-API {response.status_code}: {response.text}")
        if response.status_code >= 400:
            raise PermanentZApiError(f"Z-API {response.status_code}: {response.text}")
        return ZApiResponse.from_api(response.json()).message_id

    def _log_retry(self, retry_state: RetryCallState) -> None:
        sleep_for = getattr(retry_state.next_action, "sleep", None)
        log.warning("zapi_retry", attempt=retry_state.attempt_number, sleep=sleep_for)
