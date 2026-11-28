# Vai trò, hạn chế truy cập và tài trợ — 2026-11-28

Đã triển khai ba bước, chạy đủ benchmark **10 cohort / 3.040 cặp tin–narrative**
sau từng bước và chạy thêm một lần sau rà soát cuối. Nhãn là AI đã exposed,
không phải đánh giá mù mới hoặc human gold. Target và nhãn gốc giữ nguyên.

| Bước | Thay đổi | Relevance trên infra160: TP/FP/FN | Priority: TP/FP/FN |
|---|---|---:|---:|
| Trước task | Baseline đã khóa | 8/0/15 | 2/0/7 |
| 1 | Vai trò không loại trừ nhau; chủ vận hành không đồng nghĩa nhà cung cấp | 8/0/15 | 2/0/7 |
| 2 | Hạn chế tiếp cận compute qua đường demand/deployment có nguồn | 9/0/14 | 4/0/5 |
| 3 | Hậu thuẫn vốn gắn với đối tác và mục đích vận hành | 9/0/14 | 5/0/4 |
| Rà soát cuối | Chặn cấu hình chồng lấn và tên công ty khác | 9/0/14 | 5/0/4 |

Các cohort khác không đổi. Tổng cộng có **1 quyết định relevance và 3 quyết định
priority cải thiện**, không có quyết định bị đánh giá kém đi hoặc thay đổi chưa rõ
trong lượt này. Đây là bốn quyết định, không phải bốn sự kiện độc lập. Infra160 còn
20 cặp chưa rõ relevance và21 cặp chưa rõ priority. Hai thẻ bị hạ priority ở lượt
trước vẫn chưa có nhãn priority riêng; không được coi là đã giải quyết.

## Đã thay đổi

- Vai trò khách hàng, nhà cung cấp, bên bán và đối thủ được đọc từ cạnh graph có
  nguồn, đúng hướng, phạm vi và thời gian. Một node có thể mang nhiều vai trò.
  Bước1 chưa chứng minh được lợi ích trên nhãn benchmark hiện tại; nó sửa ranh giới
  ngữ nghĩa và được kiểm tra bằng các công ty synthetic đổi tên.
- Thêm matcher hạn chế truy cập có cấu hình riêng. Chỉ nối vào narrative nhu cầu/
  triển khai và đường cơ chế có nguồn; không suy thành tác động nguồn cung. Phạm vi
  công ty phải được xác nhận trong hồ sơ, không được mượn tên từ tiêu đề/câu khác.
- Thêm ưu tiên cho hậu thuẫn vốn có đối tác vận hành và mục đích vật chất cụ thể,
  trên một tin vốn đã liên quan. Tách kế hoạch với thông tin hậu thuẫn được nguồn
  nêu; không coi là vốn đã giải ngân, đơn hàng hoặc năng lực đã hình thành.
- Hồ sơ NVIDIA22→23 thêm một binding vào factor/edge đã có nguồn. Sáu hồ sơ,
  83nodes/97relations/11narratives giữ nguyên; không đổi target, trọng số số học hoặc
  bịa quan hệ mới. Atlas/registry cục bộ được dựng lại và kiểm tra.

## Luồng thực tế và kiểm chứng

Pipeline cục bộ: **50 thẻ chính / 42 thẻ bối cảnh**, NVDA23/DELL27 thẻ chính;
hai thẻ ACCESS_RESTRICTION và một thẻ CAPITAL_BACKING đã tới feed. Tất cả92thẻ
delivery disabled; hướng, độ lớn và thời hạn tác động tài chính vẫnUNKNOWN.
10lần kiểm tra RSS:7OK/3Not Modified,4tin mới/0tin sửa. Số thẻ tăng không được
quy hoàn toàn cho thuật toán vì đợt poll có dữ liệu mới; benchmark cố định phía trên
mới là phép so sánh chất lượng cùng tập.

Tests bước1:31đạt; bước2 cuối:37đạt; cuối lượt:141đạt. Ruff và mypy170files đạt.
CI [46118830543](https://github.com/linhpmvpub/Narrative/actions/runs/46118830543) đạt trên commit `633ad89`: 1694 passed, 1 warning in 162.80s (0:02:42); 1694 passed, 1 warning in 249.20s (0:04:09); migration, JS, audit và model smoke8 đạt. Không có thay đổi UI;
không tuyên bố đã kiểm tra giao diện desktop/mobile mới.

## Hạn chế và bước tiếp theo

1. Infra160 còn14cặp liên quan và4cặp priority bị bỏ sót; access mới có một phạm vi
   công ty được cấu hình bằng nguồn. Mở rộng bằng hồ sơ có nguồn, không thêm nhánh ticker.
2. Phạm vi cộng tác bên thứ ba còn bảo thủ; một công ty có nhiều vai trò không có
   nghĩa tin nào cũng áp dụng cho mọi vai trò. Cần tiếp tục phân biệt sản phẩm,
   đối tượng chịu hạn chế và tài sản được tài trợ theo đường graph cụ thể.
3. Bổ sung readiness/power/construction vào đúng narrative bằng bằng chứng;
   không dùng tin nhu cầu để tự tạo đường nguồn cung. Kiểm tra cú pháp bị động,
   phối hợp và tham chiếu chủ thể mà các matcher giới hạn còn bỏ sót.
4. Sau thay đổi framework/data, dùng các gia đình sự kiện chưa dùng để đánh giá
   độc lập. Bộ3040giữ làm hồi quy. Nhãn AI/nguồn hiện tại không xác lập causal truth,
   magnitude/horizon tài chính, utility cá nhân hóa hay nghiệm thu vận hành7ngày.

**V1 chưa đạt toàn bộ tiêu chí phát hành.** Dữ liệu nguồn/nhãn/database cục bộ,
cloud và thông báo thật vẫn tắt. Không cần quyết định mới từ người dùng để tiếp tục.

[Số liệu theo nhóm/công ty](roles-access-finance-review.json) ·
[Contract kỹ thuật](../docs/roles-access-finance.md) ·
[Quy trình benchmark](../docs/quality-benchmark.md)
