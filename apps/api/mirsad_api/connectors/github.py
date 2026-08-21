from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from .base import (
    BaseConnector,
    ConnectorCapabilities,
    ConnectorDiagnostics,
    ConnectorError,
    ConnectorItem,
    ConnectorMetadata,
    ConnectorValidation,
    parse_datetime,
)
from .social_utils import available_metrics


class GitHubConnector(BaseConnector):
    metadata = ConnectorMetadata(
        key="github",
        name="GitHub",
        kind="code",
        base_url="https://api.github.com",
        confidence=75,
        category="developer_community",
        coverage_label="Public repositories, issues, and pull requests",
        capabilities=ConnectorCapabilities(
            keyword_search=True,
            phrase_search=True,
            author_search=True,
            recent_search=True,
            historical_search=True,
            language_filter=True,
            date_filter=True,
            comments=True,
            engagement_metrics=True,
            pagination=True,
            full_text_search=True,
            identifier_search=True,
            content_types=("repositories", "issues", "pull_requests"),
            acquisition_modes=("DIRECT_API",),
        ),
    )

    VALID_SCOPES = ("repositories", "issues", "pull_requests")

    def __init__(
        self,
        token: str | None = None,
        scopes: list[str] | tuple[str, ...] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.token = token
        self.set_scopes(scopes or ["repositories"])

    def set_scopes(self, scopes: list[str] | tuple[str, ...]) -> None:
        selected = tuple(scope for scope in scopes if scope in self.VALID_SCOPES)
        self.scopes = selected or ("repositories",)

    def validate_configuration(self) -> tuple[bool, str | None]:
        return True, "Anonymous requests have a lower rate limit" if not self.token else None

    async def validate_access(self) -> ConnectorValidation:
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        await self.request_json("GET", f"{self.metadata.base_url}/rate_limit", headers=headers)
        return ConnectorValidation(
            "pass",
            "credentials_valid" if self.token else "anonymous_access_available",
            "GitHub token accepted" if self.token else "Anonymous GitHub API access is available",
            True,
        )

    async def health_check(self) -> dict[str, Any]:
        try:
            validation = await self.validate_access()
            return {
                "status": "healthy",
                "detail": validation.message,
                "checked_at": datetime.now(UTC).isoformat(),
            }
        except ConnectorError as error:
            status = (
                "rate_limited"
                if error.code == "rate_limited"
                else "external_limit"
                if error.code == "http_403"
                else "unavailable"
            )
            return {
                "status": status,
                "detail": error.message,
                "checked_at": datetime.now(UTC).isoformat(),
            }

    async def search(
        self, query: str, *, limit: int, since: datetime | None = None
    ) -> list[ConnectorItem]:
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        per_scope = max(1, min(100, (limit + len(self.scopes) - 1) // len(self.scopes)))

        async def collect(
            scope: str,
        ) -> tuple[list[dict[str, Any]], ConnectorDiagnostics, Exception | None]:
            endpoint, qualifier = "repositories", ""
            if scope == "issues":
                endpoint, qualifier = "issues", " is:issue"
            elif scope == "pull_requests":
                endpoint, qualifier = "issues", " is:pr"
            created = f" created:>{since.date().isoformat()}" if since else ""
            try:
                payload, _latency = await self.request_json(
                    "GET",
                    f"{self.metadata.base_url}/search/{endpoint}",
                    params={
                        "q": f"{query}{qualifier}{created}",
                        "per_page": per_scope,
                        "sort": "updated",
                    },
                    headers=headers,
                )
                values = payload.get("items", [])
                if not isinstance(values, list):
                    raise TypeError("GitHub search items payload must be a list")
                return (
                    [{**item, "_mirsad_type": scope} for item in values],
                    self.last_diagnostics,
                    None,
                )
            except Exception as exc:
                return [], self.last_diagnostics, exc

        operation_started = perf_counter()
        runs = await asyncio.gather(*(collect(scope) for scope in self.scopes))
        failures = [run[2] for run in runs if run[2] is not None]
        successful = [run for run in runs if run[2] is None]
        if not successful and failures:
            raise failures[0]
        payloads = [item for run in successful for item in run[0]][:limit]
        items = self.normalize_payloads(payloads)
        diagnostics = self.last_diagnostics
        scope_diagnostics = [run[1] for run in runs]
        diagnostics.request_latency_ms = max(
            (item.request_latency_ms for item in scope_diagnostics), default=0
        )
        diagnostics.total_latency_ms = (perf_counter() - operation_started) * 1000
        diagnostics.http_status = next(
            (item.http_status for item in scope_diagnostics if item.http_status), None
        )
        diagnostics.attempt_count = sum(item.attempt_count for item in scope_diagnostics)
        diagnostics.attempt_latencies_ms = [
            latency for item in scope_diagnostics for latency in item.attempt_latencies_ms
        ]
        if failures:
            first_failure = failures[0]
            if isinstance(first_failure, ConnectorError):
                diagnostics.warning_code = first_failure.code
                diagnostics.warning_message = "One or more configured GitHub search scopes failed"
                diagnostics.warning_status_code = first_failure.status_code
            else:
                diagnostics.warning_code = "invalid_payload"
                diagnostics.warning_message = (
                    "One or more configured GitHub scopes returned invalid data"
                )
        return items

    def normalize(self, payload: dict[str, Any]) -> ConnectorItem:
        source_type = str(payload.get("_mirsad_type") or "repositories")
        if source_type != "repositories":
            user = payload.get("user") or {}
            repository_url = str(payload.get("repository_url") or "")
            repository = repository_url.removeprefix("https://api.github.com/repos/")
            subtype = "pull_request" if source_type == "pull_requests" else "issue"
            labels = payload.get("labels") or []
            return ConnectorItem(
                source=self.metadata.key,
                external_id=f"{subtype}:{payload.get('id', payload.get('number', 'unknown'))}",
                canonical_url=str(payload.get("html_url", "")),
                author=user.get("login"),
                title=payload.get("title"),
                text=str(payload.get("body") or payload.get("title") or ""),
                published_at=parse_datetime(payload.get("updated_at") or payload.get("created_at")),
                language="und",
                raw_metrics={
                    **available_metrics(payload, {"comments": "comments"}),
                    **available_metrics(
                        payload.get("reactions") or {}, {"reactions": "total_count"}
                    ),
                },
                raw_metadata={
                    "source_type": subtype,
                    "repository": repository,
                    "number": payload.get("number"),
                    "state": payload.get("state"),
                    "labels": [label.get("name") for label in labels if isinstance(label, dict)],
                },
            )
        owner = payload.get("owner") or {}
        return ConnectorItem(
            source=self.metadata.key,
            external_id=str(payload.get("id", payload.get("full_name", "unknown"))),
            canonical_url=str(payload.get("html_url", "https://github.com")),
            author=owner.get("login"),
            title=payload.get("full_name") or payload.get("name"),
            text=str(payload.get("description") or payload.get("full_name") or ""),
            published_at=parse_datetime(payload.get("updated_at") or payload.get("created_at")),
            language="und",
            raw_metrics=available_metrics(
                payload,
                {
                    "stars": "stargazers_count",
                    "forks": "forks_count",
                    "comments": "open_issues_count",
                },
            ),
            raw_metadata={
                "source_type": "repository",
                "topics": payload.get("topics", []),
                "license": (payload.get("license") or {}).get("spdx_id"),
                "default_branch": payload.get("default_branch"),
                "programming_language": payload.get("language"),
            },
        )
