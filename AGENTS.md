# Hướng dẫn cho agent làm việc trong repository

Áp dụng cho toàn bộ repository. Đọc trước khi đề xuất hoặc thực hiện task; đây là dự án
Narrative đang phát triển, không phải bộ seed chưa triển khai. Không cần repository Threadnote.
Chỉ dẫn hiện hành của người dùng và chỉ dẫn cấp hệ thống cao hơn luôn được ưu tiên.

## Đọc đầu mỗi task

1. [Mục tiêu và định hướng](codex/PRODUCT_DIRECTION.md): người dùng, giá trị sản phẩm, phạm vi và thứ tự ưu tiên.
2. [Nguyên tắc và bài học](codex/PRINCIPLES_AND_LESSONS.md): các sai lầm cần tránh và ranh giới bằng chứng.
3. [Quy trình phát triển/tự đánh giá](codex/DEVELOPMENT_WORKFLOW.md): cách chọn việc, kiểm chứng, học hỏi và bàn giao.
4. Phần mới nhất của [CHECKPOINT](codex/CHECKPOINT.md) và [QUALITY_REVIEW](codex/QUALITY_REVIEW.md).
5. Tài liệu kỹ thuật liên quan, [kế hoạch database](docs/impact-atlas-plan.md), [nghiệm thu v1](docs/product-v1-acceptance.md)
   và phần task liên quan trong [TASKS](codex/TASKS.md). Không phải đọc lại toàn bộ lịch sử mỗi lần.

Trước khi sửa: kiểm tra Git/worktree, xác minh trạng thái thực tế; nêu ngắn gọn task cải thiện
giá trị nào cho nhà đầu tư và kết quả nào sẽ chứng minh điều đó. Không coi checkpoint là bằng
chứng một server, nguồn hoặc test vẫn ở trạng thái cũ.

## Quy tắc làm việc

- Không bịa dữ kiện trong tin hoặc giả làm số liệu công bố. Được bổ sung chỗ thiếu trong database bằng tri thức LLM phổ biến, rõ ràng, tối đa một bước từ dữ kiện có nguồn; gắn nhãn LLM_PRIOR_UNVERIFIED, cơ sở/điều kiện/phiên bản. Ước lượng số phải là khoảng có mẫu số và phương pháp; không suy tiếp từ prior, không điền nếu mơ hồ. Xem docs/knowledge-priors.md. Không tự bịa giá, kỳ, hợp đồng hoặc xác suất.
- Tin giá hàng hóa không cần pháp nhân đầu nguồn: ghép vào đầu vào công ty có nguồn. Ngưỡng thử nghiệm >5%, mạnh từ 10% là biến động giá, không phải tác động lợi nhuận; xem docs/commodity-price-relevance.md.
- Ưu tiên hồ sơ công ty, database quan hệ có nguồn, cơ chế rõ ràng và thẻ tin giải thích được.
  Không tối ưu từng bài để đẹp điểm; không thay mục tiêu bằng việc tích lũy công cụ thẩm định.
- Phân biệt tin liên quan, cơ chế có điều kiện, tác động được xác minh và độ lớn được định lượng.
  Không suy ra dự báo giá từ đường graph; không bỏ hết tin bối cảnh chỉ vì thiếu số liệu tác động.
- Giữ dữ liệu chi tiết cục bộ/được ignore; không commit nguồn thô, DB, token, nhãn chi tiết.
  `SEND_NOTIFICATIONS=false`, `ALLOW_SYNTHETIC_LIVE=false`, `LLM_MODE=none` cho đến khi người dùng đổi yêu cầu.
- Không bật cloud/public hosting, gửi thông báo thật hoặc mở quyền truy cập vì một checklist đã đạt.
- Tests phải đúng với thay đổi. Chỉ sửa tài liệu: kiểm tra liên kết, tính nhất quán, diff; không cần
  chạy lại toàn bộ tests. Thay code/data rules: kiểm tra tích hợp liên quan và quy trình CI của repo.
- Chủ động làm việc đã được cho phép; chỉ hỏi khi cần quyết định thực sự về mục tiêu, phạm vi,
  quyền truy cập/chi phí hoặc lựa chọn không thể suy ra. Không tự thêm vòng xin xác nhận.
- Không tự tạo nhãn “độc lập” bằng agent triển khai. Nếu cần đánh giá mù, tuân thủ protocol và
  quyền sử dụng agent hiện hành; công khai nhãn AI, không gọi là human gold.

## Kết thúc mỗi task

- Rà soát kết quả, sai sót còn lại, giới hạn bằng chứng và tác động đến mục tiêu sản phẩm.
- Cập nhật CHECKPOINT và QUALITY_REVIEW cho lượt triển khai/đánh giá. Khi có bài học mới,
  cập nhật PRINCIPLES_AND_LESSONS với bằng chứng, phạm vi áp dụng và cách kiểm chứng.
- Không bắt buộc “sáng tác” bài học mới: nếu không có, ghi đã rà soát và giữ nguyên nguyên tắc.
- Nếu đổi định hướng theo yêu cầu người dùng, cập nhật PRODUCT_DIRECTION và ghi phần bị thay thế.
  Không âm thầm đổi tiêu chí nghiệm thu để hợp thức hóa kết quả.
- Báo rõ đã làm/đã kiểm chứng/chưa đạt, hạn chế và bước tiếp có ưu tiên; chỉ báo push/CI thành công
  khi đã kiểm tra. Không suy ra chất lượng thị trường từ số tests đạt.

Các phần seed, Threadnote và mốc P0–P5 trong tài liệu cũ là lịch sử. Khi mâu thuẫn, dùng định
hướng hiện hành ở trên; giữ bằng chứng cũ, đánh dấu bị thay thế thay vì xóa lịch sử thất bại.
