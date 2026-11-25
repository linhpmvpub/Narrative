# Đồng bộ phiên bản nguồn RSS vào R05

Mục tiêu sản phẩm: tin liên quan đến công ty/narrative phải truy được nguồn và đường quan hệ;
bản duyệt cũ không còn được dùng khi ingestion đã ghi nhận nội dung mới. Đây là kiểm soát chung
cho database quan hệ, không phải chỉnh từ khóa từng bài hoặc dự báo giá cổ phiếu.

## Phạm vi triển khai — 2026-11-25

`engine.scope_sources` đọc trực tiếp `rie_news_items`, `rie_news_revisions`, `rie_news_sources`.
Chỉ hỗ trợ nguồn RSS trong v1. Không thêm bảng hay tác vụ nền; không tải nguồn lên cloud.

| Quy tắc | Hành vi |
|---|---|
| ID revision, payload và thời điểm nhận khớp selection | Sai hoặc thiếu: dừng đánh giá |
| Lịch sử liên tục, thời gian không đảo/ngày tương lai, item khớp revision mới nhất | Sai: dừng; không phỏng đoán CURRENT |
| Revision selection không còn mới nhất | Append source epoch DISPUTED, bản duyệt cũ không còn hiệu lực |
| Nội dung đổi rồi đổi về | Các ID/version vẫn khác; không khôi phục bản duyệt cũ |
| Không thay đổi trạng thái/packet/lịch sử | Không append epoch chỉ vì chạy lại hay poll thành công |
| Nguồn tắt, lần poll mới nhất lỗi, chưa poll thành công, last_success ở tương lai hoặc cũ hơn 3.600 giây | R05 UNKNOWN; không tạo epoch chỉ vì outage tạm thời |
| Nguồn đã WITHDRAWN/DISPUTED | Poll không tự chuyển về CURRENT |
| Đã gắn registry hash | Không thể bỏ binding bằng append bản source thiếu registry hash; đánh giá cần DB hiện tại |
| Registry đổi trong hai lần kiểm tra | R05 UNKNOWN; ledger vẫn được kiểm tra trước/sau như trước |

3.600 giây là ngưỡng vận hành bảo thủ ban đầu, **không phải hệ số tác động đã hiệu chỉnh**.
Thông tin mới nhất được kiểm tra ở thời điểm đánh giá; đây chưa phải historical as-of replay.
Receipt gắn source identity, item và lịch sử ID/version/payload/time. Source epoch mới bắt buộc
lập đề xuất/phiếu duyệt mới. Tạm mất độ mới poll chỉ giữ kết quả; khi poll hồi phục, bản duyệt
chưa hết hạn có thể dùng lại nếu revision và nguồn không đổi.

## Cách dùng

Trước khi lập đề xuất R05, đồng bộ vào store đã khởi tạo:

```powershell
python -m engine.scope_sources --store source-cache/reviews.sqlite --selection source-cache/selection.json --articles source-cache/articles
```

Lệnh kiểm tra packet đã capture rồi đọc DB từ `DATABASE_URL`, append khi cần. Không tự tạo
phiếu duyệt. Lấy source_epoch mới nhất bằng `engine.scope_review history`, chuẩn bị đề xuất
và hai phiếu như hướng dẫn [R05](scope-review-v1.md).

Thêm `--news-current` vào `engine.mechanism_playbook evaluate` cùng ba tham số
`--scope-store`, `--scope-reviews`, `--reviewer-policy`. Workbench tự đồng bộ trước R05,
kiểm tra freshness và đọc lại registry sau khi kiểm tra các đường. Trace xuất
`source_lifecycle` với căn cứ, latest_revision_id, registry hash và ngưỡng freshness.

Chế độ manual cũ vẫn phục vụ nghiên cứu offline, ghi rõ `MANUAL_LOCAL_RESEARCH_ONLY`.
Binding đã thiết lập không được chạy thiếu kết nối DB để vượt R05. Store và DB đều là
trusted local operator state; không có API hoặc chứng thực từ nhà xuất bản mới.

## Những điều chưa được chứng minh

- Poll RSS gần đây không chứng minh full article còn nguyên hoặc bài đang hiện diện trong feed.
  Bài biến mất khỏi RSS không đồng nghĩa bị rút. RSS title/summary mới là đơn vị revision hiện có.
- Ingestion RSS chưa có giao dịch xác nhận publisher withdrawal riêng. Thu hồi vẫn qua sổ
  operator hiện tại; bridge bảo toàn quyết định đó, chưa tự phát hiện/rút bài trên internet.
- Chưa có transaction phân tán giữa DB ingestion và SQLite ledger. Hai lần đọc phát hiện nhiều
  trường hợp thay đổi đồng thời, nhưng không phải khóa end-to-end cho gửi thông báo. Trước tích
  hợp feed cần kiểm tra tại thời điểm sử dụng và cơ chế invalidation bền vững.
- Mốc xảy ra/công bố/hiệu lực của EventFrame chưa tách đầy đủ; freshness ở đây chỉ là thu thập.
  Không biến tin lịch sử thành sự kiện hiện tại. R07, magnitude/horizon vẫn UNKNOWN.
- Chưa tăng số quan hệ có nguồn, recall hay độ đúng đánh giá trên tin thật. Tests và demo đều
  synthetic; hai phiếu fixture không phải nhãn độc lập.

## Hướng phát triển bám mục tiêu sản phẩm

1. Bổ sung capture/revalidation toàn văn và withdrawal có bằng chứng; giữ khác biệt giữa
   correction, disappearance, fetch error và confirmed withdrawal. Test cả quá trình mất/kết nối lại.
2. Ưu tiên điền dữ liệu quan hệ thật theo cơ chế: đầu vào → sản phẩm/phân khúc → công ty → narrative,
   gồm tỷ trọng/đơn vị/kỳ, tồn kho, nguồn thay thế và chuyển giá. Dùng trạng thái UNKNOWN cho chỗ thiếu.
   Xây ma trận phạm vi bắt buộc/có điều kiện/không áp dụng theo từng cơ chế: không ép tin giá hàng hóa
   toàn thị trường phải có một nhà máy cụ thể. “Tin có liên quan” và “tác động đã xác minh/định lượng”
   cần tiêu chí riêng; thiếu độ lớn không tự động loại bỏ mọi tin bối cảnh hữu ích.
3. Tách thời điểm sự kiện, điều kiện tác động và kênh truyền; thẻ tin/map phải hiển thị nguồn,
   lý do liên quan, phạm vi và phần chưa xác minh, không hứa dự báo giá.
4. Đóng băng database/rule version, đánh giá các nhóm tin mới bằng nhãn độc lập. Đo đúng/sót/sai
   phạm vi và chất lượng ưu tiên; chỉ chỉnh quy tắc/weights chung sau khi có kết quả. Không vá từng bài.

Tiêu chí trước feed thật: không dùng bản duyệt đã supersede/withdraw, không lẫn tin cũ thành hiện tại,
và mỗi thẻ giải thích được đường quan hệ cùng căn cứ còn thiếu. Thông báo thật tiếp tục tắt.
