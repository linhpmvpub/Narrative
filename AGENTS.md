# Hướng dẫn cho agent làm việc trong repository

## Company benchmark now active — 2026-11-28

Read [docs/company-benchmark.md](docs/company-benchmark.md) and [docs/company-assessment.md](docs/company-assessment.md).
Company relevance/attention is the primary measured target. Lead results with COMPANY_EFFECTIVENESS_V1
(first6.50/100), preserve legacy mixed25.18as a separate regression series. Do not compare formulas.
For each runtime/config/profile update, replay both fixed references, review all changes and run
quality_gate --all with company_benchmark retained in the current pointer. No missing/unknown/human
labels may be manufactured. New reference is now exposed; new blind claims require new frozen data.
Current foundation is implemented; next tasks target shared event/exposure coverage and source quality,
not narrative templates. Read latest tasks/checkpoint before work; all other source/privacy rules remain.


## Ưu tiên hiện hành: sản phẩm cấp công ty — 2026-11-28

Người dùng xác định nhận diện/phân tích/đánh giá tin cấp công ty là sản phẩm nền;
narrative là lớp nâng cao dùng lại nền đó. Đọc [kế hoạch company-first](docs/company-first-product-plan.md)
cùng các tài liệu bắt buộc. Narrative mẫu chỉ là ví dụ kiểm thử, không giới hạn
phạm vi tin, database hay thứ tự ưu tiên phát triển. Luồng công ty phải dùng được
khi không có narrative; không ép tin vào narrative để hiển thị hoặc đánh giá.
Ưu tiên tách company assessment/priority/feed khỏi narrative, rồi chất lượng nguồn,
quan hệ, giải thích và đo trực tiếp sản phẩm công ty. Giữ thời gian/phiên bản để
sau này theo dõi narrative tùy chọn và đối chiếu luận điểm ban đầu với kết quả.

Phần này thay thứ tự narrative-first và cách dùng điểm tổng hợp làm mục tiêu chính
ở các mục cũ. Giữ benchmark40/40/20 đã khóa như chuỗi hồi quy lịch sử; không sửa
nhãn/trọng số hồi tố. Benchmark cấp công ty mới cần policy/target có phiên bản và
freeze trước nhãn; báo riêng, không coi đổi công thức là tăng chất lượng. Kiểm chứng
nguồn/tests/benchmark sau thay đổi runtime, dữ liệu cục bộ và thông báo tắt giữ nguyên.


## Báo điểm dễ hiểu từ phiên sau — quyết định 2026-11-28

Dẫn đầu báo cáo benchmark bằng điểm hiệu quả 0–100 của anchor đã khóa trong current
suite; công thức và giới hạn ở [quality-benchmark](docs/quality-benchmark.md).
Giữ riêng độ phủ tin cấp công ty, độ đúng narrative và ưu tiên; báo FP/FN/unresolved,
hỗ trợ mẫu theo nhóm/công ty và thay đổi so cùng suite. Thiếu nhãn/hỗ trợ thì báo chưa
đủ dữ liệu, không tự tạo điểm. Không lấy điểm này làm xác suất tác động, % hoàn thành
sản phẩm hay lý do bỏ tiêu chí nghiệm thu. Không đổi anchor/trọng số để làm đẹp điểm.

## Benchmark bắt buộc sau thay đổi — 2026-11-28

Đọc [benchmark chất lượng](docs/quality-benchmark.md). Sau mỗi thay đổi engine, cấu hình,
thuật toán hoặc hồ sơ/database, chạy lại suite cục bộ đã khóa và so sánh với run trước.
Sau sửa cuối cùng chạy quality_gate --all; kết quả stale/thiếu/failed không được báo đã
kiểm chứng. Hook pre-commit kiểm tra runtime/config đã stage; thay đổi DB cục bộ cần gate
riêng. Báo FP/FN/unresolved theo cohort/nhóm/công ty, relevance và priority riêng, giữ
các regression. Nhãn đã lộ là hồi quy AI, không phải holdout mới/human gold. Dữ liệu
chi tiết không lên GitHub; chỉ code, tests synthetic và aggregate. Xem checkpoint để
lấy suite SHA, profiles, current-run pointer. Không đổi target/nhãn/baseline âm thầm.


## Giai đoạn hiện hành — 2026-11-26

Người dùng đã yêu cầu đánh giá toàn diện theo nhóm tin và hiệu chỉnh thuật toán/trọng số.
Chuyển sang vòng đo–chẩn đoán–hiệu chỉnh sau bước1–3; chỉ hoãn đánh giá riêng priors.
Tập đã dùng phát triển là regression, không trở thành holdout mới nhờ chia lại.
Xem [đánh giá nhóm](docs/grouped-relevance-calibration.md).

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

- Ưu tiên v1 hiện hành: chốt khung 7 nhóm/10 quan hệ trong config/core-profile-v1.json; mở rộng bằng dữ liệu có nguồn, không bắt buộc điền đủ 42 component lịch sử. Xem docs/core-profile-v1.md.
- Theo quyết định người dùng 2026-11-25, chưa thực hiện đánh giá riêng tính đúng/hữu ích của tri thức LLM. Hoàn thiện database và thuật toán trước, đánh giá hiệu suất/hướng dữ liệu toàn diện và vòng lặp cải thiện sau. Vẫn chạy tests, kiểm tra nguồn và rà soát lỗi triển khai; không gọi đó là benchmark chất lượng thị trường.
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
