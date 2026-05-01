from __future__ import annotations

import json
from abc import ABC, abstractmethod

import httpx

from ..models import Paper, SearchRequest
from ..rate_limit import AsyncRateLimiter, RateLimit


class PaperProvider(ABC):
    name: str
    base_url: str

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        rate_limit: RateLimit | None = None,
        api_key: str | None = None,
    ) -> None:
        self._client = client or httpx.AsyncClient(timeout=30.0)
        self._owns_client = client is None
        self._rate_limiter = AsyncRateLimiter(rate_limit or self.default_rate_limit())
        self._api_key = api_key

    @classmethod
    @abstractmethod
    def default_rate_limit(cls) -> RateLimit:
        raise NotImplementedError

    async def search(self, request: SearchRequest) -> list[Paper]:
        await self._rate_limiter.acquire()
        headers = {}
        if self._api_key:
            headers["x-api-key"] = self._api_key
        response = await self._client.get(
            self.base_url, params=self.build_params(request), headers=headers
        )
        response.raise_for_status()
        return self._parse_response_text(response.text)

    def _parse_response_text(self, text: str) -> list[Paper]:
        """Parse response text into Paper objects. Override for non-JSON APIs."""
        return self.parse_response(json.loads(text))

    @abstractmethod
    def build_params(self, request: SearchRequest) -> dict[str, str | int]:
        raise NotImplementedError

    def parse_response(self, payload: dict) -> list[Paper]:
        """Parse JSON response payload into Paper objects.

        Override this for JSON APIs, or override _parse_response_text for non-JSON APIs.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must implement parse_response (for JSON APIs) "
            f"or _parse_response_text (for non-JSON APIs)"
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
