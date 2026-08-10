from __future__ import annotations

import httpx

from app.config import Settings
from app.copilot import (
    CloudCopilot,
    _context_block,
    local_query_coverage,
    should_search_web,
    web_search_reason,
)
from app.llm.groq import GroqProvider
from app.rag.local import LocalMarkdownRetriever, Source
from app.rag.web import _domain_allowed, search_query_for_web, trusted_domains_for_query


def test_local_retriever_finds_relevant_markdown(repo_root):
    retriever = LocalMarkdownRetriever(repo_root)
    results = retriever.search("Docker multi-stage build", limit=3)

    assert results
    assert any("Docker" in result.title or "docker" in result.content.casefold() for result in results)
    assert all(result.source_type == "local" for result in results)


def test_local_retriever_indexes_project_walkthrough(repo_root):
    retriever = LocalMarkdownRetriever(repo_root)
    results = retriever.search("operational trace luồng request", limit=8)

    assert any(result.uri.startswith("PROJECT_WALKTHROUGH.md") for result in results)


def test_web_router_uses_web_for_current_information():
    strong_local = [
        Source(
            "Docker multi-stage",
            "README.md",
            "Docker multi-stage build giúp deploy image nhỏ hơn.",
            score=10.0,
        )
    ]

    assert should_search_web("Render hiện nay hỗ trợ region nào?", strong_local)
    assert not should_search_web("Giải thích Docker multi-stage", strong_local)


def test_web_router_detects_important_term_missing_from_local_sources():
    local_sources = [
        Source(
            "Triển khai web",
            "PROJECT_WALKTHROUGH.md",
            "Hướng dẫn triển khai web service lên Render.",
            score=12.0,
        )
    ]
    question = "Tôi cần biết gì về triển khai web bằng Terraform?"
    coverage = local_query_coverage(question, local_sources)

    assert "terraform" in coverage["missing_terms"]
    assert coverage["ratio"] < 0.8
    assert web_search_reason(question, local_sources, coverage) == "missing_local_terms"
    assert should_search_web(question, local_sources)


def test_context_reserves_room_for_every_source():
    sources = [
        Source(f"Source {index}", f"source-{index}.md", str(index) * 5000)
        for index in range(4)
    ]
    context = _context_block(sources, max_chars=4000)

    for index in range(4):
        assert f"Source {index}" in context


def test_web_search_prefers_official_domain_for_known_topic():
    assert trusted_domains_for_query("Groq hiện hỗ trợ model nào?") == ["console.groq.com"]
    assert trusted_domains_for_query("Docker trên Render") == [
        "render.com",
        "docs.docker.com",
    ]
    query = search_query_for_web(
        "Hiện nay Groq dùng model thay thế nào?", ["console.groq.com"]
    )
    assert "site:console.groq.com" in query
    assert "deprecation replacement" in query
    assert _domain_allowed("https://console.groq.com/docs/models", ["console.groq.com"])
    assert not _domain_allowed("https://example.com/groq", ["console.groq.com"])
    assert trusted_domains_for_query("Terraform dùng thế nào?") == [
        "developer.hashicorp.com"
    ]
    terraform_query = search_query_for_web(
        "Triển khai web bằng Terraform", ["developer.hashicorp.com"]
    )
    assert "terraform deploy web application" in terraform_query


def test_groq_provider_parses_usage_and_cost():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        body = __import__("json").loads(request.content)
        assert body["reasoning_effort"] == "low"
        assert body["include_reasoning"] is False
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
        reasoning_effort="low",
        include_reasoning=False,
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
    assert result["trace"][0]["name"] == "llm"
    assert result["trace"][0]["duration_ms"] >= 0


def test_ask_returns_safe_operational_trace(client, auth_headers):
    response = client.post(
        "/ask",
        json={"question": "Docker là gì?"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    trace = response.json()["trace"]

    assert len(trace["id"]) == 12
    assert trace["total_ms"] >= 0
    names = [step["name"] for step in trace["steps"]]
    assert names[:4] == ["auth", "rate_limit", "cost_guard", "history"]
    assert "llm" in names
    assert names[-1] == "persistence"

    serialized = str(trace).casefold()
    assert "x-api-key hợp lệ" in serialized
    assert "test-api-key-cua-lab" not in serialized
    assert "system_prompt" not in serialized
