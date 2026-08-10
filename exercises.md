# Phiếu Phản Ánh — K3 Ngày 12

> **Bài làm cá nhân.** Trả lời bằng lời của chính bạn, dựa trên những gì bạn
> quan sát được khi chạy code — không sao chép đáp án của người khác.
>
> Cách trả lời: thay từng dòng trả lời mẫu bằng câu trả lời của bạn.
> `grade.py` đếm số câu đã trả lời (15 điểm cho 10 câu).
>
> Họ và tên: Nguyễn Chí Hiếu  Mã học viên: 2A202601931

---

### Câu 1 — Fail fast (CP1)

Trong `Settings`, `agent_api_key` không có giá trị mặc định nên app chết ngay
khi khởi động nếu thiếu biến môi trường. Hãy mô tả một tình huống cụ thể mà
việc "chết sớm" này cứu bạn, so với việc để mặc định `"changeme"`.

> Ví dụ khi deploy lên Render nhưng quên cấu hình `AGENT_API_KEY`, fail fast làm
> container dừng ngay và báo lỗi cấu hình. Nếu có khóa mặc định `"changeme"`,
> service vẫn public bình thường và người lạ có thể đoán khóa để gọi API, tiêu
> quota hoặc chi phí trước khi tôi phát hiện.

---

### Câu 2 — Log cho máy đọc (CP1)

Chạy service và gọi `/ask` vài lần. Dán một dòng log JSON bạn thu được, rồi
nêu **hai** việc bạn làm được với dòng log đó mà `print("đã trả lời xong")`
không làm được.

> Một log thực tế:
> `{"event":"ask_completed","level":"info","timestamp":"2026-08-10T03:03:10.990280+00:00","user_id":"local-smoke","tokens_in":3,"tokens_out":37,"cost_usd":0.00002265}`.
> Từ các trường JSON, tôi có thể lọc toàn bộ request theo `user_id` để điều tra
> và cộng `tokens`/`cost_usd` theo thời gian để tạo dashboard hoặc cảnh báo.
> Chuỗi `print("đã trả lời xong")` không có dữ liệu có cấu trúc để làm hai việc này.

---

### Câu 3 — Kích thước image (CP2)

Build cả hai phiên bản và ghi lại số đo thật:

```bash
docker build -f <Dockerfile-1-stage> -t agent:single .
docker build -t agent:multi .
docker images | grep agent
```

| Bản | Dung lượng |
|-----|-----------|
| 1 stage (bản đầu) | khoảng 1.1 GB |
| Multi-stage | 270 MB |

Giải thích: phần dung lượng chênh lệch đó là những gì?

> Bản đầu dùng image `python:3.11` đầy đủ và giữ toàn bộ môi trường cài đặt trong
> image cuối. Bản multi-stage dùng `python:3.11-slim`, chỉ chép thư viện runtime
> từ builder, không giữ cache pip, công cụ build và file không cần thiết như
> `.git`, `.env`, test hay virtualenv. Vì vậy image cuối nhỏ hơn đáng kể.

---

### Câu 4 — Thứ tự lệnh trong Dockerfile (CP2)

Sửa một ký tự trong `app/main.py` rồi build lại. Với Dockerfile của bạn, những
layer nào được dùng lại từ cache, layer nào phải chạy lại? Nếu bạn đặt
`COPY . .` lên trước `RUN pip install` thì kết quả khác thế nào?

> Khi chỉ sửa `app/main.py`, các layer base image, `COPY requirements.txt`, cài
> dependency trong builder và `COPY --from=builder` được dùng lại từ cache.
> Layer `COPY app` cùng các layer đứng sau nó phải chạy lại. Nếu đặt `COPY . .`
> trước `pip install`, mọi thay đổi source đều làm mất cache dependency và pip
> phải cài lại toàn bộ thư viện dù `requirements.txt` không đổi.

---

### Câu 5 — Vì sao không chạy bằng root (CP2)

Container mặc định chạy bằng root. Mô tả chuỗi sự kiện dẫn từ "một lỗ hổng
trong code Python của bạn" tới "kẻ tấn công có quyền cao trên máy host", và
lệnh `USER` cắt đứt chuỗi đó ở chỗ nào.

> Một lỗi thực thi mã từ xa có thể cho kẻ tấn công chạy lệnh trong container.
> Nếu process là root, họ có quyền root trong container và có thể lợi dụng volume
> nhạy cảm, capability dư thừa hoặc lỗ hổng kernel/container runtime để tác động
> tới host. `USER appuser` chuyển process sang UID thường trước khi chạy Uvicorn,
> nên mã bị chiếm quyền chỉ có đặc quyền hạn chế. Cách này giảm hậu quả, dù vẫn
> cần tránh mount Docker socket và cấp capability không cần thiết.

---

### Câu 6 — Cửa sổ trượt (CP3)

Rate limit của bạn dùng sliding window 60 giây. Nếu thay bằng cách đếm theo
phút đồng hồ (reset lúc giây 00), một người dùng có thể gửi tối đa bao nhiêu
request trong 2 giây liên tiếp khi hạn mức là 10/phút? Giải thích cách đạt được
con số đó.

> Tối đa 20 request: gửi 10 request ở cuối phút, ví dụ `10:00:59`, rồi gửi tiếp
> 10 request ngay sau lúc bộ đếm reset ở `10:01:00`. Sliding window luôn nhìn
> lại đúng 60 giây gần nhất nên không cho phép burst 20 request trong khoảng
> hai giây như cách đếm theo phút đồng hồ.

---

### Câu 7 — Rate limit và cost guard (CP3)

Hai cơ chế này khác nhau ở điểm nào? Cho một tình huống mà rate limit cho qua
nhưng cost guard phải chặn, và một tình huống ngược lại.

> Rate limit giới hạn số request trong một khoảng thời gian, còn cost guard giới
> hạn tổng tiền theo tháng. Một request rất dài có thể vẫn nằm trong hạn mức
> request/phút nhưng vượt ngân sách nên cost guard phải chặn. Ngược lại, nhiều
> request rất ngắn có tổng chi phí thấp vẫn có thể bị rate limit chặn vì gửi quá
> dồn dập, dù cost guard vẫn cho qua.

---

### Câu 8 — /health khác /ready (CP4)

Nếu gộp hai endpoint làm một và cho nó kiểm tra Redis, chuyện gì xảy ra với cụm
3 container khi Redis mất kết nối 30 giây? Trả lời theo đúng thứ tự sự kiện.

> Redis mất kết nối làm endpoint gộp trả 503 ở cả ba container. Orchestrator hiểu
> đây là lỗi liveness nên loại rồi restart cả ba, dù các process FastAPI vẫn sống.
> Trong lúc Redis chưa phục hồi, container mới tiếp tục fail health check và rơi
> vào vòng restart; toàn cụm mất khả năng phục vụ. Tách `/health` giúp process
> không bị restart, còn `/ready` chỉ yêu cầu load balancer tạm ngừng gửi traffic.

---

### Câu 9 — Stateless (CP4)

Chạy `docker compose up --scale agent=3` rồi gọi `/ask` nhiều lần với cùng một
`X-User-Id`. Quan sát `history_length` trong response. Nếu lịch sử được lưu
trong một dict Python thay vì Redis, bạn sẽ thấy con số đó thay đổi thế nào?

> Với Redis dùng chung, các request cùng `X-User-Id` thấy một lịch sử thống nhất;
> `history_length` tăng lần lượt 0, 2, 4, ... dù request vào replica nào. Nếu dùng
> dict Python, mỗi container có lịch sử riêng nên số có thể nhảy không đều như
> 0, 0, 2, 0 hoặc giảm khi request chuyển replica; restart container còn làm lịch
> sử của replica đó mất hoàn toàn.

---

### Câu 10 — Deploy thật (CP5)

Ghi lại **một** lỗi bạn gặp khi deploy lên cloud (build fail, health check
timeout, sai REDIS_URL, app không đọc `$PORT`...): thông báo lỗi là gì, bạn
tìm ra nguyên nhân bằng cách nào, và sửa ra sao?

> Lần deploy đầu, Render báo `Create web service day12-agent (deploy failed)` và
> health check không thể xanh. Tôi đối chiếu commit đang deploy với log/startup
> local và thấy `lifecycle.install()` cùng `/health` còn ném
> `NotImplementedError`, đồng thời Dockerfile cố định cổng 8000. Tôi cài đặt
> lifecycle và health endpoint, đổi lệnh chạy sang `${PORT:-8000}`, test bằng
> Docker Compose rồi push lại. Deployment sau đó thành công và `/health`,
> `/ready` đều trả 200 trên URL Render.
