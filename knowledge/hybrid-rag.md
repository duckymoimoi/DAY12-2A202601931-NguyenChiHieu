# Hybrid RAG cho Cloud Deployment Copilot

## Hai tầng kiến thức

Local RAG tìm trong `README.md`, `LAB_GUIDE.md`, `DEPLOYMENT.md` và thư mục
`knowledge/`. Đây là nguồn ưu tiên cho câu hỏi về bài lab vì ổn định, nhanh và không
tốn API credit.

Web RAG được dùng khi câu hỏi cần thông tin mới hoặc local retrieval có độ liên quan
thấp. Ví dụ: region Render hiện hỗ trợ, model Groq còn hoạt động hay một lỗi mới của
Docker. Câu hỏi hoàn toàn ngoài cloud deployment không nên tự động tìm web.

## Vai trò Tavily

Tavily Search tìm một số ít trang liên quan và trả tiêu đề, URL cùng đoạn nội dung đã
chuẩn bị cho LLM. Dùng `search_depth=basic` và giới hạn kết quả để kiểm soát credit,
độ trễ và kích thước prompt.

Nguồn chính thức: https://docs.tavily.com/documentation/api-reference/introduction

## Vai trò Firecrawl

Firecrawl chỉ đọc sâu một trang tốt nhất khi snippet tìm kiếm chưa đủ. Endpoint scrape
v2 chuyển nội dung chính thành Markdown. URL phải là HTTP/HTTPS công khai; từ chối
localhost, loopback, link-local và private network để tránh SSRF.

Nguồn chính thức: https://docs.firecrawl.dev/api-reference/v2-introduction

## Chống prompt injection từ web

Nội dung web là dữ liệu không tin cậy. System prompt phải yêu cầu model không làm theo
chỉ dẫn nằm trong trang, không tiết lộ system prompt hoặc secret, và chỉ dùng nội dung
để lấy dữ kiện. Câu trả lời phải gắn `[1]`, `[2]` với danh sách URL nguồn để người dùng
có thể kiểm chứng.

## Khi nào cần vector database

Corpus vài file Markdown chưa cần embedding hoặc vector database. BM25/lexical search
nhanh, không tải model và giải thích được trong lớp. Chỉ chuyển sang semantic retrieval
khi corpus lớn, cách diễn đạt giữa câu hỏi và tài liệu khác nhau nhiều, hoặc đã đo được
recall của lexical search không đủ.
