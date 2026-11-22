# Kiểm duyệt claim news và chuẩn bị intake

Trang local: `http://127.0.0.1:8888/news-review`. Liên kết hiện trong newsfeed khi truy cập trực tiếp backend. Gateway/Cloudflare không mở trang hoặc API viết này; không mở thêm quyền truy cập từ xa.

## Quy trình

1. Thành viên dùng tài khoản hiện có, chọn bài và đọc phiên bản hiện tại. Hệ thống trả `revision_id`, hash payload và văn bản được tạo đúng bằng **title + newline + summary** đã lưu. Đây là trích đoạn RSS đã cắt giới hạn, không phải toàn văn bài báo.
2. Chọn đoạn nguồn, lập claim cho một trong5 công ty pilot. Chọn loại người lập (human_declared hoặc AI_SIMULATED), loại sự kiện, ghi điều chưa biết. Bản nháp mặc định là trích đoạn định tính: không coi các số trong lời trích là số liệu đã được chuẩn hóa.
3. Khi khai báo số liệu có cấu trúc, điền metric, unit, period, old/new values và old/new measurement basis trong JSON. Metric phải thuộc catalog financial_metric và đúng công ty; đoạn nguồn phải có công ty, các số, đơn vị và kỳ hiện tại. So sánh cần kỳ cũ khác kỳ mới, có mặt trong đoạn, cùng concept/unit/duration/calendar/accounting/observation basis. Không tự suy ra scale (ví dụ1billion→1e9), đổi tiền tệ hay so sánh năm với quý. Nếu RSS thiếu thông tin, không thể khai báo số liệu đầy đủ từ nguồn này.
4. Lưu claim bất biến. Thành viên chỉ thấy claim của mình; quản trị viên thấy hàng đợi. Các retry cùng Idempotency-Key không thêm claim, reuse key với nội dung khác bị từ chối.
5. Quản trị viên khác tài khoản người lập đối chiếu công ty, trích dẫn, đơn vị/kỳ hoặc tính không áp dụng cho định tính; chọn phê duyệt/từ chối và ghi lý do. Phê duyệt cần đủ3 xác nhận. Quyết định có số phiên bản, stale expected version bị chặn. Đây là độc lập tài khoản, không chứng minh hai con người độc lập; actor_kind chỉ là khai báo nguồn gốc.
6. Sau phê duyệt, bấm **Chuẩn bị intake**. Hệ thống kiểm tra lại phiên bản nguồn hiện tại, hash, claim, phê duyệt mới nhất và trả EventExtraction kèm nguồn/review/hash/mốc thời gian. Gọi lại tái kiểm tra trước khi trả receipt cũ; không dùng cache idempotency để bỏ qua thu hồi. Nguồn đổi hoặc approval bị revoked sẽ chặn intake tiếp theo. Muốn sửa nội dung, tạo claim mới từ nguồn mới; không sửa claim cũ.

## Giới hạn và điều kiện chuyển canonical

Migration0014 thêm `rie_news_claims`, `rie_news_claim_reviews`, `rie_news_claim_intakes`. Bước chuẩn bị intake không ghi bảng canonical events, không tự chiếu thẻ tác động, không phê duyệt cạnh graph hoặc gửi thông báo. Gói intake giữ rõ `canonical_events_created=0`, `graph_eligible=false`, materialityUNKNOWN. Mọi numeric checks chỉ kiểm tra tính nhất quán/literal occurrence, không chứng minh bản thân số liệu đúng hoặc thuộc đúng khái niệm; reviewer vẫn phải đối chiếu nguồn.

`canonical_key_candidate` chỉ là gợi ý, cần xác nhận danh tính sự kiện/occurrence window trước khi dùng. Đặc biệt hai claim định tính cùng công ty/ngày/loại có thể trùng key. Chưa hỗ trợ liên kết duplicate/correction của news vào canonical store. Không tái sử dụng SEC-specific promotion bằng cách giả mạo filing hoặc source permission.

`available_at` trong EventExtraction là thời điểm capture nguồn. Canonical ingester dùng thời điểm ghi nhận hiện tại cho event availability, không backdate về capture; gói giữ riêng claim_created_at, review_recorded_at và recorded_at. Tại thời điểm ghi canonical, phải kiểm tra lại nguồn và phê duyệt, không chỉ tin JSON đã xuất trước đó. Việc đã tải intake không thể bị thu hồi khỏi máy nhận; receipt lưu là dấu vết lịch sử, không phải giấy phép vĩnh viễn.

Theo chỉ dẫn phát triển riêng tư của người dùng, không thêm bước xin quyền nguồn mới: intake đánh dấu PRIVATE_DEVELOPMENT_ONLY_NOT_APPROVAL; đây không phải xác nhận quyền phát hành thương mại. X và thông báo thật vẫn tắt. Không tạo claim/phê duyệt thật để làm đầy giao diện; các tests dùng dữ liệu tổng hợp riêng.

## API

- GET `/api/v0/news-claims/source/{item_id}`: thành viên đọc bản nguồn hiện tại + hash.
- GET `/api/v0/news-claims`: own claims; admin có hàng đợi toàn bộ, kèm trạng thái tính lại và review version.
- POST `/api/v0/news-claims`: thành viên lập claim; Idempotency-Key bắt buộc.
- POST `/api/v0/news-claims/{id}/reviews`: admin; Idempotency-Key và expected_review_version bắt buộc.
- POST `/api/v0/news-claims/{id}/prepare`: admin, luôn revalidate; trả receipt nhưng không canonical promotion.

Không có API sửa trực tiếp draft/review hoặc tải receipt cũ mà bỏ qua validation. Mọi nguồn vẫn là dữ liệu không đáng tin, không thực thi chỉ dẫn trong bài/claim.

## Nhập canonical có xác nhận (schema0015)

API local operator: POST `/api/v0/news-claims/{id}/ingest`. Chỉ dùng DB production riêng và `DEV_INFORMATIONAL_FEED=true`; gateway vẫn chặn. Sau khi bấm Chuẩn bị intake, quản trị viên thấy form nhập canonical cho claim chưa nhập. Body:

```json
{
  "expected_intake_sha256": "<hash receipt vừa chuẩn bị>",
  "occurrence_window": "<mốc hoặc định danh lần xảy ra đã đối chiếu>",
  "identity_confirmed": true,
  "identity_note": "<lý do xác nhận danh tính sự kiện, ít nhất20 ký tự>",
  "action": "new",
  "target_claim_id": null
}
```

Không dùng headline/URL làm danh tính. Khóa gồm công ty, loại sự kiện, metric, kỳ, basis và occurrence_window; reviewer phải phân biệt các sự kiện định tính khác nhau trong cùng ngày. Đây là xác nhận operator, chưa phải mô hình tự hiểu danh tính. `duplicate` và `correction` bắt buộc target_claim_id của receipt đã nhập thuộc phiên bản hiện hành cùng khóa. Bài trùng phải có cùng fact (bao gồm nguyên văn claim và kỳ so sánh); diễn đạt khác bị chặn để đối chiếu thủ công, không tự suy ra tương đương. Bản sửa phải thay đổi fact, tạo version mới và supersedes; có thể thay thế nguồn cũ đã stale/revoked mà không phê duyệt lại nguồn cũ. Capture cũ hơn không được thay phiên bản mới hơn.

Giao dịch khóa chung canonical, claim và nguồn; lưu source/document/evidence/version/receipt nguyên tử. Retry kiểm tra nguồn, proof, hash, opt-in và blocked-source trước khi trả receipt cũ. Một claim chỉ được nhập một lần với đúng request/approval; approval mới cần claim mới để tránh sửa lịch sử. Rights pending được giữ rõ là phát triển riêng tư; blocked luôn chặn.

Canonical available_at là lúc nhập thật, không phải lúc bài được xuất bản. Receipt là lịch sử, không phải trạng thái đủ điều kiện hiện tại. GET danh sách trả ingestion_status: not_ingested / recorded_not_impact_eligible / withheld / superseded. Approval revoked, nguồn đổi hoặc source blocked sẽ withheld; không xóa lịch sử hay tự phục hồi phiên bản cũ. Bộ đọc canonical as-of được mô tả bên dưới; chưa chiếu impact feed. Feed/graph eligibility vẫn false, materiality UNKNOWN và không có thông báo thật.

## Giao diện nhập và snapshot theo thời điểm

Tại /news-review, sau khi chuẩn bị intake, chọn sự kiện mới / bài trùng / bản sửa. Với bài trùng hoặc sửa, chọn claim đã nhập từ danh sách (tối đa100 claim gần nhất), hoặc nhập ID ngoài danh sách. Chọn bản gốc điền lại occurrence_window đã lưu; vẫn phải đối chiếu metric, kỳ và basis, ghi căn cứ và tự tích xác nhận. Máy chủ sẽ từ chối mục tiêu khác khóa hoặc đã bị thay thế. Mỗi lần thay đổi danh tính sẽ bỏ tích xác nhận. Nếu nguồn hoặc phê duyệt đổi, chuẩn bị intake mới; giao diện không tự làm mới hash để ghi dưới một xác nhận cũ. Thông báo lỗi được hiển thị, nút ghi được khóa khi request đang chạy.

Admin có thể đọc snapshot với mốc ISO có múi giờ, ví dụ2026-11-22T10:00:00Z; để trống dùng hiện tại. API GET /api/v0/news-claims/canonical?as_of=...&limit=100 (giới hạn1–500). Thành viên/gateway không được đọc endpoint này. Không có migration mới; schema0015.

Bộ đọc chọn phiên bản canonical mới nhất đã available tại cutoff **trước** khi kiểm tra tính hợp lệ. Claim, approval, intake, receipt và revision nguồn phải tồn tại tại cutoff, đúng chuỗi thời gian, hash, danh tính và nội dung. Source revision được chọn từ lịch sử bất biến theo cutoff, không lấy payload hiện tại. Bản nguồn đổi nhưng chưa có correction hợp lệ tạo khoảng trống; bản mới bị thu hồi không làm bản cũ sống lại. Receipt duplicate không cứu bản canonical có primary claim đã mất hiệu lực. Một phê duyệt mới sau khi thu hồi không tự hợp thức hóa receipt cũ.

Kết quả có items, withheld với lý do, examined và truncated nếu vượt giới hạn. Truy vấn không ghi intake/receipt. **Snapshot lịch sử mô tả những gì hợp lệ ở thời điểm đó**, không xác nhận đủ điều kiện hôm nay: thu hồi sau cutoff không xóa trạng thái hợp lệ trước cutoff. Riêng rights_status chưa có lịch sử versioned; source đang blocked sẽ luôn bị loại ở mọi cutoff, được khai báo bằng CURRENT_BLOCK_OVERRIDES_HISTORICAL_SNAPSHOT. Không suy ra quyền thương mại từ pending hoặc approved của source trong luồng phát triển này.

Các tests dùng nguồn và phê duyệt tổng hợp trong DB riêng. Browser kiểm tra ghi mới/trùng/sửa và lỗi stale bằng request đã intercept, không gửi thao tác ghi đến DB thật. Tiếp theo mới nối snapshot hợp lệ vào feed thông tin với citation/thời điểm; graph và tác động vẫn cần kiểm chứng riêng.

## Feed thông tin riêng tư từ canonical news

Trang /news có khu vực Sự kiện đã kiểm duyệt trích đoạn, tách khỏi bài RSS chưa thẩm định. API GET /api/v0/news/reviewed yêu cầu tài khoản, trả trạng thái hiện tại (không hỗ trợ replay/as_of). Gateway chỉ mở GET endpoint này; API review/canonical operator vẫn đóng. Đây là inbox nguồn chung cho các tài khoản được cấp quyền, tương tự các bài RSS, chưa cá nhân hóa theo subscription.

Mỗi request chạy lại bộ kiểm tra snapshot ở thời điểm hiện tại. Trích đoạn, số liệu/unit/kỳ/basis, citation, source revision/hash, ngày đăng/nhận/nhập và khai báo loại người lập/người duyệt được đưa vào allowlist. Không trả author/reviewer ID, claim/review ID, uncertainties, rationale, occurrence identity, comparison_basis ghi tự do hoặc lý do withholding chi tiết. Không ghi thẻ cache vào DB: thu hồi/sửa nguồn/blocked sẽ loại ngay ở lần tải kế tiếp; bản sửa hợp lệ thay phiên bản cũ, duplicate không nhân thẻ.

Giao diện kiểm tra mỗi60 giây khi tab mở; đây không phải stream cập nhật tức thì. Khi tải lại hoặc lỗi, thẻ cũ bị xóa để không tiếp tục hiển thị như còn hợp lệ. Khi tab bị ẩn, xóa khu vực đã duyệt; khi quay lại thì tải mới. Nếu endpoint phần đã duyệt lỗi, các bài RSS vẫn tải bình thường. Logout xóa token và nội dung. Không lưu nội dung trong localStorage hoặc cho phép HTTP cache.

Giới hạn mặc định100, tối đa500 ứng viên canonical; UI xét200. examined/truncated/withheld_count mô tả phạm vi, không bảo đảm bao phủ toàn thị trường. Bộ lọc nguồn chỉ áp dụng bài RSS, khu vực đã duyệt xét toàn bộ nguồn. DEV_INFORMATIONAL_FEED=false trả enabled=false và danh sách trống. Thẻ luôn ghi tác động UNKNOWN, graph/impact eligibility false; đây không phải đánh giá nhân quả, khuyến nghị đầu tư hay xác nhận quyền thương mại. Chưa chiếu các news này lên bản đồ graph.

## Hồ sơ đối chiếu số liệu nền và bằng chứng tác động

Trong /news-review, quản trị viên đọc phiên bản nguồn, chọn công ty, rồi bấm Đối chiếu nguồn và số liệu nền. API GET /api/v0/news-claims/source/{item_id}/dossier?ticker=...&expected_payload_sha256=... chỉ dành cho admin local; gateway không mở. Nguồn được ghim bằng hash/version, công ty phải có tên rõ ràng trong title+summary và chronology hợp lệ. Dossier giữ UNVERIFIED_RSS; không tạo claim hay phê duyệt.

Financial/segment context dùng cutoff bằng lúc **nhận** tin. Chỉ lấy snapshot SEC đã available trước cutoff và vẫn hợp lệ ở hiện tại; snapshot mới thay thế sẽ làm context cũ bị loại, không lấp khoảng trống bằng số liệu tương lai. Đây là research context lúc hệ thống nhận tin, không phải khẳng định thị trường đã biết tại publication time. Trích đoạn, URL/hash và cutoff được giữ; dossier có hash bao gồm thời điểm tạo nên không phải ID ổn định qua các lần đọc.

Số liệu tài chính hiển thị cả hai kỳ, đơn vị, giá trị và hồ sơ SEC. Chi tiết JSON giữ provenance/JSON pointers và phân khúc. Giới hạn12 financial records,5 filings,20 segment records; truncated được công bố. Context không tự nối causal attribution, không dùng biến động giá cổ phiếu làm numerator doanh thu và không tính tỷ lệ phơi nhiễm khi thiếu denominator tương thích.

Blockers luôn giữ yêu cầu claim/review, liên kết tin→chỉ tiêu, numerator/denominator cùng kỳ/phạm vi/đơn vị, bằng chứng nhân quả/counterfactual và đường quan hệ đã xác minh. Có đủ số liệu nền không làm materiality/causality thành verified. Chưa có auto-promotion lên feed hoặc map từ dossier.

Đợt kiểm tra22Nov:135 mục nguồn →7 cặp bài/công ty khác nhau theo URL, đều NVDA. Hồ sơ riêng tư trong source-cache/news-dossiers; báo cáo public chỉ aggregate tại reports/news-dossier-runtime.json.56 lượt financial context và28 lượt segment context tính trên7 hồ sơ, có số liệu nền lặp lại giữa hồ sơ; không phải56/28 bằng chứng độc lập.0 impact-ready,0 claim/review được tạo. Nội dung RSS vẫn chưa được thẩm định độc lập.

## Thẩm định tỷ trọng doanh thu phân khúc (schema0016)

Claim đã được nhập canonical và vẫn là primary version hiện hành có nút Thẩm định tỷ trọng phân khúc. Thành viên chỉ truy cập claim của mình; admin xem được toàn bộ. Bước này chưa mở qua gateway.

Candidate pair ghim toàn bộ hai bản ghi SEC bằng hash: doanh thu reportable segment / doanh thu consolidated cùng ticker, accession, concept, unit, duration, start/end và source identity. Chấp nhận một StatementBusinessSegmentsAxis, có thể kèm đúng ConsolidationItemsAxis=OperatingSegmentsMember theo parser SEC; loại nhóm geography/product/chiều bổ sung. Không tự đổi tiền tệ, scale hay gộp concept alias. Chỉ nhận0≤numerator≤denominator và denominator>0, số hữu hạn. Percent làm tròn4 chữ số thập phân. Không cộng các segment shares vì có thể có intersegment/elimination.

Đây là BASELINE_SEGMENT_REVENUE_SHARE, không phải affected revenue fraction, ước lượng thiệt hại, materiality hay tác động giá. Người lập ghi căn cứ tin liên quan phân khúc và giới hạn; actor_kind được khai báo rõ. Bản nháp bất biến giữ pair, event version và input hash. Hai nguồn vẫn phải có sẵn trước news capture và còn hợp lệ hiện tại.

Quản trị viên khác tài khoản người lập duyệt/từ chối; approval bắt buộc xác nhận kỳ/đơn vị/phạm vi, xem xét căn cứ liên quan đến tin, và tỷ trọng nền không phải hiệu ứng do tin gây ra. Có expected review version và revoke append-only. Account independence không chứng minh hai con người độc lập. Approval không xác minh nhân quả, không tạo score, không chuyển graph/feed/map. Nếu canonical claim hoặc source bị thu hồi/sửa, evidence pair đổi hoặc hash không đúng, draft không còn hợp lệ để phê duyệt. Reload kiểm tra lại và trả stale; toàn bộ claim mất hiệu lực sẽ chặn endpoint.

API: GET/POST /api/v0/news-claims/{claim_id}/exposure; POST /api/v0/news-claims/exposure/{draft_id}/reviews. POST draft cần Idempotency-Key; review dùng expected_version, không trả approval cũ từ cache. Các ghi chú giữ riêng theo quyền author/admin; chưa có public projection hoặc as-of exposure reader.

Kiểm tra actual corpus:7 dossiers chứa14 lần xuất hiện của2 cặp baseline khác nhau. Đây là các cặp có thể đối chiếu số học, chưa có phê duyệt exposure thật. Cần claim/news linkage có nguồn và thẩm định độc lập trước khi đưa kết quả vào feed/map; materiality vẫn UNKNOWN.

## Hiển thị tỷ trọng đã duyệt trên feed và bản đồ

Feed /news gắn baseline_shares vào đúng event version; /map trả baseline_exposure ở lớp thông tin riêng. Tỷ trọng không thêm node/edge vào causal graph và không đổi scenario matcher. Bản đồ có thanh0–100% kèm phân khúc, kỳ, tử số/mẫu số, loại người duyệt, thời điểm duyệt và liên kết/hash/locator nguồn. Không cộng các tỷ trọng hay coi chúng là xác suất.

Projection yêu cầu quyết định mới nhất hiện tại là approved, reviewer khác author, đủ3 confirmations và chronology hợp lệ. Kiểm tra lại input hash, primary canonical news, phê duyệt news, current source và cặp số liệu SEC. Bằng chứng đổi, claim sửa/rút hoặc exposure revoke đều làm tỷ trọng biến mất ở lần tải kế tiếp. Nhiều bản nháp đã duyệt cùng event version/pair chỉ hiển thị một lần. Tối đa500 draft candidates, có examined/truncated; có thể có approval cũ ngoài giới hạn này.

Với cutoff trên map, chỉ hiển thị approval đã ghi trước cutoff **và còn hợp lệ hiện tại**: CURRENT_VALID_APPROVAL_RECORDED_BY_CUTOFF. Đây không phải tái dựng lịch sử approval hoàn chỉnh. Quyết định thu hồi sau cutoff vẫn loại dữ liệu; phê duyệt mới sau cutoff không được đưa ngược về quá khứ. Actor/private draft IDs, rationale/limitations và danh tính tài khoản không xuất hiện trong shared projection; chỉ giữ actor-kind declaration và source-backed operand allowlist.

Map/feed kiểm tra lại mỗi60 giây khi visible. Khi refresh/tab hide/logout, dữ liệu tỷ trọng cũ bị xóa; lỗi tải không giữ nhãn đã duyệt cũ. Map chỉ làm mới lớp tỷ trọng trong nền, không thay đồ thị/kịch bản đang xem. Khi vừa chạy mô phỏng hoặc đổi bộ lọc, response không còn đúng phiên bản UI bị bỏ qua. Không mở thêm gateway write routes, không bật thông báo hoặc Cloudflare tunnel. Corpus thật vẫn0 approvals, nên chưa có tỷ trọng thật được công bố.
