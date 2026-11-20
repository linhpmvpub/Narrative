# BẢN BÀN GIAO CODEx — Relationship & Impact Engine v0

**Ngày:** 19/11/2026. **Trạng thái:** Kế hoạch, schema tham chiếu và seed/test fixtures đã được chuẩn bị; chưa phải backend đã viết và chạy. **Phạm vi:** MU, NVDA, AMD, DELL, SNDK — 10 narrative, 40 cạnh quan hệ ứng viên.

## 1. Kết quả đầu ra phải có

Một dịch vụ backend độc lập, có thể tích hợp Threadnote, cho phép:

1. Theo dõi 5 cổ phiếu và 10 narrative mẫu, có thể lựa chọn và tạo thread.
2. Tự nạp dữ liệu từ nguồn được phép sử dụng; chuẩn hóa thành sự kiện có nguồn và thời điểm công bố chính xác.
3. Đối chiếu sự kiện với các driver trong narrative, xác định đường truyền tác động kinh tế (0–2 cạnh), lý do liên quan, điều kiện chưa được chứng minh.
4. Chấm mức độ mới, quan trọng, bằng chứng và phù hợp; quyết định PUSH / DIGEST / STORY / REVIEW / SUPPRESS.
5. Lưu dấu vết quyết định, hiển thị lịch sử storybook và nhận feedback.
6. Replay lịch sử theo as-of (chỉ sử dụng thông tin được công bố đến thời điểm mô phỏng); so sánh với baseline từ khóa và LLM không graph.
7. Vận hành fixture offline không cần LLM/API key; mặc định không gửi push thật.

### Phần KHÔNG triển khai trong v0

- Không xây app iPhone mới, không thêm hệ thanh toán thực tế, không giao dịch, không dự đoán xác suất giá tăng, không đưa khuyến nghị mua/bán.
- Không dùng nguồn tin không có quyền phân phối, không giả định mọi quan hệ AI suy luận đều là sự thật.
- Không mở rộng quá 5 cổ phiếu trước khi đạt ngưỡng đánh giá.

## 2. Danh sách 10 narrative, điều kiện kiểm chứng

**N01 — MU: HBM demand and premium product mix drive profitability.** Theo dõi nhu cầu HBM, lượng doanh thu/mix HBM MU công bố (nếu có), giá DRAM, gross margin. Củng cố khi các chỉ tiêu kinh doanh MU xác nhận được việc thương mại hóa nhu cầu. Phản bác khi cầu thị trường tăng nhưng doanh thu/mix/gross margin của MU không theo. Cần tách thay đổi giá bán, chi phí wafer, yield và accounting mix.

**N02 — MU: Memory supply cycle threatens pricing power.** Theo dõi bit supply, công suất DRAM, tồn kho, ASP, margin. Củng cố giả thuyết rủi ro khi cung tăng thực tế đi kèm giá giảm; phản bác khi giá và margin duy trì tốt mặc dù công suất tăng. Công bố công suất mới chưa đồng nghĩa với cung mới ngay lập tức.

**N03 — NVDA: AI infrastructure spending sustains accelerator demand.** Theo dõi capex hạ tầng AI, accelerator demand, revenue Data Center của NVIDIA. Củng cố khi tiền đầu tư chuyển hóa vào doanh thu giao hàng; phản bác khi capex tăng nhưng không chuyển thành revenue NVIDIA. Không lấy toàn bộ capex hyperscaler nhân cho thị phần GPU như doanh thu chắc chắn.

**N04 — NVDA: Supply and export constraints limit growth.** Theo dõi khả năng đóng gói, bộ nhớ và nguồn cung hệ thống; sản phẩm/thị trường bị export controls điều chỉnh. Củng cố giả thuyết rủi ro khi tài liệu chứng minh ràng buộc ảnh hưởng lượng giao hàng; phản bác khi năng lực cung và doanh thu được khôi phục. Không nhầm supply commitments với hàng đã giao.

**N05 — AMD: Instinct adoption drives AI revenue expansion.** Theo dõi deployments, GPU Instinct, số liệu Data Center; chỉ kết luận chuyển hóa khi có shipments/revenue phù hợp. Phản bác khi hợp đồng công bố không chuyển hóa hoặc tăng trưởng Data Center chủ yếu từ CPU. Không tự cộng các hợp đồng thông báo thành doanh thu.

**N06 — AMD: EPYC share gains improve data center business.** Theo dõi adoption EPYC, thị trường server CPU, revenue/margin Data Center. Phản bác khi tăng trưởng CPU không kéo được kinh tế phân khúc. Phải tách EPYC khỏi accelerator trong tổng Data Center.

**N07 — DELL: AI server orders convert into profitable revenue.** Theo dõi orders, backlog, doanh thu server AI, biên lợi nhuận ISG và vốn lưu động. Củng cố khi backlog thành revenue và lợi nhuận; phản bác khi backlog kéo dài hoặc margin/cash conversion xấu đi. Các kỳ báo cáo Dell và chuẩn backlog phải nhất quán.

**N08 — DELL: Component inflation compresses infrastructure margins.** Theo dõi giá DRAM/NAND, chi phí cấu phần, gross/operating margin ISG, mức chuyển giá tới khách hàng và vendor rebates. Củng cố giả thuyết rủi ro khi chi phí tăng mà giá bán không bù đắp; phản bác khi pricing/mix/rebates bù được. Giá spot không tự động là giá nhập linh kiện của Dell.

**N09 — SNDK: NAND pricing recovery supports earnings.** Theo dõi NAND ASP, bit supply/shipments, inventory, Sandisk revenue/margin. Phản bác khi ASP tốt mà margin/cash conversion không tăng. Không dùng WDC HDD revenue sau phân tách và thận trọng so sánh kỳ lịch sử quanh 2025.

**N10 — SNDK: Enterprise SSD adoption expands higher-value storage demand.** Theo dõi enterprise SSD demand, Sandisk enterprise product mix và shipments, gross margin. Phản bác khi nhu cầu toàn ngành tăng mà kết quả Sandisk không tương ứng. Không suy diễn mọi capex AI đều là đơn hàng SSD cho SNDK.

Narrative N02, N04 và N08 là **giả thuyết rủi ro**: SUPPORTS là bằng chứng làm rủi ro thuyết phục hơn, **không có nghĩa cổ phiếu tích cực**. Lưu hai trường riêng `narrative_stance` và `economic_effect`.

## 3. Phương pháp xây graph 6 bước

**Bước 1 — Entity registry:** Tạo mã cố định cho công ty, sản phẩm, driver, policy và financial metric. Ticker là alias có thời hạn; SEC CIK xác minh từ dữ liệu nguồn (không tự điền nếu chưa kiểm tra).

**Bước 2 — Relationship proposer:** Từ tài liệu và hiểu biết kinh tế, tạo candidate edge `A -> B` với một trong sáu family. Mỗi edge nêu rõ cơ chế tác động và điều kiện phụ thuộc.

**Bước 3 — Evidence verifier:** Gắn chính xác filing/document URL, ngày công bố, đoạn chứng minh, người đánh giá, thời gian xác minh. Không có bằng chứng: không được `verified`. Nếu tỷ trọng exposure / elasticity không được công bố thì không bịa số; lưu `unknown`.

**Bước 4 — Temporal graph:** Chỉ dùng những cạnh đã xác minh và có hiệu lực ở thời điểm replay. Max 2 cạnh. Không cộng các đường trùng cơ chế; chọn đường tốt nhất, lưu đường thay thế để kiểm tra.

**Bước 5 — Event matcher:** Chuẩn hóa event, gắn metric và canonical key, xử lý tin đăng lại và sửa đính chính. Match với các driver / stock thread, đánh giá điều kiện củng cố hoặc phản bác.

**Bước 6 — Quality loop:** Chấm và lưu toàn bộ quyết định, kể cả tin không push; dùng feedback và gold human labels để cập nhật có kiểm soát, không cho model tự đánh giá rồi tự sửa production.

### Công thức v0

`Score = 100 * (0.25*Relevance + 0.20*Materiality + 0.20*Novelty + 0.15*EvidenceQuality + 0.10*Timeliness + 0.10*UserFit)`.

Tất cả biến nằm trong 0–1, lưu riêng từng thành phần. Score chỉ xếp hạng. Mọi assertion có nguồn; `EvidenceQuality <0.70` thì chặn; `>=0.80` mới có thể xem xét push; khi materiality chưa xác định, không push. 80+ push candidate, 60–79 digest, còn lại story/ignore. Có hard gates và dry-run. Không dùng score như xác suất biến động giá.

### Lịch chạy gợi ý (v0, có thể đổi theo chi phí)

- SEC/IR polling mỗi 30–60 phút khi nguồn cho phép, có cache và rate limit; không cần gọi LLM nếu filing hash không thay đổi.
- Batch chuẩn hóa event sau mỗi lần phát hiện nguồn mới.
- Cập nhật relationship và narrative theo phiên bản, không chỉnh sửa ngược lịch sử.
- Weekly review danh sách edge chưa xác minh, feedback WRONG, false positives và false negatives.
- Chỉ gửi real push sau khi nghiệm thu nguồn, chất lượng và quyền nội dung; demo ở chế độ `dry_run`.

## 4. Dữ liệu, kiểm thử và nghiệm thu

**Tài sản có sẵn trong package:** 5 stock seeds, 42 entity nodes, 10 narrative definitions, 40 candidate edges, 31 synthetic fixtures, 22 golden cases, schema SQL tham chiếu, checklist từng sprint, prompt Codex. Các con số này mô tả **bộ seed mẫu**, không phải database đã chạy và không phải số quan hệ đã được xác minh.

**Vòng kiểm thử dữ liệu thật:** thu 50–100 sự kiện lịch sử có nguồn cho 5 công ty, tạo nhãn con người cho true/false relevance, materiality, stance, push-worthiness, rồi đo so với hai baseline. Chia theo thời gian, khóa holdout trước khi tune; mọi dữ liệu phải có `available_at` hợp lệ tại ngày replay.

**Chỉ tiêu mục tiêu thử nghiệm:** >90% push precision và >80% recall của sự kiện có materiality trên holdout, 100% alert có đường dẫn bằng chứng, 0 fake claim nghiêm trọng, 0 sự kiện synthetic gửi thật. Với tập nhỏ phải báo cáo mẫu số và khoảng bất định; không tự tuyên bố đạt sau khi chỉ chạy fixture tests.

## 5. Thứ tự giao việc cho Codex

- **P0:** Khảo sát repo đang có, chốt tích hợp và stack, tạo skeleton API, Docker/WSL, môi trường offline.
- **P1:** Schema + seed 5/42/10/40 + kiểm tra danh tính SNDK/WDC + kiểm tra quan hệ candidate không được push.
- **P2:** Nạp dữ liệu offline, adapter SEC, xác minh số liệu, provenance, dedup/correction.
- **P3:** Graph 0–2 hops, hard gates, scoring, stance, dry-run, trace, replay.
- **P4:** API thread, feedback, storybook, subscription entitlement 3 stock + 1 narrative miễn phí, auth/tenant isolation.
- **P5:** Bộ dữ liệu lịch sử, so sánh baseline, report đánh giá, performance, chi phí, runbook và go/no-go.

Đề nghị Codex làm theo từng pha, test thực tế rồi mới chuyển pha. **Không thay UI Threadnote hiện có trong P0–P3.** Thời gian trong `README.md` là ước tính khối lượng kỹ thuật, không phải cam kết tiến độ.

## 6. Cấu trúc sản phẩm và thương mại hóa liên quan

- Người dùng free: tối đa 3 stock threads và 1 narrative; 10 narrative có sẵn là templates để chọn chứ không phải 10 lượt miễn phí.
- Dữ liệu sự kiện được xử lý chung một lần, sau đó fan-out theo subscription. Không chạy cả pipeline riêng cho mỗi user.
- Feedback `Useful / Already knew / Not relevant / Unclear / Wrong` chia thành hai hệ: chất lượng khách quan và sở thích cá nhân.
- Storybook: bản ghi từ verified events, metrics theo mốc công bố, price series từ nguồn được phép; mặc định riêng tư. Không nội suy doanh thu theo ngày hoặc dùng diễn biến giá để bịa lại lý do quá khứ.

## 7. Khi nào coi là xong v0?

Codex chỉ được báo "DONE" khi API nhận được sự kiện từ fixture hoặc nguồn thật, tìm ra đúng đường quan hệ đã xác minh, áp hard gates, lưu `decision_trace`, trả về card có bằng chứng và tạo storybook entry; test được cả trường hợp **không** gửi. Đồng thời, `tests/golden_cases.json` phải được chuyển thành test thực thi, và các lỗi bảo mật / as-of / dữ liệu nguồn đều có kiểm tra tự động.

**Bắt đầu Codex:** xem `CODEX_START_HERE.md`. File `README.md` chứa đầy đủ chi tiết kỹ thuật và schema tham chiếu nằm tại `schemas/schema.sql`.
