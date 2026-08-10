# Day 12 — Quy Trình Đưa Một Web Service Lên Production

> Học viên: **Nguyễn Chí Hiếu** — `2A202601931`
> Production: https://day12-agent-plt0.onrender.com

## 1. Trọng tâm của bài học

Trọng tâm Day 12 là **deployment và vận hành dịch vụ**, không phải xây dựng chatbot.
Chatbot chỉ là workload mẫu để chứng minh hạ tầng có thể phục vụ một ứng dụng thật: có
request tốn chi phí, có state, có dependency bên ngoài và cần được bảo vệ.

Sau bài này, một chương trình chạy trên laptop được chuyển thành service có thể vận hành:

1. Cấu hình tách khỏi code theo 12-Factor.
2. Có health check và log cho máy đọc.
3. Được đóng gói bằng Docker an toàn, tái lập được.
4. Có authentication, rate limit và giới hạn chi phí.
5. Đưa state ra Redis để có thể scale nhiều instance.
6. Xử lý readiness và graceful shutdown khi deploy phiên bản mới.
7. Được khai báo và triển khai lên Render bằng Blueprint.
8. Có kiểm thử và trace để xác nhận hệ thống hoạt động đúng.

## 2. Bức tranh deployment tổng thể

```mermaid
flowchart LR
    DEV[Source code] --> TEST[Automated tests]
    TEST --> IMAGE[Docker image]
    IMAGE --> REGISTRY[Render build]
    CONFIG[Environment variables<br/>và secrets] --> SERVICE[Web service]
    REGISTRY --> SERVICE
    REDIS[(Render Key Value)] --> SERVICE
    SERVICE --> HEALTH[/health]
    SERVICE --> READY[/ready]
    SERVICE --> LOGS[Structured logs]
    USERS[Client] -->|HTTPS| SERVICE
```

Một image được dùng cho mọi môi trường. Điểm khác nhau giữa local và production nằm ở
biến môi trường, secret và địa chỉ dependency, không nằm trong source code.

## 3. Quy trình từ local đến production

### Bước 1 — Chuẩn hóa cấu hình

`app/config.py` đọc cấu hình từ biến môi trường bằng `pydantic-settings`.
`AGENT_API_KEY` là bắt buộc để ứng dụng **fail fast** nếu quên cấu hình secret. Các giá trị
như port, Redis URL, quota và provider đều có thể thay đổi mà không cần build lại image.

Nguyên tắc:

- `.env` chỉ dùng local và đã bị Git bỏ qua.
- `.env.example` chỉ chứa tên biến và giá trị mẫu không nhạy cảm.
- Production secret được nhập trong Render Dashboard hoặc qua `sync: false`.
- Không in API key, connection string hay prompt nội bộ vào log/trace.

### Bước 2 — Tạo tín hiệu vận hành

Service cung cấp hai probe khác nhau:

| Endpoint | Câu hỏi cần trả lời | Khi nào lỗi |
|---|---|---|
| `/health` | Process còn sống không? | Event loop hoặc process hỏng |
| `/ready` | Instance đã sẵn sàng nhận traffic chưa? | Đang shutdown hoặc Redis không dùng được |

`/health` không kiểm tra sâu Redis vì dependency lỗi tạm thời không có nghĩa process cần
bị khởi động lại liên tục. `/ready` mới quyết định instance có nên nhận request hay không.

Log được xuất dạng JSON để nền tảng cloud có thể tìm kiếm theo event, status và user mà
không phải tách một chuỗi log tự do.

### Bước 3 — Đóng gói bằng Docker

`Dockerfile` dùng multi-stage build: stage đầu cài dependency, stage cuối chỉ nhận artifact
cần chạy. Container chạy bằng non-root user và chỉ copy những file runtime cần thiết.

`docker-compose.yml` mô tả hai service:

- `agent`: FastAPI web service.
- `redis`: state store nằm ngoài process của agent.

Tên service `redis` trở thành hostname nội bộ trong mạng Compose, vì vậy container dùng
`redis://redis:6379/0`, không dùng `localhost`.

### Bước 4 — Bảo vệ tài nguyên production

Luồng `/ask` kiểm tra các guard trước khi gọi workload tốn chi phí:

```text
request → API key → rate limit → cost guard → xử lý → lưu usage → response
```

- API key xác định người được phép gọi.
- Sliding-window rate limit chặn burst request.
- Cost guard chặn khi ngân sách tháng đã hết.
- Chỉ ghi usage sau khi workload hoàn thành.

Thứ tự này quan trọng: nếu gọi model trước rồi mới kiểm tra quota thì hệ thống vẫn mất tiền
dù cuối cùng trả lỗi cho client.

### Bước 5 — Tách state để scale ngang

Lịch sử hội thoại, cửa sổ rate limit và chi phí tích lũy được lưu trong Redis. Instance
FastAPI không giữ dữ liệu cần chia sẻ trong RAM, nên request tiếp theo có thể đến instance
khác mà vẫn thấy cùng state.

```mermaid
flowchart TB
    LB[Load balancer] --> A[Agent instance A]
    LB --> B[Agent instance B]
    A --> R[(Redis)]
    B --> R
```

Khi Render gửi `SIGTERM`, instance chuyển sang trạng thái chưa ready, ngừng nhận request
mới, chờ request đang chạy kết thúc rồi mới thoát. Đây là nền tảng của rolling deployment
không làm rơi request.

### Bước 6 — Khai báo hạ tầng Render

`render.yaml` là bản mô tả deployment có thể review và tái tạo:

- Web service `day12-agent`, runtime Docker.
- Health check path `/health`.
- Render Key Value `day12-redis`.
- `REDIS_URL` được nối từ connection string của Key Value.
- Secret dùng `sync: false`; cấu hình không nhạy cảm có giá trị rõ ràng.

Luồng triển khai thực tế:

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant Git as GitHub
    participant Render
    participant App as Web service
    participant Redis as Key Value

    Dev->>Git: git push main
    Git-->>Render: thông báo revision mới
    Render->>Render: đọc render.yaml
    Render->>Render: build Docker image
    Render->>Redis: tạo/kết nối Key Value
    Render->>App: inject env và secret
    Render->>App: start container trên $PORT
    Render->>App: GET /health
    App-->>Render: 200 healthy
    Render-->>Dev: deployment live
```

## 4. Các checkpoint và ý nghĩa

| Checkpoint | Phần triển khai | Kết quả cần đạt |
|---|---|---|
| CP0 | Môi trường | Clone đúng repo, cài dependency, chạy được test |
| CP1 | 12-Factor và observability | Env config, fail fast, `/health`, JSON log |
| CP2 | Containerization | Multi-stage image, non-root, Compose hoạt động |
| CP3 | Production guardrails | Auth, rate limit, cost guard dùng Redis |
| CP4 | Scaling và reliability | Stateless, `/ready`, SIGTERM và graceful shutdown |
| CP5 | Cloud deployment | Render build thành công, URL public và Redis kết nối |

Các checkpoint tạo thành một chuỗi phụ thuộc. Ví dụ, CP5 không chỉ là bấm Deploy: nó dùng
image của CP2, config của CP1, Redis của CP3–CP4 và probe của CP1–CP4.

## 5. Cấu trúc file theo trách nhiệm deployment

| File/thư mục | Trách nhiệm |
|---|---|
| `app/config.py` | Đọc env và kiểm tra cấu hình lúc startup |
| `app/main.py` | API, health/readiness và thứ tự guardrails |
| `app/logging_utils.py` | Structured logging |
| `app/auth.py` | Xác thực `X-API-Key` |
| `app/rate_limiter.py` | Rate limit dùng Redis |
| `app/cost_guard.py` | Theo dõi và chặn vượt ngân sách |
| `app/store.py` | State dùng chung giữa các instance |
| `app/lifecycle.py` | Startup, readiness và graceful shutdown |
| `Dockerfile` | Runtime image |
| `docker-compose.yml` | Môi trường nhiều service trên local |
| `render.yaml` | Blueprint production |
| `tests/` | Quality gate trước khi deploy |
| `screenshots/` | Bằng chứng deployment |

## 6. Chạy và kiểm tra ở local

### Chạy trực tiếp bằng Python

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
pytest tests -q
uvicorn app.main:app --host 0.0.0.0 --port 8012
```

Cổng `8012` được dùng khi chạy thủ công để không xung đột với service khác đang dùng
`8000`. Trên Render, ứng dụng phải bind vào biến `$PORT` do nền tảng cấp.

### Chạy bằng Compose

```powershell
docker compose build
docker compose up -d
docker compose ps
docker compose logs agent
```

### Smoke test

```powershell
Invoke-RestMethod http://localhost:8012/health
Invoke-RestMethod http://localhost:8012/ready
Invoke-RestMethod http://localhost:8012/capabilities
```

Với endpoint cần auth:

```powershell
$headers = @{ "X-API-Key" = "<AGENT_API_KEY>" }
$body = @{ question = "Giải thích readiness khi deploy" } | ConvertTo-Json
Invoke-RestMethod http://localhost:8012/ask -Method Post -Headers $headers `
  -ContentType "application/json" -Body $body
```

## 7. Deploy lên Render

1. Push commit đã qua test lên nhánh `main`.
2. Trong Render chọn **New → Blueprint** và kết nối đúng repository.
3. Chọn branch `main`; Blueprint Path để `render.yaml`.
4. Nhập các secret mà giao diện yêu cầu, tối thiểu `AGENT_API_KEY` và
   `GROQ_API_KEY` nếu bật provider Groq.
5. Nhập `TAVILY_API_KEY` và `FIRECRAWL_API_KEY` nếu bật phần web retrieval mở rộng.
6. Chọn **Deploy Blueprint** và theo dõi build log.
7. Khi deploy xanh, kiểm tra `/health`, `/ready`, trang `/docs` và một request `/ask`.
8. Xác nhận dashboard hiển thị web service online và Redis connected.

Không đưa nội dung secret từ `.env` lên GitHub. Nếu nghi ngờ key đã lộ, revoke/rotate key
ở nhà cung cấp và cập nhật Render ngay.

## 8. Chẩn đoán lỗi deployment

| Triệu chứng | Kiểm tra đầu tiên | Nguyên nhân thường gặp |
|---|---|---|
| Build failed | Build log và Dockerfile | Dependency hoặc đường dẫn copy sai |
| Service không bind port | Start log | Hard-code port thay vì dùng `$PORT` |
| `/health` lỗi | Process log | App crash hoặc thiếu env bắt buộc |
| `/health` xanh, `/ready` đỏ | Redis và lifecycle | Redis URL sai hoặc dependency chưa sẵn sàng |
| `/ask` trả 401 | Header request | Thiếu/sai `X-API-Key` |
| `/ask` trả 429 | Rate-limit state | Gọi quá nhanh trong cửa sổ trượt |
| Chạy local nhưng lỗi cloud | Env và filesystem | Dựa vào `.env`, localhost hoặc file local |
| Deploy revision mới không đổi | Blueprint sync/build log | Sai branch, sai repo hoặc build cache |

Quy trình xử lý nên đi từ dưới lên: revision → build → startup → health → readiness →
endpoint nghiệp vụ → dependency bên ngoài. Không bắt đầu bằng việc sửa frontend khi
container còn chưa healthy.

## 9. Workload demo: chatbot và RAG

Phần AI là lớp mở rộng đặt trên hạ tầng đã hoàn thiện:

```mermaid
flowchart LR
    UI[Frontend] --> API[POST /ask]
    API --> GUARD[Auth + quota]
    GUARD --> LOCAL[Local Markdown retrieval]
    LOCAL --> ROUTE{Context đủ?}
    ROUTE -->|Đủ| LLM[Groq]
    ROUTE -->|Thiếu hoặc cần dữ liệu mới| WEB[Tavily / Firecrawl]
    WEB --> LLM
    LLM --> REDIS[(History + usage)]
    REDIS --> UI
```

Router không có nhánh riêng cho bất kỳ công nghệ cụ thể nào. Nó đo độ phủ của câu hỏi
trong tài liệu local. Nếu còn thuật ngữ quan trọng chưa được phủ, Tavily nhận một truy
vấn tổng quát ưu tiên tài liệu triển khai; kết quả được xếp hạng bằng dấu hiệu URL tài liệu
thay vì bảng ánh xạ tên công nghệ → domain. Vì vậy một công cụ mới vẫn đi qua đúng luồng.

Local RAG, web RAG và Groq giúp demo service có dependency, latency và chi phí thực tế.
Chúng không thay đổi mục tiêu chính của bài: đóng gói, cấu hình, bảo vệ, scale, deploy và
quan sát một web service trên cloud.

## 10. Trace dùng để trình bày luồng vận hành

Mỗi response `/ask` có operational trace gồm các bước như auth, rate limit, cost guard,
history, retrieval, LLM và persistence cùng thời gian xử lý. Đây là telemetry để debug,
không phải chain-of-thought và không chứa secret.

Khi demo trên lớp, nên trình bày theo thứ tự:

1. Mở Render Dashboard: web service và Redis đều hoạt động.
2. Mở `/health` và `/ready`, giải thích sự khác nhau.
3. Gửi một request hợp lệ và mở trace.
4. Cho thấy state/usage được lưu ngoài process.
5. Chỉ sau đó mới minh họa local RAG và web retrieval như workload mở rộng.

## 11. Tiêu chí hoàn thành

- Toàn bộ test bắt buộc chạy xanh trước khi push.
- Repo không chứa `.env` hoặc API key thật.
- Docker image chạy non-root và app bind đúng port.
- `/health` và `/ready` phản ánh đúng hai trạng thái khác nhau.
- Auth, rate limit và cost guard chạy trước workload tốn phí.
- State dùng chung nằm ở Redis, không nằm trong RAM của một instance.
- `render.yaml` tái tạo được web service và Key Value.
- Production URL hoạt động và có ảnh bằng chứng trong `screenshots/`.
- Người thực hiện giải thích được toàn bộ luồng từ commit đến request production.

Chi tiết yêu cầu từng checkpoint nằm trong [LAB_GUIDE.md](LAB_GUIDE.md); phần trả lời phản
ánh nằm trong [exercises.md](exercises.md).
