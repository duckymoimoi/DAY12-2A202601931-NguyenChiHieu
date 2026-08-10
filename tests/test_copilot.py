from __future__ import annotations

import httpx

from app.config import Settings
from app.copilot import CloudCopilot, should_search_web
from app.llm.groq import GroqProvider
from app.rag.local import LocalMarkdownRetriever, Source


def test_local_retriever_finds_relevant_markdown(repo_root):
    retriever = LocalMarkdownRetriever(repo_root)
    results = retriever.search("Docker multi-stage build", limit=3)

    assert results
    assert any("Docker" in result.title or "docker" in result.content.casefold() for result in results)
    assert all(result.source_type == "local" for result in results)


def test_web_router_uses_web_for_current_information():
    strong_local = [Source("Render", "README.md", "Render", score=10.0)]

    assert should_search_web("Render hiện nay hỗ trợ region nào?", strong_local)
    assert not should_search_web("Giải thích Docker multi-stage", strong_local)


def test_groq_provider_parses_usage_and_cost():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Câu trả lời thật"}}],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 500},
            },
        )

    provider = GroqProvider(
        api_key="test-key",
        base_url="https://api.groq.com/openai/v1",
        model="openai/gpt-oss-20b",
        timeout_seconds=2,
        max_tokens=100,
        temperature=0.2,
        input_price_per_million=0.075,
        output_price_per_million=0.30,
        transport=httpx.MockTransport(handler),
    )
    result = provider.complete([{"role": "user", "content": "test"}])

    assert result["answer"] == "Câu trả lời thật"
    assert result["tokens_in"] == 1000
    assert result["tokens_out"] == 500
    assert result["cost_usd"] == 0.000225


def test_mock_mode_keeps_offline_contract(monkeypatch):
    monkeypatch.setenv("AGENT_API_KEY", "test")
    settings = Settings(_env_file=None, llm_provider="mock")
    result = CloudCopilot(settings).ask("Docker là gì?", [])

    assert result["provider"] == "mock"
    assert result["knowledge_mode"] == "offline"
    assert result["sources"] == []
    assert result["cost_usd"] > 0
