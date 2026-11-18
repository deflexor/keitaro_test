import os
import time
from typing import Any

import httpx

BASE_URL = os.getenv("KEITARO_BASE_URL", "https://tlgk.host/admin_api/v1")
API_KEY = os.getenv("KEITARO_API_KEY", "")
if not API_KEY:
    raise RuntimeError("KEITARO_API_KEY is not set; put it in backend/.env (see .env.example)")

_client = httpx.Client(
    base_url=BASE_URL,
    headers={"Api-Key": API_KEY},
    timeout=30,
)


class KeitaroError(Exception):
    def __init__(self, status_code: int, detail: Any):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def call(method: str, path: str, **kwargs: Any) -> Any:
    response = None
    for attempt in range(3):
        try:
            response = _client.request(method, path, **kwargs)
            break
        except httpx.TransportError as exc:
            if attempt == 2:
                raise KeitaroError(502, f"Keitaro request failed: {exc}") from exc
            time.sleep(0.5 * (attempt + 1))
    assert response is not None
    if response.status_code >= 400:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        raise KeitaroError(response.status_code, detail)
    return response.json() if response.content else None
