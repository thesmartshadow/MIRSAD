from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from .base import (
    BaseConnector,
    ConnectorCapabilities,
    ConnectorError,
    ConnectorItem,
    ConnectorMetadata,
    ConnectorValidation,
    parse_datetime,
)
from .social_utils import available_metrics, extract_entities


class TelegramConnector(BaseConnector):
    metadata = ConnectorMetadata(
        key="telegram",
        name="Telegram",
        kind="social",
        base_url="https://api.telegram.org",
        requires_credentials=True,
        confidence=62,
        category="social",
        support_level="supported_with_credentials",
        coverage_label="Public Channels only; requires a locally authorized user session",
        capabilities=ConnectorCapabilities(
            keyword_search=True,
            phrase_search=True,
            hashtag_search=True,
            recent_search=True,
            historical_search="conditional",
            date_filter="conditional",
            public_posts=True,
            comments="conditional",
            engagement_metrics=True,
            pagination=True,
            requires_credentials=True,
            paid_access="conditional",
            content_types=("posts",),
        ),
    )

    def __init__(
        self,
        api_id: int | None = None,
        api_hash: str | None = None,
        session_string: str | None = None,
        client_factory: Callable[..., Any] | None = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_string = session_string
        self.client_factory = client_factory

    def validate_configuration(self) -> tuple[bool, str | None]:
        configured = bool(self.api_id and self.api_hash and self.session_string)
        return configured, None if configured else "Public-channel user session not configured"

    def _client(self):
        if self.client_factory:
            return self.client_factory(self.session_string, self.api_id, self.api_hash)
        try:
            from telethon import TelegramClient
            from telethon.sessions import StringSession
        except ImportError as exc:  # pragma: no cover - dependency is installed in production
            raise ConnectorError(
                "telegram", "configuration_missing", "Telegram client dependency is unavailable"
            ) from exc
        return TelegramClient(StringSession(self.session_string), self.api_id, self.api_hash)

    async def validate_access(self) -> ConnectorValidation:
        if not self.validate_configuration()[0]:
            return await super().validate_access()
        client = self._client()
        try:
            async with asyncio.timeout(self.timeout):
                await client.connect()
                if not await client.is_user_authorized():
                    raise ConnectorError(
                        "telegram",
                        "http_401",
                        "Telegram user session is not authorized",
                        status_code=401,
                    )
        except TimeoutError as exc:
            raise ConnectorError(
                "telegram", "timeout", "Telegram validation timed out", retryable=True
            ) from exc
        except ConnectorError:
            raise
        except Exception as exc:
            name = type(exc).__name__.lower()
            if "flood" in name:
                raise ConnectorError(
                    "telegram", "rate_limited", "Telegram rate limit reached", retryable=True
                ) from exc
            if "auth" in name or "session" in name:
                raise ConnectorError(
                    "telegram", "http_401", "Telegram authorization was rejected", status_code=401
                ) from exc
            raise ConnectorError(
                "telegram", "dns_network", "Telegram network request failed", retryable=True
            ) from exc
        finally:
            with suppress(TimeoutError, OSError):
                await asyncio.wait_for(client.disconnect(), timeout=min(2.0, self.timeout))
        return ConnectorValidation(
            "pass", "credentials_valid", "Telegram user session is authorized", True
        )

    async def search(self, query: str, *, limit: int, since: datetime | None = None):
        if not self.validate_configuration()[0]:
            raise ConnectorError(
                "telegram", "configuration_missing", "Public-channel user session not configured"
            )
        client = self._client()
        try:
            return await asyncio.wait_for(
                self._search_client(client, query, limit=limit, since=since),
                timeout=self.timeout,
            )
        except ConnectorError:
            raise
        except TimeoutError as exc:
            raise ConnectorError(
                "telegram", "timeout", "Telegram request timed out", retryable=True
            ) from exc
        except Exception as exc:
            name = type(exc).__name__.lower()
            if "flood" in name:
                raise ConnectorError(
                    "telegram", "rate_limited", "Telegram rate limit reached", retryable=True
                ) from exc
            if "stars" in name or "payment" in name:
                raise ConnectorError(
                    "telegram",
                    "access_limited",
                    "Telegram public-channel search requires additional account access",
                ) from exc
            if "auth" in name or "session" in name:
                raise ConnectorError(
                    "telegram", "http_401", "Telegram authorization was rejected", status_code=401
                ) from exc
            raise ConnectorError(
                "telegram", "dns_network", "Telegram network request failed", retryable=True
            ) from exc
        finally:
            with suppress(TimeoutError, OSError):
                await asyncio.wait_for(client.disconnect(), timeout=min(2.0, self.timeout))

    async def _search_client(
        self, client: Any, query: str, *, limit: int, since: datetime | None
    ) -> list[ConnectorItem]:
        await client.connect()
        if not await client.is_user_authorized():
            raise ConnectorError(
                "telegram",
                "http_401",
                "Telegram user session is not authorized",
                status_code=401,
            )
        try:
            from telethon import functions, types
        except ImportError as exc:  # pragma: no cover
            raise ConnectorError(
                "telegram", "configuration_missing", "Telegram client dependency is unavailable"
            ) from exc
        payloads: list[dict[str, Any]] = []
        raw_count = 0
        offset_rate = 0
        offset_peer: Any = types.InputPeerEmpty()
        offset_id = 0
        cleaned_query = query.strip()
        hashtag = cleaned_query.removeprefix("#") if cleaned_query.startswith("#") else None

        # channels.searchPosts is the documented public-channel search operation.
        # Two bounded pages prevent a paid/flood-controlled source delaying the full search.
        for _page in range(2):
            page_limit = min(100, max(1, limit - len(payloads)))
            search_posts = getattr(functions.channels, "SearchPostsRequest", None)
            if search_posts is not None:
                request = search_posts(
                    offset_rate=offset_rate,
                    offset_peer=offset_peer,
                    offset_id=offset_id,
                    limit=page_limit,
                    hashtag=hashtag,
                    query=None if hashtag else cleaned_query,
                    allow_paid_stars=None,
                )
            else:  # pragma: no cover - compatibility with older Telethon releases
                request = functions.messages.SearchGlobalRequest(
                    q=cleaned_query,
                    filter=types.InputMessagesFilterEmpty(),
                    min_date=since or datetime.fromtimestamp(0, tz=UTC),
                    max_date=datetime.now(UTC),
                    offset_rate=offset_rate,
                    offset_peer=offset_peer,
                    offset_id=offset_id,
                    limit=page_limit,
                    broadcasts_only=True,
                )
            response = await client(request)
            messages = list(getattr(response, "messages", []))
            raw_count += len(messages)
            chats = {
                int(chat.id): chat
                for chat in getattr(response, "chats", [])
                if getattr(chat, "broadcast", False) and getattr(chat, "username", None)
            }
            for message in messages:
                published_at = parse_datetime(getattr(message, "date", None))
                if since and published_at and published_at < since:
                    continue
                peer = getattr(message, "peer_id", None)
                channel_id = getattr(peer, "channel_id", None)
                channel = chats.get(int(channel_id)) if channel_id is not None else None
                if channel is not None:
                    payloads.append(self._message_payload(message, channel))
                if len(payloads) >= limit:
                    break
            next_rate = getattr(response, "next_rate", None)
            if len(payloads) >= limit or not messages or next_rate is None:
                break
            last_message = messages[-1]
            get_input_entity = getattr(client, "get_input_entity", None)
            if get_input_entity is None:
                break
            offset_rate = int(next_rate)
            offset_id = int(getattr(last_message, "id", 0))
            offset_peer = await get_input_entity(getattr(last_message, "peer_id", None))

        items = self.normalize_payloads(payloads[:limit])
        self.last_diagnostics.raw_result_count = raw_count
        return items

    @staticmethod
    def _message_payload(message: Any, channel: Any) -> dict[str, Any]:
        reactions = getattr(getattr(message, "reactions", None), "results", None)
        reaction_count = (
            sum(int(getattr(reaction, "count", 0)) for reaction in reactions)
            if reactions is not None
            else None
        )
        replies = getattr(getattr(message, "replies", None), "replies", None)
        return {
            "id": getattr(message, "id", None),
            "message": getattr(message, "message", None),
            "date": getattr(message, "date", None),
            "views": getattr(message, "views", None),
            "forwards": getattr(message, "forwards", None),
            "replies": replies,
            "reactions": reaction_count,
            "media": getattr(message, "media", None) is not None,
            "channel_id": getattr(channel, "id", None),
            "channel_title": getattr(channel, "title", None),
            "channel_username": getattr(channel, "username", None),
        }

    def normalize(self, payload: dict[str, Any]) -> ConnectorItem:
        message_id = str(payload["id"])
        username = str(payload["channel_username"])
        text = str(payload.get("message") or "")
        hashtags, mentions = extract_entities(text)
        return ConnectorItem(
            source="telegram",
            external_id=f"{username}:{message_id}",
            canonical_url=f"https://t.me/{username}/{message_id}",
            author=payload.get("channel_title") or username,
            author_handle=username,
            title=None,
            text=text,
            published_at=parse_datetime(payload.get("date")),
            language="und",
            hashtags=hashtags,
            mentions=mentions,
            media_type="post_media" if payload.get("media") else "post",
            raw_metrics=available_metrics(
                payload,
                {
                    "views": "views",
                    "forwards": "forwards",
                    "replies": "replies",
                    "reactions": "reactions",
                },
            ),
            raw_metadata={
                "source_type": "post",
                "coverage": "public_channels",
                "channel_id": payload.get("channel_id"),
            },
        )
