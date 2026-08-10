# Cloud Deployment Playbook

## Twelve-Factor configuration

Tách cấu hình khỏi source code và truyền bằng biến môi trường. Secret như API key
không có giá trị mặc định; thiếu secret thì service nên fail fast khi khởi động.
Giữa local, staging và production, cùng một image được sử dụng nhưng nhận cấu hình
khác nhau.

## Docker multi-stage build

Multi-stage build dùng nhiều lệnh `FROM`. Stage build chứa compiler và công cụ đóng
gói; runtime stage chỉ copy artifact cần chạy. Cách này làm image nhỏ hơn, giảm bề
mặt tấn công và vẫn giữ Dockerfile dễ đọc. Nên copy file dependency trước source code
để tận dụng layer cache.

Nguồn chính thức: https://docs.docker.com/build/building/multi-stage/

## Health và readiness

Liveness trả lời tiến trình có còn sống không và phải rất nhẹ. Readiness kiểm tra
service có sẵn sàng nhận traffic, vì vậy được phép ping Redis hoặc dependency quan
trọng. Trên dự án này, `/health` không phụ thuộc Redis còn `/ready` có kiểm tra Redis.

Render chỉ chuyển traffic sang bản deploy mới sau khi health check thành công. Một
health endpoint trả mã 2xx hoặc 3xx được xem là khỏe; cấu hình sai có thể khiến deploy
bị hủy dù image build thành công.

Nguồn chính thức: https://render.com/docs/health-checks

## Secret trên Render

Trong `render.yaml`, dùng `sync: false` cho secret để Render yêu cầu nhập giá trị trên
dashboard. Không ghi secret thật vào Blueprint hoặc GitHub. Biến không bí mật như tên
model, timeout và feature flag có thể khai báo trực tiếp bằng `value`.

Nguồn chính thức: https://render.com/docs/configure-environment-variables

## Render Key Value

Web service nên kết nối Render Key Value bằng internal URL trong cùng region để giảm
độ trễ và không đưa Redis ra Internet. URL có scheme `redis://` hoặc `rediss://` và
được gắn vào `REDIS_URL` qua Blueprint.

Nguồn chính thức: https://render.com/docs/key-value
