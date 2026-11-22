# Phân tích26 ca không khớp và bản thử nghiệm ngôn ngữ v2.0.1

Ngày22/11/2026, đã đối chiếu toàn bộ132 ca văn bản với nhãn AI đã chốt của đợt204 ca. Kết quả và phiên bản thử nghiệm nằm trong `reports/language-error-audit.json`. Không gọi lại các agent để đổi nhãn theo thuật toán. Nhãn AI vẫn là tham chiếu tạm thời, không phải nhãn người thật hay chứng minh nhân quả.

## Vì sao26 ca holdout không khớp

| Nhóm | Số ca | Nhận định |
|---|---:|---|
| Dự báo, rủi ro hoặc quan hệ phụ thuộc tài chính |19|Bản v1 chỉ nhận các cụm nhân quả hẹp; tiêu chí agent còn bao gồm dự báo tài chính. Đây có phần là khác biệt phạm vi, không thể gọi toàn bộ là26 lỗi đã được chứng minh.|
| Giải thích kết quả đã xảy ra bị bỏ sót |6|Biến thể như reflected, drivers, thuế/tiền mặt và khoản trả trước cần xét trong đúng câu và kỳ.|
| Lý do kiểm toán bị hiểu thành nguyên nhân tài chính |1|Lý do cần xét đoán hoặc bằng chứng kiểm toán không giải thích nguyên nhân doanh thu tăng/giảm.|

Trong60 ca holdout chỉ có53 đoạn văn khác nhau sau chuẩn hóa; bộ development72 ca có59 đoạn khác nhau. Đoạn rủi ro lặp lại qua nhiều hồ sơ không tạo thêm bằng chứng độc lập. Báo cáo có cả mẫu số theo ca và theo văn bản duy nhất.

## Thay đổi đã triển khai

`engine/evaluation/language_candidate.py` cung cấp **financial-language-shadow-v2.0.1**. Bộ nhận diện xét từng câu và lưu offset, nguyên văn câu, nhãn, mã lý do. Nhờ đó có thể kiểm tra câu nào làm phát sinh nhận định, và phân biệt đoạn có cả kết quả đã xảy ra lẫn triển vọng tương lai.

Phạm vi mới bao gồm dự báo/quan hệ phụ thuộc tài chính ngay cả khi thiếu một cụm như “due to”; mở rộng các dạng diễn đạt kết quả thuế, tiền mặt và khoản người mua trả trước. Nó phân biệt yêu cầu công bố báo cáo với dự báo kinh doanh, coi rủi ro tồn kho là khả năng chứ không phải kết quả đã xảy ra, và không biến lý do thủ tục kiểm toán thành nguyên nhân biến động tài chính.

Đây vẫn là heuristic, chưa phải bộ phân tích ngữ nghĩa đầy đủ. Những câu mơ hồ, cơ chế tổng quát, phủ định phức tạp, thuật ngữ kế toán và liên kết giữa nhiều câu vẫn có thể bị phân loại sai.

| Tập đã được xem | Bản cũ khớp AI | Bản thử nghiệm khớp AI | Khớp trên văn bản duy nhất | Ca khớp cũ nhưng không khớp mới |
|---|---:|---:|---:|---:|
| Development |39/72|60/72|49/59|4|
| Holdout đã lộ cho phân tích |34/60|57/60|50/53|1|

Trên holdout cũ,24 ca chuyển sang khớp AI và1 ca chuyển sang không khớp. Còn3 ca không khớp tổng thể. Các tỷ lệ này **chỉ là đối chiếu hồi cứu với AI**, sau khi đã đọc dữ liệu và điều chỉnh quy tắc; tuyệt đối không gọi57/60 là chất lượng ngoài mẫu hoặc độ chính xác dự báo cổ phiếu.

**Chế độ triển khai: SHADOW_ONLY.** Không thay `engine.filing_evidence.parse`, không tính lại snapshot cũ, không thay dự đoán đã khóa, không nhập nhãn AI vào bảng nhãn người thật, không sửa graph/feed và không bật thông báo. Bản gốc vẫn được phục vụ cho đến khi có căn cứ cho thay đổi phiên bản một cách rõ ràng. API thẩm định chỉ bổ sung bảng chẩn đoán; annotator vẫn không thấy dự đoán hoặc nhãn người khác.

## Xem bằng chứng và chạy lại

Mở http://127.0.0.1:8888/adjudicate bằng tài khoản thẩm định hoặc quản trị hiện có. Mục phân tích hồi cứu hiển thị bản cũ/bản thử nghiệm, số ca giảm và mẫu số văn bản duy nhất. Gateway vẫn chặn trang quản trị này.

Chi tiết riêng nằm ở `source-cache/language-audit-v2.0.1/case-audit.json`: mỗi ca có nguồn, hash, nhãn cũ, nhãn AI/lý do, trace của bản thử nghiệm và nhóm bất đồng. Không commit tệp này vì có nguyên văn nguồn và nhãn theo ca. Prototype v2.0.0 và protocol cũ được giữ riêng dưới `source-cache/language-audit-v2/`; không dùng protocol cũ cho mã v2.0.1.

```powershell
.venv/Scripts/python -m engine.evaluation.language_audit
```

Lệnh kiểm tra nhãn/nguồn và hash phiếu thẩm định trước khi phân tích, không sửa dự đoán gốc. Báo cáo công khai chỉ chứa số liệu tổng hợp và hash truy vết.

## Đợt đánh giá mới đã chuẩn bị, chưa có kết quả

Protocol riêng `source-cache/language-audit-v2.0.1/prospective-protocol.json` khóa phiên bản, hash mã nguồn, thời điểm khóaUTC, toàn bộ hồ sơ/hash nguồn đã xem và chữ ký văn bản. Đầu vào đợt mới phải có `id`, `accession`, `source_sha256`, `text`, `available_at` có múi giờ và `filing_date` dạngYYYY-MM-DD.

```powershell
.venv/Scripts/python -m engine.evaluation.language_audit --screen-cases source-cache/new-language-cases.json
```

Bộ lọc từ chối hồ sơ/hash đã xem; hồ sơ nộp không sau ngày khóa; capture không sau thời điểm khóa hoặc nằm trong tương lai; thời gian thiếu/không hợp lệ; đoạn văn y hệt hoặc gần lặp lại (Jaccard của bộ ba từ>=0,8). Mã candidate thay đổi sau khi khóa cũng làm bộ lọc từ chối. Đã thử với204 ca cũ:0 ca đủ điều kiện.

Vượt qua bộ lọc chỉ có nghĩa đủ điều kiện đưa đi kiểm tra nguồn và gán nhãn mới. Nó không xác minh URL/hash với máy chủ nguồn, không nhập canonical event, không tạo gold và không tự cho phép triển khai. Sau khi kiểm tra nguồn, phải khóa dự đoán trước khi nhận nhãn, dùng đúng quy trình hai agent kín và thẩm định riêng; tiếp tục ghi rõAI_SIMULATED. Đưa cả ví dụ không có nhân quả, có điều kiện, đoạn không chứa từ khóa tài chính và các ca bộ trích xuất bỏ sót vào thiết kế lấy mẫu.

Hiện **chưa có đợt đánh giá trên hồ sơ sau thời điểm khóa**. Cần thu thập hồ sơ mới đáp ứng điều kiện, gán nhãn kín và báo cáo cả bất đồng, ca giảm chất lượng và trường hợp bị loại. Không tái sử dụng132 đoạn đã phân tích rồi gọi đó là kiểm thử mới. Nếu tiếp tục chỉnh candidate, tạo phiên bản/protocol mới trước khi thu thập nhãn; không thay hash trong protocol đã khóa.
