"""Dependency-free Markdown retrieval suitable for a small teaching corpus."""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Source:
    title: str
    uri: str
    content: str
    source_type: str = "local"
    score: float = 0.0

    def public(self) -> dict[str, str | float]:
        data = asdict(self)
        data.pop("content", None)
        data["type"] = data.pop("source_type")
        return data


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.casefold())
    no_marks = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return no_marks.replace("đ", "d")


def tokenize(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9][a-z0-9.+#/-]*", normalize(text)) if len(token) > 1]


class LocalMarkdownRetriever:
    """Ranks Markdown sections with a compact BM25 implementation."""

    DEFAULT_FILES = ("README.md", "LAB_GUIDE.md", "DEPLOYMENT.md")

    def __init__(self, root: Path, knowledge_dir: str = "knowledge") -> None:
        self.root = root
        self.knowledge_dir = root / knowledge_dir
        self.sources = self._load_sources()
        self._tokens = [tokenize(f"{source.title} {source.content}") for source in self.sources]
        self._average_length = (
            sum(map(len, self._tokens)) / len(self._tokens) if self._tokens else 1.0
        )
        self._document_frequency: dict[str, int] = {}
        for terms in self._tokens:
            for term in set(terms):
                self._document_frequency[term] = self._document_frequency.get(term, 0) + 1

    def _paths(self) -> list[Path]:
        paths = [self.root / name for name in self.DEFAULT_FILES]
        if self.knowledge_dir.exists():
            paths.extend(sorted(self.knowledge_dir.glob("*.md")))
        return [path for path in paths if path.is_file()]

    def _load_sources(self) -> list[Source]:
        sources: list[Source] = []
        heading_pattern = re.compile(r"^(#{1,4})\s+(.+?)\s*$", re.MULTILINE)
        for path in self._paths():
            text = path.read_text(encoding="utf-8")
            matches = list(heading_pattern.finditer(text))
            if not matches:
                sources.append(Source(path.stem, path.relative_to(self.root).as_posix(), text.strip()))
                continue
            for index, match in enumerate(matches):
                start = match.end()
                end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
                body = text[start:end].strip()
                if body:
                    uri = f"{path.relative_to(self.root).as_posix()}#{normalize(match.group(2)).replace(' ', '-')}"
                    sources.append(Source(match.group(2).strip(), uri, body))
        return sources

    def search(self, query: str, limit: int = 4) -> list[Source]:
        query_terms = list(dict.fromkeys(tokenize(query)))
        if not query_terms or not self.sources:
            return []
        n_docs = len(self.sources)
        scored: list[Source] = []
        for source, terms in zip(self.sources, self._tokens):
            if not terms:
                continue
            frequencies = {term: terms.count(term) for term in query_terms}
            score = 0.0
            for term, frequency in frequencies.items():
                if not frequency:
                    continue
                df = self._document_frequency.get(term, 0)
                idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
                length_factor = 1 - 0.75 + 0.75 * len(terms) / self._average_length
                score += idf * (frequency * 2.2) / (frequency + 1.2 * length_factor)
            if score > 0:
                scored.append(
                    Source(source.title, source.uri, source.content, score=round(score, 4))
                )
        return sorted(scored, key=lambda item: item.score, reverse=True)[:limit]
