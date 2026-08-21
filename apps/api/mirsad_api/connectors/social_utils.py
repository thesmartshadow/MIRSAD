from __future__ import annotations

import html
import re
from collections.abc import Mapping
from typing import Any

HTML_TAG = re.compile(r"<[^>]+>")
HASHTAG = re.compile(r"(?<!\w)#([\w\u0600-\u06ff]+)", re.UNICODE)
MENTION = re.compile(r"(?<!\w)@([\w.\-]+)", re.UNICODE)


def optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def available_metrics(payload: Mapping[str, Any], mapping: Mapping[str, str]) -> dict[str, int]:
    output: dict[str, int] = {}
    for normalized, upstream in mapping.items():
        value = optional_int(payload.get(upstream))
        if value is not None:
            output[normalized] = value
    return output


def extract_entities(text: str) -> tuple[tuple[str, ...] | None, tuple[str, ...] | None]:
    hashtags = tuple(dict.fromkeys(HASHTAG.findall(text))) or None
    mentions = tuple(dict.fromkeys(MENTION.findall(text))) or None
    return hashtags, mentions


def plain_text(value: Any) -> str:
    text = html.unescape(HTML_TAG.sub(" ", str(value or "")))
    return " ".join(text.split())
