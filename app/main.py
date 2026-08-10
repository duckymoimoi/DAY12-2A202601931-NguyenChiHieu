"""Agent service — điểm ráp nối của cả lab (CP1, CP3, CP4).

Luồng một request tới /ask:

    client ──► verify_api_key ──► rate_limiter ──► cost_guard
                                                       │
                              store.get_history ◄──────┘
                                       │
                                    ask_llm
                                       │
                              store.append × 2 ──► cost_guard.record ──► log_event
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .auth import verify_api_key
from .config import get_settings
from .copilot import CloudCopilot
from .cost_guard import CostGuard
from .lifecycle import lifecycle
from .logging_utils import log_event
from .rate_limiter import RateLimiter
from .store import ConversationStore, get_redis_client

SERVICE_NAME = "day12-agent"
SERVICE_VERSION = "1.0.0"
STATIC_DIR = Path(__file__).parent / "static"


# ─────────────────────────────────────────────────────────────
# Providers — CHO SẴN
# Tách ra thành hàm để test có thể thay bằng Redis giả qua
# app.dependency_overrides, và để kết nối Redis chỉ tạo khi thật sự cần.
# ─────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def get_store() -> ConversationStore:
    return ConversationStore(get_redis_client())


@lru_cache(maxsize=1)
def get_rate_limiter() -> RateLimiter:
    return RateLimiter(get_redis_client(), get_settings().rate_limit_per_minute)


@lru_cache(maxsize=1)
def get_cost_guard() -> CostGuard:
    return CostGuard(get_redis_client(), get_settings().monthly_budget_usd)


@lru_cache(maxsize=1)
def get_copilot() -> CloudCopilot:
    return CloudCopilot(get_settings())


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """CHO SẴN — chạy lúc app khởi động và lúc tắt."""
    lifecycle.install()
    log_event("service_started", service=SERVICE_NAME, version=SERVICE_VERSION)
    yield
    log_event("service_stopped", service=SERVICE_NAME)


app = FastAPI(title="Day 12 Production Agent", version=SERVICE_VERSION, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


@app.get("/", include_in_schema=False)
def index():
    """Serve the optional browser demo without changing the API contract."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/capabilities")
def capabilities():
    """Public, secret-free metadata used by the browser demo."""
    return get_copilot().capabilities()


# ─────────────────────────────────────────────────────────────
# Health & readiness
# ─────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    """Liveness probe — process còn sống không?

    TODO (CP1 + CP4):
      - Đang tắt dần (``lifecycle.shutting_down``) → trả
        ``JSONResponse(status_code=503, content={"status": "shutting_down"})``
      - Bình thường → ``{"status": "ok", "service": SERVICE_NAME,
        "version": SERVICE_VERSION}`` (mặc định FastAPI trả 200).

    Endpoint này phải **nhẹ**: không gọi Redis, không query DB. Nó chỉ trả
    lời câu hỏi "có cần restart container này không?". Nếu nó phụ thuộc
    Redis, Redis chết một nhịp là cả cụm container bị restart theo.
    """
    if lifecycle.shutting_down:
        return JSONResponse(
            status_code=503,
            content={"status": "shutting_down"},
        )

    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
    }


@app.get("/ready")
def ready(store: ConversationStore = Depends(get_store)):
    """Readiness probe — đã sẵn sàng nhận traffic chưa?

    TODO (CP4):
      - Đang tắt dần → 503 ``{"status": "shutting_down"}``
      - ``store.ping()`` False → 503 ``{"status": "not ready", "redis": False}``
      - Ngược lại → ``{"status": "ready", "redis": True}``

    Khác /health ở chỗ: endpoint này ĐƯỢC PHÉP kiểm tra dependency. Load
    balancer dùng nó để quyết định có đẩy request vào instance này không.
    """
    if lifecycle.shutting_down:
        return JSONResponse(
            status_code=503,
            content={"status": "shutting_down"},
        )

    if not store.ping():
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "redis": False},
        )

    return {"status": "ready", "redis": True}


@app.post("/guardrails/test")
def test_guardrails(
    user_id: str = Depends(verify_api_key),
    limiter: RateLimiter = Depends(get_rate_limiter),
    guard: CostGuard = Depends(get_cost_guard),
):
    """Run an isolated guardrail diagnostic without calling the LLM.

    The temporary rate-limit key expires normally after 60 seconds. Cost is only
    estimated for ``check`` and is never recorded, so this endpoint cannot consume
    a user's real monthly budget.
    """
    run_id = uuid4().hex[:12]
    test_user = f"guardrail-test:{user_id}:{run_id}"
    tested_limit = min(max(limiter.limit, 1), 50)
    diagnostic_limiter = RateLimiter(limiter.client, tested_limit)

    allowed_requests = 0
    rate_status = None
    for _ in range(tested_limit + 1):
        try:
            diagnostic_limiter.check(test_user)
            allowed_requests += 1
        except HTTPException as exc:
            rate_status = exc.status_code
            break

    simulated_cost = guard.budget + max(0.01, guard.budget * 0.01)
    cost_status = None
    try:
        guard.check(test_user, estimated_cost=simulated_cost)
    except HTTPException as exc:
        cost_status = exc.status_code

    log_event(
        "guardrail_test_completed",
        user_id=user_id,
        run_id=run_id,
        rate_limit_protected=rate_status == 429,
        cost_guard_protected=cost_status == 402,
        llm_calls=0,
    )

    return {
        "run_id": run_id,
        "isolated": True,
        "llm_calls": 0,
        "rate_limit": {
            "protected": rate_status == 429,
            "status_code": rate_status,
            "configured_limit": limiter.limit,
            "tested_limit": tested_limit,
            "allowed_requests": allowed_requests,
            "window_seconds": 60,
        },
        "cost_guard": {
            "protected": cost_status == 402,
            "status_code": cost_status,
            "monthly_budget_usd": guard.budget,
            "simulated_cost_usd": round(simulated_cost, 6),
            "cost_recorded": False,
        },
    }


# ─────────────────────────────────────────────────────────────
# Endpoint chính
# ─────────────────────────────────────────────────────────────
@app.post("/ask")
def ask(
    payload: AskRequest,
    user_id: str = Depends(verify_api_key),
    store: ConversationStore = Depends(get_store),
    limiter: RateLimiter = Depends(get_rate_limiter),
    guard: CostGuard = Depends(get_cost_guard),
):
    """Hỏi agent một câu.

    TODO (CP3 + CP4) — làm ĐÚNG THỨ TỰ sau:
      1. ``limiter.check(user_id)``           → 429 nếu gọi quá nhanh
      2. ``guard.check(user_id)``             → 402 nếu hết ngân sách
      3. ``history = store.get_history(user_id)``
      4. ``result = ask_llm(payload.question, history)``
      5. ``store.append(user_id, "user", payload.question)`` và
         ``store.append(user_id, "assistant", result["answer"])``
      6. ``guard.record(user_id, result["cost_usd"])``
      7. ``log_event("ask_completed", user_id=user_id,
         tokens_in=result["tokens_in"], tokens_out=result["tokens_out"],
         cost_usd=result["cost_usd"])``
      8. trả về::

            {
                "answer": result["answer"],
                "user_id": user_id,
                "history_length": len(history),
                "cost_usd": result["cost_usd"],
                "tokens": {"in": result["tokens_in"], "out": result["tokens_out"]},
            }

    Vì sao check trước rồi mới gọi LLM? Vì tiền mất ở bước gọi LLM. Chặn sau
    khi đã gọi thì bạn vừa trả tiền vừa trả lỗi.

    ``user_id`` do ``verify_api_key`` trả về, nên request không có API key
    hợp lệ sẽ dừng ở 401 trước khi chạm vào bất cứ dòng nào ở đây.
    """
    request_started = perf_counter()
    trace_id = uuid4().hex[:12]
    trace_steps = [
        {
            "name": "auth",
            "label": "API key authentication",
            "status": "ok",
            "duration_ms": None,
            "detail": "X-API-Key hợp lệ",
        }
    ]

    started_at = perf_counter()
    limiter.check(user_id)
    trace_steps.append(
        {
            "name": "rate_limit",
            "label": "Sliding-window rate limit",
            "status": "ok",
            "duration_ms": round((perf_counter() - started_at) * 1000, 2),
        }
    )

    started_at = perf_counter()
    guard.check(user_id)
    trace_steps.append(
        {
            "name": "cost_guard",
            "label": "Monthly cost guard",
            "status": "ok",
            "duration_ms": round((perf_counter() - started_at) * 1000, 2),
        }
    )

    started_at = perf_counter()
    history = store.get_history(user_id)
    trace_steps.append(
        {
            "name": "history",
            "label": "Redis conversation history",
            "status": "ok",
            "duration_ms": round((perf_counter() - started_at) * 1000, 2),
            "detail": f"{len(history)} messages",
        }
    )
    result = get_copilot().ask(payload.question, history)
    trace_steps.extend(result.get("trace", []))

    started_at = perf_counter()
    store.append(user_id, "user", payload.question)
    store.append(user_id, "assistant", result["answer"])
    guard.record(user_id, result["cost_usd"])
    trace_steps.append(
        {
            "name": "persistence",
            "label": "Persist history + cost",
            "status": "ok",
            "duration_ms": round((perf_counter() - started_at) * 1000, 2),
            "detail": "Redis",
        }
    )
    total_ms = round((perf_counter() - request_started) * 1000, 2)

    log_event(
        "ask_completed",
        user_id=user_id,
        tokens_in=result["tokens_in"],
        tokens_out=result["tokens_out"],
        cost_usd=result["cost_usd"],
        trace_id=trace_id,
        duration_ms=total_ms,
    )

    return {
        "answer": result["answer"],
        "user_id": user_id,
        "history_length": len(history),
        "cost_usd": result["cost_usd"],
        "tokens": {
            "in": result["tokens_in"],
            "out": result["tokens_out"],
        },
        "provider": result.get("provider", "mock"),
        "model": result.get("model", "mock-llm"),
        "knowledge_mode": result.get("knowledge_mode", "offline"),
        "sources": result.get("sources", []),
        "warning": result.get("warning"),
        "routing": result.get("routing"),
        "trace": {
            "id": trace_id,
            "total_ms": total_ms,
            "steps": trace_steps,
        },
    }


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
