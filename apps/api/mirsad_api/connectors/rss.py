from __future__ import annotations

import asyncio
import email.utils
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from html.parser import HTMLParser
from time import perf_counter
from typing import Any
from urllib.parse import urlsplit

import httpx

from ..domains.query import normalize_text, tokenize
from ..provenance import AcquisitionMode
from .base import (
    BaseConnector,
    ConnectorCapabilities,
    ConnectorDiagnostics,
    ConnectorError,
    ConnectorItem,
    ConnectorMetadata,
    ConnectorSearchOptions,
    parse_datetime,
)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _plain_text(value: object) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(str(value or ""))
        parser.close()
    except (ValueError, TypeError):
        return ""
    return " ".join("".join(parser.parts).split())


class RssConnector(BaseConnector):
    metadata = ConnectorMetadata(
        key="rss",
        name="RSS Feeds",
        kind="feed",
        base_url="https://feeds.bbci.co.uk",
        confidence=72,
        category="news",
        coverage_label="Server-configured public feeds",
        capabilities=ConnectorCapabilities(
            keyword_search=True,
            phrase_search=True,
            recent_search=True,
            historical_search="conditional",
            language_filter="conditional",
            date_filter=True,
            full_text_search="conditional",
            identifier_search="conditional",
            content_types=("news",),
            acquisition_modes=("PUBLIC_API",),
        ),
    )

    def __init__(self, feed_urls: list[str] | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.feed_urls = tuple(feed_urls or ["https://feeds.bbci.co.uk/news/world/rss.xml"])

    def validate_configuration(self) -> tuple[bool, str | None]:
        valid = all(
            urlsplit(url).scheme == "https" and urlsplit(url).hostname for url in self.feed_urls
        )
        return (
            bool(self.feed_urls) and valid,
            None if valid else "No valid server-configured feeds",
        )

    async def _fetch(self, url: str) -> str:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            started = perf_counter()
            recorded = False
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout,
                    follow_redirects=True,
                    transport=self.transport,
                ) as client:
                    response = await client.get(
                        url, headers={"Accept": "application/rss+xml, application/atom+xml"}
                    )
                self.last_diagnostics.http_status = response.status_code
                latency = (perf_counter() - started) * 1000
                self.last_diagnostics.attempt_count += 1
                self.last_diagnostics.attempt_latencies_ms.append(round(latency, 2))
                self.last_diagnostics.request_latency_ms = max(
                    self.last_diagnostics.request_latency_ms, latency
                )
                recorded = True
                if response.is_error:
                    error = self._http_error(response)
                    if error.retryable and attempt < self.retries:
                        await asyncio.sleep(self._retry_delay(attempt, response))
                        continue
                    raise error
                if len(response.content) > 5_000_000:
                    raise ConnectorError(
                        self.metadata.key, "response_too_large", "RSS response exceeds limit"
                    )
                return response.text
            except (httpx.TimeoutException, httpx.NetworkError, ConnectorError) as exc:
                if not recorded:
                    latency = (perf_counter() - started) * 1000
                    self.last_diagnostics.attempt_count += 1
                    self.last_diagnostics.attempt_latencies_ms.append(round(latency, 2))
                    self.last_diagnostics.request_latency_ms = max(
                        self.last_diagnostics.request_latency_ms, latency
                    )
                last_error = exc
                if isinstance(exc, ConnectorError) and not exc.retryable:
                    raise
                if attempt < self.retries:
                    await asyncio.sleep(self._retry_delay(attempt))
        if isinstance(last_error, ConnectorError):
            raise last_error
        code = "timeout" if isinstance(last_error, httpx.TimeoutException) else "dns_network"
        message = (
            "RSS feed request timed out" if code == "timeout" else "RSS feed network request failed"
        )
        raise ConnectorError(self.metadata.key, code, message, retryable=True) from last_error

    async def search(
        self, query: str, *, limit: int, since: datetime | None = None
    ) -> list[ConnectorItem]:
        return await self.search_with_options(query, limit=limit, since=since)

    async def search_with_options(
        self,
        query: str,
        *,
        limit: int,
        since: datetime | None = None,
        options: ConnectorSearchOptions | None = None,
    ) -> list[ConnectorItem]:
        self.last_diagnostics = ConnectorDiagnostics()
        operation_started = perf_counter()
        documents = await asyncio.gather(
            *(self._fetch(url) for url in self.feed_urls), return_exceptions=True
        )
        self.last_diagnostics.total_latency_ms = (perf_counter() - operation_started) * 1000
        if documents and all(isinstance(document, BaseException) for document in documents):
            first_error = documents[0]
            if isinstance(first_error, ConnectorError):
                raise first_error
            code = "timeout" if isinstance(first_error, httpx.TimeoutException) else "dns_network"
            raise ConnectorError(
                self.metadata.key,
                code,
                "All configured RSS feed requests timed out"
                if code == "timeout"
                else "All configured RSS feed network requests failed",
                retryable=True,
            ) from first_error
        output: list[ConnectorItem] = []
        raw_count = 0
        schema_valid_count = 0
        query_match_count = 0
        time_eligible_count = 0
        malformed = 0
        invalid_documents = 0
        exact_phrase = bool(options and options.exact_phrase)
        for feed_url, document in zip(self.feed_urls, documents, strict=True):
            if isinstance(document, BaseException):
                continue
            try:
                root = ET.fromstring(document)
            except ET.ParseError:
                malformed += 1
                invalid_documents += 1
                continue
            nodes = root.findall(".//item") + root.findall("{http://www.w3.org/2005/Atom}entry")
            raw_count += len(nodes)
            for node in nodes:
                payload = self._node_payload(node, feed_url)
                try:
                    item = self.normalize(payload)
                except (TypeError, ValueError, OverflowError):
                    malformed += 1
                    continue
                if not self._valid_item(item):
                    malformed += 1
                    continue
                schema_valid_count += 1
                if not self._matches_query(item, query, exact_phrase=exact_phrase):
                    continue
                query_match_count += 1
                if since and item.published_at and item.published_at < since:
                    continue
                time_eligible_count += 1
                output.append(item)
                if len(output) >= limit:
                    self._record_stage_counts(
                        raw_count,
                        schema_valid_count,
                        query_match_count,
                        time_eligible_count,
                        malformed,
                        len(output),
                    )
                    self._record_document_failures(documents)
                    return output
        self._record_stage_counts(
            raw_count,
            schema_valid_count,
            query_match_count,
            time_eligible_count,
            malformed,
            len(output),
        )
        successful_documents = sum(
            not isinstance(document, BaseException) for document in documents
        )
        if successful_documents and invalid_documents == successful_documents:
            raise ConnectorError(
                self.metadata.key, "invalid_payload", "RSS feeds returned invalid XML"
            )
        self._record_document_failures(documents)
        return output

    def _record_document_failures(self, documents: list[object]) -> None:
        failures = [document for document in documents if isinstance(document, BaseException)]
        if failures:
            first = failures[0]
            self.last_diagnostics.warning_code = (
                first.code if isinstance(first, ConnectorError) else "dns_network"
            )
            self.last_diagnostics.warning_message = (
                "One or more server-configured RSS feeds could not be collected"
            )
            self.last_diagnostics.warning_status_code = (
                first.status_code if isinstance(first, ConnectorError) else None
            )

    @staticmethod
    def _matches_query(item: ConnectorItem, query: str, *, exact_phrase: bool) -> bool:
        normalized_query = normalize_text(query)
        combined = normalize_text(f"{item.title or ''} {item.text}")
        if not normalized_query:
            return False
        if exact_phrase:
            return normalized_query in combined
        query_tokens = set(tokenize(normalized_query))
        return bool(query_tokens) and query_tokens.issubset(set(tokenize(combined)))

    def _record_stage_counts(
        self,
        fetched: int,
        schema_valid: int,
        query_matching: int,
        time_eligible: int,
        malformed: int,
        normalized: int,
    ) -> None:
        diagnostics = self.last_diagnostics
        diagnostics.raw_result_count = fetched
        diagnostics.fetched_result_count = fetched
        diagnostics.schema_valid_count = schema_valid
        diagnostics.query_match_count = query_matching
        diagnostics.time_eligible_count = time_eligible
        diagnostics.normalized_result_count = normalized
        diagnostics.malformed_count = malformed
        diagnostics.query_excluded_count = max(0, schema_valid - query_matching)
        diagnostics.time_excluded_count = max(0, query_matching - time_eligible)

    def _node_payload(self, node: ET.Element, feed_url: str) -> dict[str, Any]:
        atom = "{http://www.w3.org/2005/Atom}"
        link_node = node.find("link")
        if link_node is None:
            link_node = node.find(f"{atom}link")
        link = ""
        if link_node is not None:
            link = link_node.text or link_node.attrib.get("href", "")

        def value(*names: str) -> str | None:
            for name in names:
                found = node.find(name)
                if found is not None and found.text:
                    return found.text
            return None

        return {
            "id": value("guid", f"{atom}id") or link,
            "url": link,
            "title": value("title", f"{atom}title"),
            "text": value("description", f"{atom}summary", f"{atom}content"),
            "author": value("author", f"{atom}author/{atom}name"),
            "date": value("pubDate", f"{atom}published", f"{atom}updated"),
            "feed_url": feed_url,
        }

    def normalize(self, payload: dict[str, Any]) -> ConnectorItem:
        date_value = payload.get("date")
        published = parse_datetime(date_value)
        if not published and isinstance(date_value, str):
            parsed = email.utils.parsedate_to_datetime(date_value)
            published = parsed.astimezone(UTC) if parsed else None
        raw_title = str(payload.get("title") or "")
        raw_text = str(payload.get("text") or raw_title)
        return ConnectorItem(
            source=self.metadata.key,
            external_id=str(payload.get("id") or payload.get("url")),
            canonical_url=str(payload.get("url")),
            author=payload.get("author"),
            title=_plain_text(raw_title) or None,
            text=_plain_text(raw_text),
            published_at=published,
            raw_metadata={
                "source_type": "feed_item",
                "feed_url": payload.get("feed_url"),
                "original_title": raw_title,
                "original_description": raw_text,
            },
            acquisition_mode=AcquisitionMode.PUBLIC_API,
        )
