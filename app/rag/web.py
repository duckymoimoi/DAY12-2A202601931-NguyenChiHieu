"""Web retrieval through Tavily, with optional focused Firecrawl scraping."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import httpx

from .local import Source, normalize


class WebRetrievalError(RuntimeError):
    pass


TRUSTED_DOMAIN_HINTS = {
    "groq": ["console.groq.com"],
    "render": ["render.com"],
    "docker": ["docs.docker.com"],
    "redis": ["redis.io"],
    "fastapi": ["fastapi.tiangolo.com"],
    "github": ["docs.github.com"],
    "kubernetes": ["kubernetes.io"],
    "python": ["docs.python.org"],
    "terraform": ["developer.hashicorp.com"],
}

SEARCH_QUERY_EXPANSIONS = {
    "terraform": "terraform deploy web application infrastructure as code tutorial",
    "kubernetes": "kubernetes deployment service official documentation",
    "ansible": "ansible deploy web application official documentation",
}


def trusted_domains_for_query(query: str) -> list[str]:
    normalized = normalize(query)
    domains: list[str] = []
    for marker, candidates in TRUSTED_DOMAIN_HINTS.items():
        if marker in normalized:
            domains.extend(candidates)
    return list(dict.fromkeys(domains))[:5]


def search_query_for_web(query: str, trusted_domains: list[str]) -> str:
    if not trusted_domains:
        return query
    normalized = normalize(query)
    suffix = " official documentation"
    for marker, expansion in SEARCH_QUERY_EXPANSIONS.items():
        if marker in normalized:
            suffix += f" {expansion}"
    if "groq" in normalized and any(
        marker in normalized for marker in ("thay", "ngung", "deprecat", "replacement")
    ):
        suffix += " deprecation replacement"
    sites = " ".join(f"site:{domain}" for domain in trusted_domains)
    return f"{normalized} {suffix} {sites}".strip()


def _domain_allowed(url: str, trusted_domains: list[str]) -> bool:
    if not trusted_domains:
        return True
    hostname = (urlparse(url).hostname or "").casefold()
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in trusted_domains)


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
        trusted_domains = trusted_domains_for_query(query)
        request_body = {
            "query": search_query_for_web(query, trusted_domains),
            "search_depth": "basic",
            "max_results": self.max_results,
            "include_answer": False,
            "include_raw_content": False,
        }
        if trusted_domains:
            request_body["include_domains"] = trusted_domains
        try:
            with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = client.post(
                    "https://api.tavily.com/search",
                    headers={"Authorization": f"Bearer {self.tavily_api_key}"},
                    json=request_body,
                )
                response.raise_for_status()
                rows = response.json().get("results", [])
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise WebRetrievalError("Tavily search failed") from exc

        sources: list[Source] = []
        for row in rows:
            url = str(row.get("url", ""))
            if not _domain_allowed(url, trusted_domains) or not _safe_public_url(url):
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
