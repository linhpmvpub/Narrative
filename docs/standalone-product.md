# Narrative — sản phẩm độc lập

Theo chỉ đạo mới của chủ dự án, sản phẩm không phụ thuộc vào repository Threadnote. Các tài liệu bàn giao gốc được giữ nguyên để đối chiếu; yêu cầu tích hợp Threadnote trong đó đã được thay thế bởi hướng phát triển độc lập này.

## Mở giao diện

Trong thư mục chứa `pyproject.toml`, với database demo đã khởi tạo:

```powershell
$env:DATABASE_URL='sqlite:///rie-p4-demo.db'
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m uvicorn engine.api:app --host 127.0.0.1 --port 8876 --no-access-log
```

Mở http://127.0.0.1:8876 và chọn **Xem bản demo tổng hợp**. Demo F021/N08 chỉ đọc, có nhãn dữ liệu tổng hợp và không phát thông báo thật. Dữ liệu nguồn và nội dung phân tích hiện giữ ngôn ngữ gốc; giao diện thao tác là tiếng Việt.

Tài khoản preview riêng tư đã được tạo cục bộ. Mã truy cập nằm trong `secrets/local-access-token.txt` (không được Git theo dõi), có hạn 30 ngày kể từ lúc cấp. Nhập mã vào giao diện để thao tác. Không gửi mã lên GitHub hoặc đặt trong URL. Trang chỉ giữ mã trong bộ nhớ; tải lại trang cần kết nối lại. Đây là cơ chế cấp tài khoản nội bộ, chưa có đăng ký công khai/khôi phục tài khoản.

Giao diện hỗ trợ theo dõi tối đa 3 cổ phiếu và 1 luận điểm, dòng sự kiện có nguồn và dấu vết đánh giá, bản sửa đổi, phản hồi riêng tư, chia sẻ/thu hồi chủ động; tạo, xem lại, xác nhận và theo dõi luận điểm riêng. API sửa đổi luận điểm đã có; giao diện chỉnh sửa phiên bản sẽ là bước tiếp theo. Theo dõi mới có thể chưa có sự kiện cho đến lần xử lý nguồn tiếp theo. Không có lịch chạy thu thập hay gửi thông báo tự động.

Tài khoản preview chứa dữ liệu thao tác kiểm thử. Nút demo công khai không đọc tài khoản này. Khởi tạo database mới, cấp tài khoản và replay xem `RUNBOOK.md`; bản triển khai Docker/TLS xem `docs/deployment-validation.md`. Chỉ dùng môi trường demo riêng biệt cho fixture.

## Kiểm tra giao diện

`deploy/browser_smoke.py` dùng Playwright trong `.audit-venv` và Chrome đã cài. Script cần server ở cổng 8876 và token của tài khoản thử nghiệm **mới, chưa có theo dõi/luận điểm** trong file trên. Script thực hiện thao tác ghi vào tài khoản đó; không chạy với tài khoản thật. Kết quả và ảnh desktop/mobile nằm trong `reports/`.

## Thứ tự phát triển tiếp

1. Màn hình kiểm duyệt 50 hồ sơ SEC đã triển khai ngày 2026-11-21; xem `docs/sec-review.md`. Cần người thực sự trích xuất và kiểm duyệt trước khi có sự kiện được phê duyệt.
2. Nối sự kiện đã duyệt vào feed riêng tư, giữ kiểm tra as-of, provenance và trạng thái chưa đủ bằng chứng. Không tự phê duyệt graph/materiality bằng nội dung nguồn.
3. Lập 50–100 sự kiện chuẩn có nhãn độc lập, chốt holdout theo thời gian và chạy B0/B1/V0; 50 hồ sơ không đồng nghĩa 50 sự kiện đã duyệt.
4. Bổ sung đăng nhập/khôi phục tài khoản, chỉnh sửa luận điểm và hạn mức theo tài khoản cho pilot nhiều người.
5. Docker Scout đã chạy ngày 2026-11-21; đã vá zlib và bỏ pip runtime, còn 56 findings (5 HIGH) chưa có fixed version trong báo cáo. Cần xử lý/đánh giá các rủi ro này trước production. Đẩy repository khi công cụ GitHub/remote khả dụng và chạy CI từ xa; sau đó mới chốt hạ tầng và đánh giá phát hành.

Thông báo thật vẫn tắt. Trạng thái phát hành production vẫn **NO_GO**.
