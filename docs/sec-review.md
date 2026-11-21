# Kiểm duyệt hồ sơ SEC — 2026-11-21

Đã triển khai workspace tại `/review`, migration `0005`, importer không dùng mạng và API quản trị `/api/v0/admin/sec/`. Dữ liệu thật nằm trong `rie-sec-review.db`, tách biệt với `rie-p4-demo.db` chứa fixture. Tên mode `production` trong schema chỉ phân biệt nguồn thật với synthetic, **không có nghĩa sản phẩm đã được phép phát hành**.

## Sử dụng cục bộ

Workspace đã được khởi động tại http://127.0.0.1:8886/review. Token operator ở `secrets/sec-review-access-token.txt`, được Git ignore, không gửi lên repository hoặc đặt trong URL. Chưa tạo tài khoản người duyệt thứ hai cho dữ liệu thật; cần cấp tài khoản riêng cho người thực sự thực hiện kiểm duyệt. Không dùng hai token do cùng một người điều khiển để giả lập đánh giá độc lập.

Nếu cần khởi động lại, từ thư mục chứa pyproject.toml:

```powershell
$env:DATABASE_URL='sqlite:///rie-sec-review.db'
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m uvicorn engine.api:app --host 127.0.0.1 --port 8886 --no-access-log
```

Để tạo một store mới, dùng đường dẫn database riêng, migrate và seed trước, sau đó:

```powershell
.venv/Scripts/python -m engine.sec_review source-cache/sec-review-2026-11-20 --initialize-review-store
```

Importer từ chối chuyển database synthetic sang nguồn thật. Import lại cùng capture không tạo bản trùng; đổi nội dung, URL, công ty hoặc thời điểm của capture cũ bị từ chối. Toàn bộ batch rollback khi có xung đột. Hồ sơ mới vẫn cần quyền sử dụng và kiểm tra độc lập.

Proxy public hiện chặn tất cả `/api/v0/admin/`; giữ nguyên quy tắc đó. Workspace này dùng loopback/operator ingress riêng, không mở cổng 8886 ra mạng công cộng. Khi triển khai operator ingress cần TLS và kiểm soát truy cập riêng.

## Quy trình

1. Mở hồ sơ, kiểm tra link SEC, ngày filing, thời điểm tải/nhập và hash. Văn bản được chuẩn hóa bằng `html-to-text-v1`, loại script/style/inline-XBRL hidden; không render HTML từ nguồn. Hash văn bản và HTML được lưu riêng. Bảng số liệu có thể mất cấu trúc khi chuyển sang text; người duyệt phải đối chiếu hồ sơ gốc.
2. Chọn đoạn nguồn, bấm **Dùng đoạn đang chọn**. Nhập tiêu đề trung tính, loại sự kiện, thời điểm công bố đã xác minh theo UTC, kỳ và cơ sở so sánh, điều chưa biết. Không tự đặt giờ công bố chỉ vì manifest có ngày filing.
3. Lưu bản nháp. Mỗi lần lưu tạo phiên bản bất biến, có author/timestamp; cùng Idempotency-Key trả lại cùng kết quả. Version cũ không bị ghi đè; sửa đồng thời bị báo xung đột.
4. Khi có bản trùng/sửa đổi, tham chiếu ID của bản trích xuất đã được duyệt thuộc capture trước, cùng canonical identity. Không cho tự liên kết, liên kết ngược thời gian hoặc liên kết với bản đã bị thay thế.
5. Người vận hành khác đăng nhập, đọc nội dung và kiểm tra độc lập. Duyệt yêu cầu ghi cơ sở quyền sử dụng, xác nhận định danh/đoạn trích/cơ sở so sánh. Có thể yêu cầu làm lại kèm lý do. Quyết định lưu bất biến; muốn sửa phải tạo phiên bản nháp mới.

Quyết định duyệt chỉ là **receipt trong khu vực kiểm duyệt**. Nó không tự phê duyệt graph, materiality, canonical events hay nguồn production; không tự tạo feed hoặc notification. Các API đọc hỗ trợ `as_of` và không lộ phiên bản/quyết định được ghi sau thời điểm đó.

## Giới hạn phiên bản này

- Một chuỗi bản trích xuất và một claim mỗi hồ sơ. Form tạo/sửa chỉ hỗ trợ định tính. API nhận claim định lượng có schema kỳ/đơn vị/basis nhưng người duyệt phải kiểm tra ý nghĩa; UI chỉ xem/duyệt bản định lượng, không âm thầm chuyển thành định tính.
- Không suy đoán sự kiện hay nhãn bằng LLM. Không tự gán giờ công bố, source rights hoặc materiality.
- 50 hồ sơ thật đã nhập, **0 draft thật, 0 review thật, 0 sự kiện được xuất bản** khi bàn giao. Browser test ghi dữ liệu vào database riêng bằng văn bản giả; với 50 hồ sơ thật chỉ đọc.
- Bước tiếp theo là adapter từ receipt đã duyệt sang canonical ingestion, với kiểm tra lại version/rights/identity/as-of trước khi đưa vào private feed. Cần thiết kế nguồn authoritative cho graph/materiality và gold labels; không dùng receipt staging để vượt các gate này.

Kiểm tra: `tests/test_sec_review.py`, `deploy/sec_review_browser.py`, các báo cáo `reports/sec-review-*`. PostgreSQL dùng database test dùng một lần; không đặt TEST_DATABASE_URL trỏ vào review/demo store.
