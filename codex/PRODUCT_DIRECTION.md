# Mục tiêu và định hướng sản phẩm

## Đánh giá toàn diện theo nhóm tin — quyết định 2026-11-26

Người dùng yêu cầu bắt đầu giai đoạn đánh giá/hiệu chỉnh sau khi luồng bước1–3 đã triển khai.
Thay thế trạng thái hoãn benchmark tổng thể bên dưới; vẫn không mở đánh giá riêng tri thức LLM.
Đo ghép hồ sơ và chọn thẻ riêng; phân biệt relevance, độ đáng ưu tiên và tác động tài chính.
Không biến tập phát triển cũ thành kiểm tra mù mới, không đổi trọng số khi dữ liệu không nhận diện
được đóng góp của chúng. Giữ tiêu chí nghiệm thu, dữ liệu cục bộ và thông báo thật tắt.
Xem [quy trình/đợt đo hiện tại](../docs/grouped-relevance-calibration.md).

## Phạm vi v1 gọn và trình tự triển khai — quyết định 2026-11-25

Chốt sớm cấu trúc dùng lại cho nhiều công ty: 7 nhóm cốt lõi và 10 loại quan hệ theo
[core-profile-v1](../docs/core-profile-v1.md), không mở rộng database quá rộng/khó kiểm soát.
42component cũ là thư viện mở rộng, không phải checklist bắt buộc để thêm một công ty.
Mã hàng hóa/thị trường giá dùng chung; quan hệ với công ty luôn giữ phạm vi sản phẩm và nguồn.
Ưu tiên hoàn thiện database và thuật toán, rồi xem xét toàn diện hiệu suất, hướng dữ liệu và
các vòng lặp cải thiện. **Không triển khai đánh giá riêng tính đúng/hữu ích tri thức LLM lúc này.**
Các đề xuất explanation-review/blind evaluation riêng trong checkpoint/L014 cũ được hoãn,
không phải yêu cầu tiếp tục ngay. Tests, kiểm tra dữ liệu/nguồn và sửa lỗi vẫn bắt buộc;
không hạ tiêu chí chất lượng phát hành hoặc tuyên bố accuracy khi chưa đo. Giữ dữ liệu cục bộ,
thông báo thật tắt. Đợt đầu chỉ mở rộng đầu vào bộ nhớ có nguồn để kiểm tra cấu trúc dùng chung.

## Bổ sung tri thức LLM có giới hạn — 2026-11-25

Người dùng cho phép lấp khoảng trống database bằng tri thức LLM phổ biến khi nguyên tắc
ước lượng/suy luận rõ ràng, tối đa một bước. Đây là lớp LLM_PRIOR_UNVERIFIED riêng, không phải
dữ kiện công ty công bố. Dữ kiện có nguồn được ưu tiên; prior không được dùng làm tiền đề cho
prior tiếp theo hoặc âm thầm trở thành SOURCE_BACKED. Tỷ trọng/độ phụ thuộc có thể dùng khoảng
ước lượng nếu phạm vi, mẫu số, cách ước lượng và cơ sở kiến thức đủ rõ; không phổ biến/mơ hồ thì
để UNKNOWN. Không giả định số cụ thể chỉ để database đầy. Xem [contract](../docs/knowledge-priors.md).
Quyết định này thay lệnh cấm tuyệt đối ước lượng chỗ thiếu trước đây; giữ nguyên cấm bịa dữ kiện
trong tin, nguồn, kỳ, giá, hợp đồng và tuyên bố tác động đã xác minh.

## Quyết định hàng hóa và bằng chứng — 2026-11-25

Tin biến động giá hàng hóa có thể ảnh hưởng toàn ngành và không cần một pháp nhân đầu nguồn.
Ghép hàng hóa vào danh mục đầu vào sản phẩm/phân khúc/cơ sở của từng công ty có nguồn trong database;
không yêu cầu tin phải nêu tên công ty, không tự suy ra mọi doanh nghiệp cùng ngành đều dùng nguyên liệu đó.
Mặc định thử nghiệm: biến động tuyệt đối vượt 5% trong kỳ được tin nêu rõ mới tạo ứng viên cảnh báo;
từ 10% là biến động giá mạnh. Hai ngưỡng có phiên bản, chưa phải trọng số đã hiệu chỉnh thực nghiệm.
Liên quan đầu vào không đồng nghĩa tác động lợi nhuận đã xác minh, cũng không dự báo giá cổ phiếu.

Tuyệt đối không bịa dữ liệu. Dữ kiện lấy đúng từ tin, kết hợp database có nguồn (ưu tiên trọng tâm)
và quy tắc thuật toán minh bạch để suy luận mức liên quan/cơ chế. Thiếu tỷ trọng, kỳ, hợp đồng hoặc
bằng chứng về thời gian truyền dẫn thì dữ kiện gốc vẫn UNKNOWN; có thể bổ sung prior theo quy tắc một bước ở trên, không trình bày prior như sự thật.
Chi tiết triển khai và giới hạn: [commodity-price-relevance](../docs/commodity-price-relevance.md).
Quyết định này thay yêu cầu pháp nhân đầu nguồn đối với nhánh hàng hóa; các đường xác minh khác giữ contract riêng.

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

## Cross-source price context — user decision 2026-11-26

The user permits one-step inference from comparable sources when price metadata is
missing. Preserve source prices, exact instrument/market/period and separate inferred
units from source-declared units. Do not assume a chip, module, retail and contract
quote must be similar; do not use numerical closeness as sole identity evidence.
See L016 and the core price-series contract. This does not authorize live delivery,
cloud publication, invented observations or calibrated-impact claims.
