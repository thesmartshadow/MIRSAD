from __future__ import annotations

from datetime import datetime
from typing import Any

from .base import (
    BaseConnector,
    ConnectorCapabilities,
    ConnectorError,
    ConnectorItem,
    ConnectorMetadata,
)


class RestrictedConnector(BaseConnector):
    def __init__(self, metadata: ConnectorMetadata, reason: str, **kwargs: Any):
        self.metadata = metadata
        self.reason = reason
        super().__init__(**kwargs)

    def configuration_state(self) -> str:
        return "restricted"

    def validate_configuration(self) -> tuple[bool, str | None]:
        return False, self.reason

    async def search(
        self, query: str, *, limit: int, since: datetime | None = None
    ) -> list[ConnectorItem]:
        raise ConnectorError(self.metadata.key, "restricted_access", self.reason)

    def normalize(self, payload: dict[str, Any]) -> ConnectorItem:
        raise ConnectorError(self.metadata.key, "capability_restricted", self.reason)


def facebook_connector(**kwargs: Any) -> RestrictedConnector:
    return RestrictedConnector(
        ConnectorMetadata(
            key="facebook",
            name="Facebook",
            kind="social",
            base_url="https://graph.facebook.com",
            confidence=60,
            category="social",
            support_level="restricted_access",
            coverage_label="Global public-post keyword search is unavailable",
            capabilities=ConnectorCapabilities(
                author_search="conditional",
                public_posts="conditional",
                engagement_metrics="conditional",
                requires_credentials=True,
                requires_approval=True,
                content_types=("posts",),
            ),
        ),
        "Global public-post keyword search is not available with the configured API access",
        **kwargs,
    )


def linkedin_connector(**kwargs: Any) -> RestrictedConnector:
    return RestrictedConnector(
        ConnectorMetadata(
            key="linkedin",
            name="LinkedIn",
            kind="social",
            base_url="https://api.linkedin.com",
            confidence=60,
            category="social",
            support_level="restricted_access",
            coverage_label="Authorized user or organization content only",
            capabilities=ConnectorCapabilities(
                author_search="conditional",
                public_posts="conditional",
                engagement_metrics="conditional",
                pagination="conditional",
                requires_credentials=True,
                requires_approval=True,
                content_types=("posts",),
            ),
        ),
        "Global public-post search is unavailable through configured API access",
        **kwargs,
    )
