# Hướng Dẫn Lab — K3 Ngày 12: Hạ Tầng Cloud & Deployment

> **Bài làm cá nhân.** Xem quy định và cách đặt tên repo ở [README.md](README.md).
>
> Mỗi block kết thúc bằng một checkpoint. Đến giờ thì chạy lệnh checkpoint,
> xanh hết mới sang block sau. Kẹt quá 10 phút → gọi Lab Coach và đi tiếp,
> đừng đứng lại một chỗ.

**Mục lục**

- [CP0 — Setup (9h00–9h20)](#cp0--setup-9h009h20)
- [Block 1 — 12-Factor Config, Health & Logging (9h20–10h00)](#block-1--12-factor-config-health--logging-9h2010h00)
- [Block 2 — Docker (10h00–10h45)](#block-2--docker-10h0010h45)
- [Block 3 — API Security (10h55–11h40)](#block-3--api-security-10h5511h40)
- [Block 4 — Scaling & Reliability (11h40–12h20)](#block-4--scaling--reliability-11h4012h20)
- [Block 5 — Cloud Deployment (12h20–12h50)](#block-5--cloud-deployment-12h2012h50)
- [Wrap-up (12h50–13h00)](#wrap-up-12h5013h00)
- [Phụ lục A — Lỗi thường gặp](#phụ-lục-a--lỗi-thường-gặp)
- [Phụ lục B — Bảng tra nhanh](#phụ-lục-b--bảng-tra-nhanh)

---

## CP0 — Setup (9h00–9h20)

### 1. Tạo repo đúng tên

Xem [README.md § Cách Đặt Tên Repository](README.md#-cách-đặt-tên-repository).
Làm bước này **trước tiên** — đổi tên repo giữa chừng dễ mất commit.

### 2. Môi trường

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
```

Sinh khóa riêng và dán vào `AGENT_API_KEY` trong `.env`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Bật Redis

```bash
docker compose up -d redis
docker compose ps                  # cột STATE phải là running/healthy
```

Chưa có Docker? Đặt `REDIS_URL=fake://` trong `.env` để làm tạm, nhưng nhớ cài
Docker trước Block 2.

### ✅ Checkpoint 0

```bash
pytest tests/ -v -m "not docker"
```

**Kết quả mong đợi: hầu hết test RỚT.** Đó là đúng — bạn chưa viết code nào.
Điều cần xác nhận là pytest *chạy được* và bạn *đọc được* thông báo lỗi. Nếu
thấy `ModuleNotFoundError` hoặc `ImportError`, môi trường chưa cài xong.

---

## Block 1 — 12-Factor Config, Health & Logging (9h20–10h00)

### Vấn đề

Ba dòng code sau trông vô hại trên laptop và là thảm họa trên production:

```python
API_KEY = "sk-proj-abc123"          # ai clone repo cũng có khóa của bạn
app.run(port=8000, debug=True)      # cloud gán cổng khác; debug=True lộ source
print(f"user {uid} hỏi {question}") # log không lọc được, không cảnh báo được
```

**12-Factor App** trả lời bằng một nguyên tắc: *code là thứ giống nhau ở mọi
môi trường, config là thứ khác nhau — nên config phải nằm ngoài code.*
Cùng một image chạy ở laptop, staging và production, chỉ khác biến môi trường.

### Việc cần làm

#### 1.1 — `app/config.py`

Khai báo 6 trường trong class `Settings`. Bảng đầy đủ nằm trong docstring của
file. Điểm quan trọng nhất: **`agent_api_key` không có giá trị mặc định.**

```python
port: int = 8000              # có mặc định — không phải secret
agent_api_key: str            # KHÔNG mặc định — thiếu là app chết ngay
```

Vì sao? Mặc định nghĩa là app vẫn khởi động khi bạn quên set secret trên cloud.
Nó chạy, trả lời request, và bạn chỉ biết có chuyện khi nhìn hóa đơn. Không
mặc định = lỗi hiện ra lúc deploy, khi bạn còn đang nhìn màn hình.

pydantic-settings tự ánh xạ tên trường sang biến môi trường viết hoa:
`agent_api_key` ← `AGENT_API_KEY`.

#### 1.2 — `app/logging_utils.py`

Cài `log_event()` sao cho mỗi lần gọi in ra **một dòng JSON**:

```json
{"event": "ask_completed", "level": "info", "timestamp": "2026-08-01T09:30:00+00:00", "user_id": "sv01", "cost_usd": 0.0001}
```

Một dòng — không `indent`. Cloud gom log theo dòng; JSON xuống dòng là một log
bị vỡ thành nhiều mảnh vô nghĩa.

Có định dạng này rồi thì bạn hỏi được những câu mà `print()` không trả lời nổi:
*"user nào tiêu nhiều tiền nhất hôm nay?"*, *"tỷ lệ lỗi 5 phút qua là bao nhiêu?"*

#### 1.3 — `/health` trong `app/main.py`

```
GET /health  →  200  {"status": "ok", "service": ..., "version": ...}
```

Đang tắt dần (`lifecycle.shutting_down`) → `503 {"status": "shutting_down"}`.
Phần 503 thuộc CP4, nhưng viết luôn bây giờ cũng được.

**Quy tắc: `/health` không được chạm vào Redis, database hay bất cứ dependency
nào.** Nó chỉ trả lời "process này có cần restart không?". Nếu nó phụ thuộc
Redis, Redis nấc một cái là orchestrator restart toàn bộ container — biến sự cố
nhỏ thành sự cố lớn. (Endpoint kiểm tra dependency là `/ready`, làm ở CP4.)

### Thử chạy

```bash
uvicorn app.main:app --reload --port 8000
curl -i http://localhost:8000/health
```

### ✅ Checkpoint 1 (10h00)

```bash
pytest tests/test_cp1.py -v
```

<details>
<summary>Kẹt? Vài gợi ý</summary>

- `ValidationError` khi khởi động: `.env` thiếu `AGENT_API_KEY`
- Test `test_log_ra_stdout_dung_mot_dong` rớt: bạn đang dùng `json.dumps(..., indent=2)`
- Test `test_health_khong_phu_thuoc_dependency_nao` rớt: hàm `health()` của bạn
  đang nhận tham số `Depends(...)` — bỏ đi
- Tiếng Việt trong log bị thành `ạ`: thêm `ensure_ascii=False`

</details>

---

## Block 2 — Docker (10h00–10h45)

### Vấn đề

"Máy tôi chạy được" — vì máy bạn có Python 3.11, máy server có 3.9; máy bạn có
`libpq`, server không. Docker đóng gói *cả môi trường* vào một image: cùng một
image thì chạy giống nhau ở mọi nơi.

Nhưng image sai cách cũng gây họa: image 1.2GB làm deploy chậm 5 phút mỗi lần;
container chạy root biến một lỗ hổng nhỏ thành quyền cao trên host; không có
`.dockerignore` thì `.env` của bạn nằm luôn trong image gửi lên registry.

### Việc cần làm

File `Dockerfile` hiện tại chạy được nhưng vi phạm gần hết các nguyên tắc. Sửa
lại theo 6 yêu cầu ghi trong chính file đó.

#### 2.1 — Multi-stage build

```dockerfile
FROM python:3.11-slim AS builder
# ... cài dependency ở đây (có thể cần compiler)

FROM python:3.11-slim AS runtime
COPY --from=builder /install /usr/local
# ... chỉ copy KẾT QUẢ sang, không mang theo compiler
```

Stage `builder` được phép nặng: nó cài `build-essential`, biên dịch, rồi bị vứt
đi. Chỉ stage cuối trở thành image. Đây là cách image tụt từ ~1GB xuống ~200MB.

#### 2.2 — Thứ tự lệnh quyết định tốc độ build

```dockerfile
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt
COPY app ./app                    # code copy SAU
```

Docker cache theo từng layer và huỷ cache từ layer đầu tiên thay đổi trở đi.
Đặt `COPY . .` lên trước `pip install` nghĩa là mỗi lần sửa một dấu phẩy trong
code, Docker cài lại toàn bộ thư viện.

#### 2.3 — Không chạy bằng root

```dockerfile
RUN useradd --create-home --uid 10001 appuser
USER appuser
```

#### 2.4 — HEALTHCHECK và PORT

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health').read()" || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

`0.0.0.0` chứ không phải `127.0.0.1`: bind vào localhost thì bên ngoài container
không gọi vào được. `${PORT:-8000}` vì Railway/Render/Cloud Run tự gán cổng.

#### 2.5 — `.dockerignore`

Bổ sung tối thiểu: `.env`, `__pycache__`, `.git`, `.venv`. Nhớ giữ lại những
thứ image **cần** (`app`, `utils`, `requirements.txt`) — ignore nhầm thì build
xong app không chạy.

#### 2.6 — `docker-compose.yml`

Thêm service `agent`: build từ Dockerfile, mở cổng 8000, `depends_on: redis`,
có healthcheck, và:

```yaml
environment:
  AGENT_API_KEY: ${AGENT_API_KEY}      # đọc từ .env, KHÔNG viết thẳng khóa
  REDIS_URL: redis://redis:6379/0      # `redis` là tên service = hostname
```

`localhost` bên trong container là chính container đó, không phải máy bạn —
đây là lỗi phổ biến nhất khi mới dùng compose.

### Thử chạy

```bash
docker build -t day12-agent:prod .
docker images day12-agent:prod          # ghi lại dung lượng cho câu 3 exercises

docker compose up -d
curl http://localhost:8000/health
docker compose logs agent
```

### ✅ Checkpoint 2 (10h45)

```bash
pytest tests/test_cp2.py -v
```

Các test build image thật mất vài phút. Muốn kiểm tra nhanh phần cấu trúc:

```bash
pytest tests/test_cp2.py -v -m "not docker"
```

<details>
<summary>Kẹt? Vài gợi ý</summary>

- `failed to compute checksum ... not found`: bạn `COPY` một thư mục đang bị
  `.dockerignore` loại trừ
- Image vẫn hơn 500MB: kiểm tra stage runtime có phải `slim` không, và bạn có
  thật sự `COPY --from=builder` thay vì cài lại dependency ở stage cuối
- Container start rồi tắt ngay: `docker compose logs agent` — thường là thiếu
  biến môi trường nên `Settings` ném `ValidationError`
- `Connection refused` khi curl: uvicorn đang bind `127.0.0.1`, đổi sang `0.0.0.0`

</details>

---

## Block 3 — API Security (10h55–11h40)

### Vấn đề

Bạn vừa có một URL công khai. Nó cũng công khai với các bot quét Internet —
chúng tìm thấy endpoint mới trong vòng vài giờ. Không có lớp bảo vệ, mỗi request
của người lạ là một lần bạn trả tiền cho nhà cung cấp LLM.

Ba lớp, ba câu hỏi khác nhau:

| Lớp | Câu hỏi | Mã lỗi |
|-----|---------|--------|
| Authentication | Bạn là ai? | 401 |
| Rate limiting | Bạn gọi có quá nhanh không? | 429 |
| Cost guard | Bạn đã tiêu hết ngân sách chưa? | 402 |

### Việc cần làm

#### 3.1 — `app/auth.py`

Kiểm tra header `X-API-Key`, trả về `user_id` (lấy từ `X-User-Id`, mặc định
`ANONYMOUS_USER`).

**So sánh khóa bằng `secrets.compare_digest`, không dùng `==`.** Toán tử `==`
dừng ngay tại ký tự đầu tiên khác nhau, nên thời gian trả lời rò rỉ thông tin:
đoán đúng ký tự đầu thì phản hồi chậm hơn một chút. Với đủ số lần đo, kẻ tấn
công dò ra khóa từng ký tự một. `compare_digest` luôn chạy hết chuỗi.

#### 3.2 — `app/rate_limiter.py`

Sliding window bằng Redis Sorted Set, score = timestamp:

```
zremrangebyscore(key, 0, now - 60)   # vứt các request đã ra khỏi cửa sổ
zcard(key)                           # đếm số còn lại
zadd(key, {member_duy_nhat: now})    # ghi nhận request này
expire(key, 60)                      # key tự dọn
```

Hai chi tiết dễ sai:
- **Kiểm tra trước, ghi nhận sau.** Ghi trước rồi đếm sẽ chặn nhầm ngay ở
  request thứ `limit`.
- **Member phải duy nhất** (`f"{now}:{uuid4().hex}"`). Hai request cùng
  timestamp mà trùng member thì ZSET chỉ giữ một, bạn đếm thiếu.

Vì sao không đếm theo phút đồng hồ cho đơn giản? Với hạn mức 10/phút, người
dùng gửi 10 request lúc 10:00:59 và 10 request lúc 10:01:01 — 20 request trong
2 giây, vẫn "đúng luật". Cửa sổ trượt không có kẽ hở đó.

#### 3.3 — `app/cost_guard.py`

`spent()` đọc tổng chi tiêu tháng, `check()` chặn khi vượt, `record()` cộng dồn.
Key theo `cost:<user>:<YYYY-MM>` nên sang tháng là tự reset.

Rate limit và cost guard **không thay thế nhau**: 10 request/phút nghe có vẻ an
toàn, nhưng mỗi request 50.000 token thì ngân sách bay trong vài phút.

#### 3.4 — `/ask` trong `app/main.py`

Ghép lại, đúng thứ tự:

```
verify_api_key (dependency)  →  limiter.check  →  guard.check
    →  get_history  →  ask_llm  →  append × 2  →  guard.record  →  log_event
```

Chặn **trước** khi gọi LLM. Chặn sau thì bạn vừa mất tiền vừa trả lỗi cho user.

### Thử chạy

```bash
# Không key → 401
curl -i -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" -d '{"question":"Hello"}'

# Có key → 200
curl -i -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $AGENT_API_KEY" -H "X-User-Id: sv01" \
  -d '{"question":"Docker là gì?"}'

# Gọi 15 lần → những lần cuối phải 429
for i in $(seq 1 15); do
  curl -s -o /dev/null -w "%{http_code} " -X POST http://localhost:8000/ask \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $AGENT_API_KEY" -H "X-User-Id: sv01" \
    -d '{"question":"test"}'
done; echo
```

### ✅ Checkpoint 3 (11h40)

```bash
pytest tests/test_cp3.py -v
```

<details>
<summary>Kẹt? Vài gợi ý</summary>

- 429 xuất hiện sớm hơn một nhịp: bạn `zadd` trước khi `zcard`
- `test_cua_so_truot_qua_thi_duoc_goi_lai` rớt: chưa `zremrangebyscore`, hoặc
  bỏ qua tham số `now` mà dùng thẳng `time.time()`
- `spent()` ném `TypeError`: Redis trả `None` khi chưa có key — trả `0.0`
- `/ask` trả 500: chạy `pytest tests/test_cp3.py -x --tb=short` để thấy dòng lỗi

</details>

---

## Block 4 — Scaling & Reliability (11h40–12h20)

### Vấn đề

Một instance không đủ, và instance nào cũng có thể chết bất cứ lúc nào — cloud
restart container để vá lỗi, dời máy, hoặc vì bạn deploy bản mới. Hệ thống phải
chịu được điều đó mà user không nhận ra.

### Việc cần làm

#### 4.1 — `app/store.py`: state ra khỏi process

```python
#  Sai — mỗi container một dict riêng
conversation_history = {}

#  Đúng — mọi container cùng nhìn một Redis
self.client.rpush(f"history:{user_id}", ...)
```

Với 3 instance sau load balancer, câu 1 của user vào container A, câu 2 vào
container B. Nếu lịch sử nằm trong RAM của A thì B không biết gì — agent "mất
trí nhớ" ngẫu nhiên. Đó là lý do stateless không phải tùy chọn.

Hai chi tiết bắt buộc:
- `ltrim` giữ tối đa `HISTORY_MAX_MESSAGES` message gần nhất — prompt dài vô hạn
  = tiền token vô hạn
- `expire` để hội thoại cũ tự hết hạn — không thì Redis đầy dần đến khi sập

`ping()` phải nuốt mọi exception và trả `False`. Nó dùng cho `/ready`; một
exception thoát ra sẽ biến readiness probe thành lỗi 500.

#### 4.2 — `/ready`

```
Redis sống  →  200 {"status": "ready", "redis": true}
Redis chết  →  503 {"status": "not ready", "redis": false}
Đang tắt    →  503 {"status": "shutting_down"}
```

Khác `/health` ở đúng một điểm cốt lõi:

| | `/health` (liveness) | `/ready` (readiness) |
|---|---|---|
| Câu hỏi | Process còn sống không? | Nhận traffic được chưa? |
| Kiểm tra dependency | **Không** | **Có** |
| Trả 503 thì sao | Orchestrator **restart** container | LB **ngừng gửi** request, không restart |

Gộp hai cái làm một là lỗi kinh điển: Redis mất kết nối 30 giây → cả 3 container
đều báo unhealthy → orchestrator restart cả 3 cùng lúc → khi Redis quay lại thì
không còn container nào phục vụ. Sự cố nhỏ thành sự cố toàn hệ thống.

#### 4.3 — `app/lifecycle.py`: graceful shutdown

Khi bạn deploy bản mới, platform gửi **SIGTERM** rồi đợi (thường 10–30 giây)
trước khi SIGKILL. App bỏ qua SIGTERM = mọi request đang xử lý dở bị cắt giữa
chừng = user thấy 502 mỗi lần bạn deploy.

```python
def install(self):
    for sig in (signal.SIGTERM, signal.SIGINT):
        self._previous[sig] = signal.getsignal(sig)   # nhớ handler cũ
        signal.signal(sig, self.request_shutdown)     # rồi mới ghi đè

def request_shutdown(self, signum=None, frame=None):
    self.shutting_down = True                         # chỉ bật cờ
    previous = self._previous.get(signum)
    if callable(previous):
        previous(signum, frame)                       # nhường lại cho uvicorn
```

Handler chạy xen giữa bytecode nên chỉ được làm việc rất nhẹ. Bật cờ → `/health`
trả 503 → load balancer rút instance khỏi vòng xoay → uvicorn xử lý nốt request
đang chạy rồi thoát.

**Cái bẫy ở đây:** mỗi tín hiệu chỉ có **một** handler. Đăng ký handler của mình
là ghi đè handler của uvicorn — thứ chịu trách nhiệm thật sự cho việc dừng
server. Quên gọi lại nó thì app bật cờ "đang tắt" rồi chạy tiếp mãi mãi, cho tới
khi orchestrator hết kiên nhẫn và SIGKILL. Bạn viết code graceful shutdown để
rồi bị kill cứng — tệ hơn là không viết gì.

### Thử chạy

```bash
docker compose up -d --scale agent=3
docker compose ps                      # 3 container agent

# Gọi nhiều lần với cùng user — history_length phải TĂNG DẦN dù đổi container
for i in $(seq 1 5); do
  curl -s -X POST http://localhost:8000/ask \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $AGENT_API_KEY" -H "X-User-Id: sv01" \
    -d '{"question":"lượt '$i'"}' | python -c "import json,sys; print(json.load(sys.stdin)['history_length'])"
done
```

Muốn xem load balancing thật thì bật thêm service `nginx` (cấu hình đã có sẵn ở
`nginx/nginx.conf`) và gọi qua cổng 80 — phần điểm cộng.

### ✅ Checkpoint 4 (12h20)

```bash
pytest tests/test_cp4.py -v
```

<details>
<summary>Kẹt? Vài gợi ý</summary>

- `test_cat_bot_lich_su_qua_dai` rớt: `ltrim(key, -N, -1)` giữ N phần tử **cuối**
  (mới nhất). `ltrim(key, 0, N-1)` giữ nhầm phần cũ nhất.
- `test_dang_ky_handler...` rớt: bạn truyền `self.request_shutdown()` (đã gọi)
  thay vì `self.request_shutdown` (tham chiếu hàm)
- `test_khong_co_bien_toan_cuc_giu_state` rớt: còn một dict toàn cục trong
  `main.py` hoặc `store.py` — xóa và chuyển sang Redis
- `/ready` trả 200 dù Redis chết: bạn quên kiểm tra giá trị trả về của `ping()`

</details>

---

## Block 5 — Cloud Deployment (12h20–12h50)

### Chọn platform

| Platform | Độ khó | Free tier | Redis kèm theo |
|----------|--------|-----------|----------------|
| **Railway** | ⭐ | $5 credit dùng thử | Có, thêm 1 click |
| **Render** | ⭐⭐ | 750 giờ/tháng | Có (Key Value) |
| Cloud Run | ⭐⭐⭐ | 2 triệu request/tháng | Không — cần Memorystore/Upstash |

Chọn Railway nếu bạn muốn xong nhanh. Cả hai đều đọc `Dockerfile` bạn vừa viết.

### Đường Railway

```bash
npm i -g @railway/cli
railway login
railway init                       # đặt tên project
railway add --database redis       # tạo Redis, tự sinh biến REDIS_URL

railway variables --set AGENT_API_KEY=<khóa của bạn> \
                  --set RATE_LIMIT_PER_MINUTE=10 \
                  --set MONTHLY_BUDGET_USD=10.0 \
                  --set LOG_LEVEL=INFO

railway up                         # build từ Dockerfile và deploy
railway domain                     # sinh URL công khai
railway logs                       # xem log khi có sự cố
```

Kiểm tra biến `REDIS_URL` đã được gắn vào service agent chưa (dashboard →
service → Variables). Railway tự set `PORT` — đừng ghi đè.

### Đường Render

1. Push repo lên GitHub (repo đúng tên `DAY12-...`)
2. [render.com](https://render.com) → **New** → **Blueprint** → chọn repo
3. Render đọc `render.yaml` có sẵn, tạo cả web service lẫn Redis
4. Điền `AGENT_API_KEY` khi Render hỏi (khai báo `sync: false` nghĩa là Render
   không lấy giá trị từ repo — đúng như vậy, secret không nằm trong repo)
5. **Create** và chờ build

### Kiểm tra bản deploy

```bash
URL=https://<domain-cua-ban>

curl -i $URL/health          # 200 {"status":"ok"}
curl -i $URL/ready           # 200 {"status":"ready"} ← chứng minh đã nối Redis
curl -i -X POST $URL/ask -H "Content-Type: application/json" \
  -d '{"question":"Hello"}'  # 401 — không có key thì không được vào
```

`/ready` trả 503 gần như luôn có nghĩa là `REDIS_URL` trên cloud sai hoặc chưa
tạo Redis.

### Điền `DEPLOYMENT.md`

Mở [DEPLOYMENT.md](DEPLOYMENT.md), điền Public URL, platform, danh sách biến môi
trường, và dán output các lệnh trên. Chụp màn hình dashboard vào `screenshots/`.

**Chỉ ghi TÊN biến, không dán giá trị `AGENT_API_KEY`.** Repo công khai, dán vào
là mất khóa — và test CP5 sẽ báo lỗi đúng chỗ đó.

Muốn test luôn cả đường có xác thực (điểm cộng): thêm `DEPLOY_API_KEY=<khóa>`
vào `.env` ở máy bạn (file này không được commit).

### Không deploy được?

Đăng ký thất bại, không có thẻ, mạng chặn — vẫn nộp được bài:

1. `LOCAL_FALLBACK=true` trong `.env`
2. `docker compose up -d` và kiểm tra `docker compose ps`
3. Chụp màn hình vào `screenshots/`
4. Ghi lý do vào cuối `DEPLOYMENT.md`

CP5 khi đó tối đa 9/15 điểm.

### ✅ Checkpoint 5 (12h50)

```bash
pytest tests/test_cp5.py -v
```

<details>
<summary>Kẹt? Vài gợi ý</summary>

- Build trên cloud fail còn ở máy thì được: thường do `.dockerignore` loại trừ
  file mà build cần, hoặc bạn quên commit file nào đó
- Deploy xong nhưng health check timeout: app đang bind `127.0.0.1` hoặc cố định
  cổng 8000 thay vì đọc `$PORT`
- Request đầu tiên rất chậm rồi các request sau nhanh: free tier "ngủ đông" khi
  không có traffic — bình thường
- `/ready` 503: kiểm tra `REDIS_URL` trong dashboard

</details>

---


---

## Wrap-up (12h50–13h00)

```bash
# 1. Trả lời 10 câu trong exercises.md

# 2. Chấm thử
python grade.py

# 3. Kiểm tra .env không bị commit
git ls-files | grep "^\.env$" && echo "NGUY HIỂM: .env đang bị theo dõi!"

# 4. Nộp
git add -A
git commit -m "Hoàn thành lab Day 12"
git push
```

Nộp **link repository** lên LMS. Đối chiếu lại [danh sách kiểm tra](README.md#danh-sách-kiểm-tra-trước-khi-nộp).

---

## Phụ Lục A — Lỗi Thường Gặp

| Triệu chứng | Nguyên nhân thường gặp | Cách xử lý |
|-------------|------------------------|------------|
| `ValidationError: agent_api_key Field required` | chưa có `.env` hoặc thiếu biến | `cp .env.example .env` rồi điền khóa |
| `ConnectionError: Error 61 connecting to localhost:6379` | Redis chưa chạy | `docker compose up -d redis` hoặc `REDIS_URL=fake://` |
| `ModuleNotFoundError: No module named 'app'` | chạy pytest từ thư mục con | chạy từ gốc repo |
| `curl: (7) Failed to connect` | uvicorn bind `127.0.0.1` trong container | đổi sang `--host 0.0.0.0` |
| Container start rồi tắt ngay | thiếu biến môi trường | `docker compose logs agent` |
| `docker build` không dùng cache | `COPY . .` đứng trước `pip install` | đảo thứ tự |
| Image > 500MB | build 1 stage, hoặc base image không slim | multi-stage + `python:3.11-slim` |
| 429 xuất hiện quá sớm | `zadd` trước `zcard` | kiểm tra trước, ghi nhận sau |
| `/ready` luôn 200 dù Redis chết | không dùng kết quả `ping()` | `if not store.ping(): return 503` |
| Deploy xong health check fail | app không đọc `$PORT` | `--port ${PORT:-8000}` |

## Phụ Lục B — Bảng Tra Nhanh

**pytest**
```bash
pytest tests/test_cp3.py -v            # một checkpoint
pytest tests/ -v -m "not docker"       # bỏ qua test build (nhanh hơn nhiều)
pytest tests/test_cp3.py -x --tb=short # dừng ở lỗi đầu tiên, xem traceback gọn
pytest tests/test_cp3.py -k rate       # chỉ chạy test có "rate" trong tên
```

**Docker**
```bash
docker build -t day12-agent:prod .
docker images day12-agent:prod                 # xem dung lượng
docker compose up -d --scale agent=3
docker compose logs -f agent
docker compose exec agent sh                   # vào trong container
docker compose down -v                         # dọn sạch, xóa cả volume
```

**Redis**
```bash
docker compose exec redis redis-cli KEYS '*'
docker compose exec redis redis-cli LRANGE history:sv01 0 -1
docker compose exec redis redis-cli GET cost:sv01:2026-08
docker compose exec redis redis-cli ZCARD ratelimit:sv01
```

**Mã trạng thái HTTP dùng trong lab**

| Mã | Ý nghĩa | Xuất hiện khi |
|----|---------|---------------|
| 200 | OK | mọi thứ ổn |
| 401 | Unauthorized | thiếu/sai API key |
| 402 | Payment Required | hết ngân sách tháng |
| 422 | Unprocessable Entity | body sai định dạng (pydantic bắt) |
| 429 | Too Many Requests | vượt rate limit |
| 503 | Service Unavailable | chưa ready, hoặc đang tắt dần |
