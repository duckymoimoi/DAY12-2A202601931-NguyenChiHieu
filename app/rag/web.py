"""Web retrieval through Tavily, with optional focused Firecrawl scraping."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import httpx

from .local import Source


class WebRetrievalError(RuntimeError):
    pass


def _safe_public_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    if parsed.hostname.casefold() in {"localhost", "localhost.localdomain"}:
        return False
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(parsed.hostname, None)}
        return all(
            not (
                ipaddress.ip_address(address).is_private
                or ipaddress.ip_address(address).is_loopback
                or ipaddress.ip_address(address).is_link_local
                or ipaddress.ip_address(address).is_reserved
            )
            for address in addresses
        )
    except (socket.gaierror, ValueError):
        return False


class WebRetriever:
    def __init__(
        self,
        *,
        tavily_api_key: str,
        firecrawl_api_key: str | None,
        timeout_seconds: float,
        max_results: int,
        scrape_enabled: bool,
        scrape_max_pages: int,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.tavily_api_key = tavily_api_key
        self.firecrawl_api_key = firecrawl_api_key
        self.timeout_seconds = timeout_seconds
        self.max_results = max(1, min(max_results, 8))
        self.scrape_enabled = scrape_enabled
        self.scrape_max_pages = max(0, min(scrape_max_pages, 2))
        self.transport = transport

    def search(self, query: str) -> list[Source]:
        try:
            with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = client.post(
                    "https://api.tavily.com/search",
                    headers={"Authorization": f"Bearer {self.tavily_api_key}"},
                    json={
                        "query": query,
                        "search_depth": "basic",
                        "max_results": self.max_results,
                        "include_answer": False,
                        "include_raw_content": False,
                    },
                )
                response.raise_for_status()
                rows = response.json().get("results", [])
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise WebRetrievalError("Tavily search failed") from exc

        sources: list[Source] = []
        for row in rows:
            url = str(row.get("url", ""))
            if not _safe_public_url(url):
                continue
            sources.append(
                Source(
                    title=str(row.get("title") or url),
                    uri=url,
                    content=str(row.get("content") or "")[:5000],
                    source_type="web",
                    score=float(row.get("score") or 0.0),
                )
            )

        if self.scrape_enabled and self.firecrawl_api_key:
            for index, source in enumerate(sources[: self.scrape_max_pages]):
                scraped = self._scrape(source.uri)
                if scraped:
                    sources[index] = Source(
                        source.title,
                        source.uri,
                        scraped[:9000],
                        source_type="web",
                        score=source.score,
                    )
        return sources

    def _scrape(self, url: str) -> str:
        if not _safe_public_url(url):
            return ""
        try:
            with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = client.post(
                    "https://api.firecrawl.dev/v2/scrape",
                    headers={"Authorization": f"Bearer {self.firecrawl_api_key}"},
                    json={"url": url, "formats": ["markdown"], "onlyMainContent": True},
                )
                response.raise_for_status()
                data = response.json().get("data") or {}
                return str(data.get("markdown") or "")
        except (httpx.HTTPError, ValueError, TypeError):
            return ""
