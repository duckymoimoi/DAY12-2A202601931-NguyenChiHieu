"""CP1 — Cấu hình theo 12-Factor.

Nguyên tắc: **không có giá trị cấu hình nào nằm trong code**. Tất cả đến từ
biến môi trường, để cùng một image chạy được ở laptop, staging và production
mà không phải sửa một dòng code nào.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Toàn bộ cấu hình của service.

    TODO (CP1): khai báo các trường dưới đây. pydantic-settings tự đọc biến
    môi trường theo tên trường (không phân biệt hoa thường), nên trường
    ``agent_api_key`` sẽ lấy giá trị từ biến ``AGENT_API_KEY``.

    | Trường                  | Kiểu  | Mặc định                   |
    |-------------------------|-------|----------------------------|
    | port                    | int   | 8000                       |
    | agent_api_key           | str   | KHÔNG có mặc định (bắt buộc)|
    | redis_url               | str   | "redis://localhost:6379/0" |
    | rate_limit_per_minute   | int   | 10                         |
    | monthly_budget_usd      | float | 10.0                       |
    | log_level               | str   | "INFO"                     |

    Vì sao ``agent_api_key`` không được có giá trị mặc định? Vì mặc định
    nghĩa là app vẫn khởi động khi bạn quên set secret trên cloud — và bạn
    chỉ phát hiện ra khi ai đó đã gọi API miễn phí bằng khóa mặc định đó.
    Không mặc định = fail fast ngay lúc khởi động.
    """

    model_config = SettingsConfigDict(
        # Local development keeps shared provider keys one level above the repo,
        # while deployment platforms inject the same values as environment variables.
        # A repo-local .env (ignored by Git) wins when both files exist.
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    port: int = 8000
    agent_api_key: str
    redis_url: str = "redis://localhost:6379/0"
    rate_limit_per_minute: int = 10
    monthly_budget_usd: float = 10.0
    log_level: str = "INFO"

    # Cloud Deployment Copilot. Defaults remain offline so tests and fresh forks do
    # not unexpectedly call paid APIs.
    llm_provider: str = "mock"
    llm_fallback_to_mock: bool = True
    groq_api_key: str | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "openai/gpt-oss-20b"
    groq_timeout_seconds: float = 25.0
    groq_max_tokens: int = 900
    groq_temperature: float = 0.2
    groq_input_price_per_million: float = 0.075
    groq_output_price_per_million: float = 0.30

    rag_enabled: bool = True
    rag_top_k: int = 4
    rag_max_context_chars: int = 9000
    knowledge_dir: str = "knowledge"

    web_search_enabled: bool = False
    web_search_max_results: int = 4
    web_search_timeout_seconds: float = 10.0
    tavily_api_key: str | None = None
    firecrawl_api_key: str | None = None
    web_scrape_enabled: bool = False
    web_scrape_max_pages: int = 1


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Đọc cấu hình một lần rồi cache lại (đọc env mỗi request là lãng phí)."""
    return Settings()
