# Mục tiêu và định hướng sản phẩm

Cập nhật: 2026-11-25. Chủ quyết định sản phẩm: người dùng. Agent duy trì tài liệu theo chỉ đạo
và bằng chứng; không tự thay mục tiêu. Đây là định hướng hiện hành, không phải tuyên bố đã hoàn thành.

## Vấn đề cần giải quyết

Nhà đầu tư cá nhân thiếu thời gian và cái nhìn toàn cảnh để nhận ra tin tức có liên quan đến
công ty/cổ phiếu hoặc narrative họ theo dõi. Tin quan trọng có thể nằm ở nhà cung cấp, khách hàng,
giá nguyên liệu, công suất, logistics, tài trợ, giấy phép hoặc thời tiết, chứ không nhắc tên cổ phiếu.

Narrative cần giúp họ trả lời: **Tin gì đáng đọc, vì sao liên quan, đi qua quan hệ nào, điều gì
đã có bằng chứng và điều gì còn chưa biết?** Bản đồ quan hệ dùng để minh họa/kiểm tra đường liên
quan và cơ chế tác động, không dự báo diễn biến giá hay khuyến nghị mua/bán.

## Sản phẩm đích

- Hồ sơ chuẩn có cấu trúc cho từng công ty: pháp nhân/lịch sử doanh nghiệp; sản phẩm/phân khúc;
  doanh thu/chi phí/tài chính; đầu vào/nhà cung cấp; khách hàng/nhu cầu đầu ra; giá/điều khoản hợp đồng;
  tồn kho/nguồn thay thế; cơ sở/công suất/logistics; công nghệ/đối thủ; tài trợ; giấy phép/chính sách;
  thị trường/địa lý/thời tiết và giao dịch nội bộ khi có cơ chế phù hợp.
- Mỗi yếu tố và quan hệ có định nghĩa, phạm vi, nguồn, thời điểm biết/hiệu lực, phiên bản và phần thiếu.
  Khung có thể rộng; không giả vờ rằng mọi công ty đều đã được điền đầy đủ.
- Pipeline: thu thập → phiên bản/lọc trùng → nhận diện phát biểu/sự kiện → ghép yếu tố trong hồ sơ →
  xét đường quan hệ và cơ chế → gắn narrative → thẻ tin/map → ưu tiên theo người dùng.
- Thẻ tin: tóm tắt sự kiện, công ty/narrative liên quan, đường giải thích, nguồn và kỳ, điều kiện/
  yếu tố bù trừ, độ chắc chắn và phần chưa biết. Cường độ và ngắn/dài hạn chỉ điền khi có căn cứ;
  thiếu dữ liệu được biểu diễn rõ, không mặc định là “tác động thấp”.
- Push cá nhân hóa là mục tiêu sau cùng; private feed/map là nơi kiểm tra chất lượng trước đó.

## Lợi thế cần xây dựng và đo lường

Lợi thế kỳ vọng nằm ở database quan hệ được duy trì có nguồn, ontology/cơ chế/đơn vị rõ ràng,
khả năng nhận ra liên quan gián tiếp, xử lý lịch sử sửa đổi và lời giải thích truy vết được.
LLM có thể là công cụ hỗ trợ theo cấu hình được chấp thuận; không thay thế bằng chứng hoặc
được coi là ground truth. Chưa có benchmark chứng minh sản phẩm vượt LLM thông thường.

Phải đo chất lượng trên cùng tập sự kiện với baseline phù hợp: tin đúng/sai/bỏ sót, độ bao phủ
theo công ty/cơ chế, lỗi pháp nhân/phạm vi/kỳ, chất lượng ưu tiên, độ mới và chi phí vận hành.
Số node, số bài, số tests hoặc tỷ lệ đồng thuận AI không tự chứng minh lợi thế sản phẩm.

## Thứ tự phát triển đã thống nhất

1. Hoàn thiện khung hồ sơ và database/bản đồ quan hệ có nguồn; ưu tiên chiều sâu phạm vi và dữ liệu
   kinh tế có nghĩa hơn số cạnh. Pilot: MU, NVDA, AMD, DELL, SNDK; canonical seed có 10 narrative.
   Không tự ép mọi lớp research/profile phải có đúng 10 narrative hay cùng giới hạn hop với graph canonical.
2. Chuẩn hóa nhóm cơ chế, dữ liệu, tham số, quy tắc và trạng thái thiếu; giải thích được đường từ
   tin đến narrative. Chọn yêu cầu phạm vi phù hợp từng cơ chế, không ép mọi tin có một nhà máy.
3. Đóng băng database/rules/predictions, test từng nhóm tin đa dạng và ca âm tính bằng nhãn độc lập.
   Dùng dữ liệu lịch sử để tăng tốc, phân biệt current-profile diagnostic và backtest đúng as-of.
4. Sửa lỗi có tính hệ thống; chỉ hiệu chỉnh trọng số/cường độ/thời gian khi dữ liệu và đánh giá đủ.
   Không sửa một câu tin rồi gọi là cải thiện thuật toán.
5. Hoàn thiện feed/map cá nhân hóa, độ mới, lifecycle, quan sát vận hành và nghiệm thu; chỉ triển
   khai cloud/push khi có yêu cầu rõ và các điều kiện tương ứng đã đạt.

Các luồng có thể phát triển song song khi cần, nhưng mỗi task phải chỉ ra đóng góp cho sản phẩm.
Hạ tầng kiểm tra là phương tiện; không để nhiều lượt chỉ thêm kiểm soát trong khi dữ liệu/recall đứng yên.

## Phân tầng kết luận

| Mức | Có thể trình bày | Không được suy ra |
|---|---|---|
| Tin có liên quan | Căn cứ nguồn và quan hệ với yếu tố/narrative, phần chưa xác minh | Đã có ảnh hưởng kinh tế thực tế |
| Cơ chế có điều kiện | Kênh truyền, chiều tác động lên kênh nếu điều kiện đúng, yếu tố bù trừ | Lợi nhuận/giá cổ phiếu chắc chắn tăng giảm |
| Tác động được hỗ trợ | Phạm vi, kỳ, bằng chứng công ty và quan hệ nhân quả phù hợp | Độ lớn khi chưa có mẫu số/giả định |
| Định lượng/kịch bản | Giá trị có nguồn hoặc giả định được gắn nhãn rõ | Biến kịch bản thành dữ kiện hay dự báo chắc chắn |

## Ràng buộc hiện hành

Standalone Narrative, bỏ qua Threadnote. Repository: `linhpmvpub/Narrative`.
Dữ liệu chi tiết cục bộ; GitHub chỉ nhận code/docs/fixtures synthetic và số liệu tổng hợp phù hợp.
Thông báo thật tắt, synthetic live false, LLM mode none. Sự cho phép Cloudflare thử nghiệm trước đây
không có nghĩa tự đưa dữ liệu lên cloud sau chỉ đạo giữ cục bộ. Không biến vấn đề quyền nguồn thành
vòng hỏi lặp lại đã được người dùng quyết định; vẫn giữ provenance, tôn trọng kiểm soát truy cập,
không mặc định quyền phát hành công khai/thương mại đã được xử lý.

## Điều hướng tài liệu và cập nhật quyết định

- Trạng thái thực tế/bước gần nhất: [CHECKPOINT](CHECKPOINT.md); tồn tại và khắc phục: [QUALITY_REVIEW](QUALITY_REVIEW.md).
- Thiết kế database: [impact-atlas-plan](../docs/impact-atlas-plan.md); khung hồ sơ: [company-profile-framework](../docs/company-profile-framework.md).
- Tiêu chí định lượng v1: [product-v1-acceptance](../docs/product-v1-acceptance.md); giữ nguyên target khi báo chưa đạt.
- Quy trình và bài học: [DEVELOPMENT_WORKFLOW](DEVELOPMENT_WORKFLOW.md), [PRINCIPLES_AND_LESSONS](PRINCIPLES_AND_LESSONS.md).

Khi người dùng đổi phạm vi/ưu tiên, ghi ngày, quyết định, lý do và tài liệu bị thay thế tại đây;
cập nhật checkpoint và tài liệu liên quan. Không sao chép số liệu vận hành thay đổi liên tục vào charter.

| Ngày ghi nhận | Quyết định hiện hành | Căn cứ |
|---|---|---|
| 2026-11-25 | Sản phẩm theo dõi tin/narrative, không dự báo giá; standalone, database trước rồi đánh giá nhóm tin | Chỉ đạo nhiều phiên của người dùng; kế hoạch atlas và checkpoint |
| 2026-11-25 | Chuẩn hóa tài liệu bắt buộc đọc và cơ chế học hỏi sau mỗi task | Yêu cầu người dùng của phiên này |

Ngày trên là ngày tổng hợp quyết định, không suy đoán ngày phát biểu gốc trong lịch sử chat.
