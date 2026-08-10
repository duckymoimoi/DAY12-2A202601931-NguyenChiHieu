# Thông Tin Deploy — Checkpoint 5

> Tài liệu này chỉ ghi **tên** biến môi trường. Giá trị secret được lưu trong
> Render Dashboard và file `.env` local không được commit.

## Thông Tin Học Viên

| Mục | Nội dung |
|-----|----------|
| Họ và tên | Nguyễn Chí Hiếu |
| Mã học viên | 2A202601931 |
| Repo | https://github.com/duckymoimoi/DAY12-2A202601931-NguyenChiHieu |

## Service

| Mục | Nội dung |
|-----|----------|
| Public URL | https://day12-agent-plt0.onrender.com |
| Platform | Render Blueprint |
| Ngày deploy | 2026-08-10 |

## Biến Môi Trường Đã Set Trên Cloud

| Biến | Đã set | Nguồn giá trị |
|------|--------|---------------|
| `PORT` | ✅ | Render tự gán cho web service |
| `AGENT_API_KEY` | ✅ | Secret nhập trong Render Dashboard (`sync: false`) |
| `REDIS_URL` | ✅ | Internal connection string của Render Key Value `day12-redis` |
| `RATE_LIMIT_PER_MINUTE` | ✅ | Blueprint, giá trị 10 |
| `MONTHLY_BUDGET_USD` | ✅ | Blueprint, giá trị 10.0 |
| `LOG_LEVEL` | ✅ | Blueprint, giá trị INFO |

## Lệnh Kiểm Tra

```bash
# 1. Liveness
curl -i https://day12-agent-plt0.onrender.com/health

# 2. Readiness và kết nối Redis
curl -i https://day12-agent-plt0.onrender.com/ready

# 3. Không có API key — mong đợi 401
curl -i -X POST https://day12-agent-plt0.onrender.com/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Hello"}'

# 4. Có API key — mong đợi 200
curl -i -X POST https://day12-agent-plt0.onrender.com/ask \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $AGENT_API_KEY" \
  -H "X-User-Id: sv-test" \
  -d '{"question":"Deploy là gì?"}'

# 5. Rate limit — 15 request cùng user
for i in $(seq 1 15); do
  curl -s -o /dev/null -w "%{http_code} " \
    -X POST https://day12-agent-plt0.onrender.com/ask \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $AGENT_API_KEY" \
    -H "X-User-Id: deployment-rate-check" \
    -d '{"question":"rate-limit-check"}'
done; echo
```

## Kết Quả Chạy Thật

```text
GET  /health -> 200 {"status":"ok","service":"day12-agent","version":"1.0.0"}
GET  /ready  -> 200 {"status":"ready","redis":true}
POST /ask không có API key -> 401
POST /ask có API key hợp lệ -> 200, có answer và user_id
Rate limit 15 request -> 200 200 200 200 200 200 200 200 200 200 429 429 429 429 429
```

## Ảnh Chụp Màn Hình

- `screenshots/dashboard.png`: trang resource/deploy của Render.
- `screenshots/health.png`: kết quả gọi public endpoint `/health`.
