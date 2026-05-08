"""Web search helper for optional topic expansion discovery."""

from __future__ import annotations

import os
from typing import Any

import requests

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


def search_web_brave(query: str, count: int = 10) -> list[dict[str, str]]:
    """Search Brave and return normalized title/url/description records."""
    api_key = os.getenv("BRAVE_SEARCH_API_KEY")
    if not api_key:
        raise RuntimeError("BRAVE_SEARCH_API_KEY is not set.")

    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": api_key,
    }
    params = {
        "q": query,
        "count": min(max(count, 1), 20),
        "search_lang": "en",
        "country": "us",
    }
    response = requests.get(BRAVE_SEARCH_URL, headers=headers, params=params, timeout=20)
    response.raise_for_status()
    payload: dict[str, Any] = response.json()
    web_results = payload.get("web", {}).get("results", [])

    out: list[dict[str, str]] = []
    for item in web_results:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "title": str(item.get("title") or ""),
                "url": str(item.get("url") or ""),
                "description": str(item.get("description") or ""),
            }
        )
    return out
