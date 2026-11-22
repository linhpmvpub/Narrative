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

API local operator: POST `/api/v0/news-claims/{id}/ingest`. Chỉ dùng DB production riêng và `DEV_INFORMATIONAL_FEED=true`; gateway vẫn chặn. Bước này hiện dùng API, chưa có nút nhập trên giao diện. Body:

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

Canonical available_at là lúc nhập thật, không phải lúc bài được xuất bản. Receipt là lịch sử, không phải trạng thái đủ điều kiện hiện tại. GET danh sách trả ingestion_status: not_ingested / recorded_not_impact_eligible / withheld / superseded. Approval revoked, nguồn đổi hoặc source blocked sẽ withheld; không xóa lịch sử hay tự phục hồi phiên bản cũ. Chưa có bộ đọc news canonical as-of hoặc chiếu impact feed: các consumer tương lai phải kiểm tra lại review/nguồn tại cutoff trước khi sử dụng. Feed/graph eligibility vẫn false, materiality UNKNOWN và không có thông báo thật.
