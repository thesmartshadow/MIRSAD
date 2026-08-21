from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import unquote, urlsplit, urlunsplit


class ContentType(StrEnum):
    POST = "post"
    COMMENT = "comment"
    PROFILE = "profile"
    COMMUNITY = "community"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class ClassifiedUrl:
    platform: str
    content_type: ContentType
    canonical_url: str
    canonical_content_id: str | None
    author_handle: str | None = None
    community: str | None = None

    @property
    def is_content(self) -> bool:
        return self.content_type in {ContentType.POST, ContentType.COMMENT}


_X_HOSTS = {"x.com", "twitter.com"}
_THREADS_HOSTS = {"threads.net", "threads.com"}
_REDDIT_HOSTS = {"reddit.com", "redd.it"}
_HANDLE = re.compile(r"^[A-Za-z0-9_]{1,30}$")
_REDDIT_ID = re.compile(r"^[A-Za-z0-9]{4,16}$")
_THREAD_ID = re.compile(r"^[A-Za-z0-9_-]{5,100}$")


def _safe_parts(value: str):
    if not isinstance(value, str) or len(value) > 2048:
        return None
    value = value.strip()
    try:
        parts = urlsplit(value)
        port = parts.port
    except (ValueError, UnicodeError):
        return None
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        return None
    if parts.username or parts.password or port not in {None, 80, 443}:
        return None
    try:
        host = parts.hostname.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError:
        return None
    if host.startswith("www."):
        host = host[4:]
    elif host.startswith("mobile.") or host.startswith("old.") or host.startswith("new."):
        host = host.split(".", 1)[1]
    try:
        address = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        address = None
    if address is not None:
        return None
    path = unquote(parts.path or "/")
    if "\x00" in path or "\\" in path:
        return None
    return host, [segment for segment in path.split("/") if segment]


def _canonical(host: str, segments: list[str]) -> str:
    path = "/" + "/".join(segments)
    return urlunsplit(("https", host, path, "", ""))


def classify_x_url(value: str) -> ClassifiedUrl | None:
    parsed = _safe_parts(value)
    if parsed is None:
        return None
    host, segments = parsed
    if host not in _X_HOSTS:
        return None
    if (
        len(segments) >= 4
        and [segment.casefold() for segment in segments[:3]] == ["i", "web", "status"]
        and segments[3].isdigit()
    ):
        post_id = segments[3]
        return ClassifiedUrl(
            "x",
            ContentType.POST,
            _canonical("x.com", ["i", "web", "status", post_id]),
            post_id,
        )
    if len(segments) >= 3 and segments[1].casefold() == "status" and segments[2].isdigit():
        handle = segments[0]
        if not _HANDLE.fullmatch(handle):
            return None
        post_id = segments[2]
        return ClassifiedUrl(
            "x",
            ContentType.POST,
            _canonical("x.com", [handle, "status", post_id]),
            post_id,
            handle,
        )
    if len(segments) == 1 and _HANDLE.fullmatch(segments[0]):
        handle = segments[0]
        return ClassifiedUrl(
            "x", ContentType.PROFILE, _canonical("x.com", [handle]), handle.casefold(), handle
        )
    return ClassifiedUrl("x", ContentType.OTHER, _canonical("x.com", segments), None)


def classify_threads_url(value: str) -> ClassifiedUrl | None:
    parsed = _safe_parts(value)
    if parsed is None:
        return None
    host, segments = parsed
    if host not in _THREADS_HOSTS:
        return None
    if len(segments) >= 3 and segments[0].startswith("@") and segments[1] == "post":
        handle = segments[0][1:]
        post_id = segments[2]
        if not _HANDLE.fullmatch(handle) or not _THREAD_ID.fullmatch(post_id):
            return None
        return ClassifiedUrl(
            "threads",
            ContentType.POST,
            _canonical("www.threads.com", [f"@{handle}", "post", post_id]),
            post_id,
            handle,
        )
    if len(segments) >= 2 and segments[0] in {"t", "post"}:
        post_id = segments[1]
        if not _THREAD_ID.fullmatch(post_id):
            return None
        return ClassifiedUrl(
            "threads",
            ContentType.POST,
            _canonical("www.threads.com", ["t", post_id]),
            post_id,
        )
    if len(segments) == 1 and segments[0].startswith("@"):
        handle = segments[0][1:]
        if not _HANDLE.fullmatch(handle):
            return None
        return ClassifiedUrl(
            "threads",
            ContentType.PROFILE,
            _canonical("www.threads.com", [f"@{handle}"]),
            handle.casefold(),
            handle,
        )
    return ClassifiedUrl(
        "threads", ContentType.OTHER, _canonical("www.threads.com", segments), None
    )


def classify_reddit_url(value: str) -> ClassifiedUrl | None:
    parsed = _safe_parts(value)
    if parsed is None:
        return None
    host, segments = parsed
    if host not in _REDDIT_HOSTS:
        return None
    if host == "redd.it":
        if len(segments) == 1 and _REDDIT_ID.fullmatch(segments[0]):
            post_id = segments[0]
            return ClassifiedUrl(
                "reddit",
                ContentType.POST,
                _canonical("www.reddit.com", ["comments", post_id]),
                post_id.casefold(),
            )
        return None
    lower = [segment.casefold() for segment in segments]
    if len(segments) >= 4 and lower[0] == "r" and lower[2] == "comments":
        community, post_id = segments[1], segments[3]
        if not _REDDIT_ID.fullmatch(post_id):
            return None
        canonical_segments = ["r", community, "comments", post_id]
        if len(segments) >= 5:
            canonical_segments.append(segments[4])
        comment_id = segments[5] if len(segments) >= 6 else None
        if comment_id and _REDDIT_ID.fullmatch(comment_id):
            canonical_segments.append(comment_id)
            return ClassifiedUrl(
                "reddit",
                ContentType.COMMENT,
                _canonical("www.reddit.com", canonical_segments),
                f"{post_id.casefold()}:{comment_id.casefold()}",
                community=community,
            )
        return ClassifiedUrl(
            "reddit",
            ContentType.POST,
            _canonical("www.reddit.com", canonical_segments),
            post_id.casefold(),
            community=community,
        )
    if len(segments) >= 2 and lower[0] == "comments" and _REDDIT_ID.fullmatch(segments[1]):
        post_id = segments[1]
        return ClassifiedUrl(
            "reddit",
            ContentType.POST,
            _canonical("www.reddit.com", ["comments", post_id]),
            post_id.casefold(),
        )
    if len(segments) == 2 and lower[0] == "r":
        return ClassifiedUrl(
            "reddit",
            ContentType.COMMUNITY,
            _canonical("www.reddit.com", ["r", segments[1]]),
            segments[1].casefold(),
            community=segments[1],
        )
    if len(segments) == 2 and lower[0] in {"user", "u"}:
        return ClassifiedUrl(
            "reddit",
            ContentType.PROFILE,
            _canonical("www.reddit.com", ["user", segments[1]]),
            segments[1].casefold(),
            author_handle=segments[1],
        )
    return ClassifiedUrl("reddit", ContentType.OTHER, _canonical("www.reddit.com", segments), None)


def classify_platform_url(platform: str, value: str) -> ClassifiedUrl | None:
    classifiers = {
        "x": classify_x_url,
        "threads": classify_threads_url,
        "reddit": classify_reddit_url,
    }
    classifier = classifiers.get(platform)
    return classifier(value) if classifier else None
