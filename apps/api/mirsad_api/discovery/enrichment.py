from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from .classifiers import classify_platform_url


@dataclass(frozen=True, slots=True)
class EmbedEnrichment:
    state: str
    metadata: dict[str, Any]


class OfficialEmbedEnricher:
    """Retrieve safe text metadata for known URLs; returned embed HTML is discarded."""

    ENDPOINTS = {
        "x": "https://publish.twitter.com/oembed",
        "reddit": "https://www.reddit.com/oembed",
    }

    def __init__(
        self,
        *,
        enabled: bool = False,
        timeout: float = 3.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.enabled = enabled
        self.timeout = max(0.5, min(timeout, 6.0))
        self.transport = transport

    async def enrich(self, platform: str, public_url: str) -> EmbedEnrichment:
        if not self.enabled:
            return EmbedEnrichment("disabled", {})
        endpoint = self.ENDPOINTS.get(platform)
        if endpoint is None:
            return EmbedEnrichment("not_available", {})
        classified = classify_platform_url(platform, public_url)
        if classified is None or not classified.is_content:
            return EmbedEnrichment("rejected_url", {})
        params: dict[str, str] = {"url": classified.canonical_url}
        if platform == "x":
            params.update({"omit_script": "true", "dnt": "true"})
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=False,
                transport=self.transport,
                headers={"Accept": "application/json", "User-Agent": "MIRSAD/1.0"},
            ) as client:
                response = await client.get(endpoint, params=params)
        except httpx.TimeoutException:
            return EmbedEnrichment("timeout", {})
        except httpx.NetworkError:
            return EmbedEnrichment("network_error", {})
        if response.status_code in {401, 403}:
            return EmbedEnrichment("access_restricted", {"http_status": response.status_code})
        if response.status_code == 429:
            return EmbedEnrichment("rate_limited", {"http_status": 429})
        if response.status_code != 200:
            return EmbedEnrichment("unavailable", {"http_status": response.status_code})
        try:
            payload = response.json()
        except ValueError:
            return EmbedEnrichment("invalid_payload", {})
        if not isinstance(payload, dict):
            return EmbedEnrichment("invalid_payload", {})
        # Never return or persist provider-controlled embed HTML.
        safe_keys = ("author_name", "author_url", "provider_name", "provider_url", "title", "type")
        metadata = {
            key: payload[key]
            for key in safe_keys
            if isinstance(payload.get(key), (str, int, float, bool))
        }
        return EmbedEnrichment("enriched", metadata)
