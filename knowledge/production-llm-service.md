# Production LLM Service

## Luồng request an toàn

Thứ tự xử lý nên là: xác thực API key, rate limit, kiểm tra ngân sách, lấy lịch sử,
truy xuất kiến thức, gọi LLM, lưu hội thoại, ghi nhận chi phí và log có cấu trúc.
Kiểm tra quota sau khi gọi model là quá muộn vì chi phí đã phát sinh.

## Provider và fallback

Provider được chọn bằng `LLM_PROVIDER`. `mock` giúp test deterministic và demo offline;
`groq` tạo câu trả lời thật. Nếu Groq tạm lỗi, `LLM_FALLBACK_TO_MOCK=true` giữ endpoint
hoạt động nhưng response phải ghi rõ `provider=mock` và `knowledge_mode=fallback` để
không khiến người dùng hiểu nhầm đó là câu trả lời từ model thật.

## Model mặc định

Dự án dùng `openai/gpt-oss-20b` trên Groq cho demo vì tốc độ và chi phí phù hợp.
Không hardcode API key. Groq cung cấp API tương thích OpenAI tại
`https://api.groq.com/openai/v1/chat/completions`.

Nguồn chính thức:

- https://console.groq.com/docs/openai
- https://console.groq.com/docs/models
- https://console.groq.com/docs/deprecations

## Token và cost guard

Token thực tế lấy từ trường `usage.prompt_tokens` và `usage.completion_tokens` trong
response provider. Chi phí được tính theo giá input/output cấu hình bằng biến môi
trường rồi cộng vào Redis theo user và tháng. Vì bảng giá có thể thay đổi, các mức giá
phải cấu hình được thay vì gắn cố định vào logic nghiệp vụ.

## Timeout và lỗi

Mọi request ra ngoài cần timeout. Thông báo lỗi không được chứa header Authorization,
API key hoặc toàn bộ response nhạy cảm. Khi provider lỗi, log mã trạng thái đã làm sạch
và trả fallback hoặc lỗi dịch vụ có kiểm soát.
