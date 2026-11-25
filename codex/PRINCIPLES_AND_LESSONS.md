# Nguyên tắc và bài học phát triển

Cập nhật: 2026-11-25. Sổ kiến thức sống, được rà soát sau mỗi task; không phải mọi quan sát đều
là quy luật. Mục tiêu gốc nằm trong [PRODUCT_DIRECTION](PRODUCT_DIRECTION.md).

## Nguyên tắc ổn định

1. **Database có nguồn trước.** Pháp nhân, sản phẩm, quan hệ, phạm vi, kỳ và nguồn phải rõ trước
   khi ghép tin/định lượng. SNDK không phải WDC; cùng thương hiệu/tên gần nhau không chứng minh cùng pháp nhân.
2. **Phân biệt bằng chứng và kết luận.** Đồng xuất hiện tên, đường graph, trích dẫn đúng chữ hoặc
   hai phiếu duyệt chưa chứng minh nhân quả. Kế hoạch/cam kết không phải hoạt động/doanh thu thực hiện.
3. **Thiếu khác với bằng không.** UNKNOWN, NOT_APPLICABLE có căn cứ, chưa công bố, mâu thuẫn và
   đã bị thay thế phải khác nhau; không suy ra một tỷ lệ từ mô tả định tính.
4. **Phạm vi theo cơ chế.** Tin giá hàng hóa rộng và gián đoạn một cơ sở cần điều kiện khác nhau.
   Không bịa facility để đủ năm trường; không dùng thiếu magnitude để loại mọi tin bối cảnh.
5. **Thời gian và phiên bản là dữ liệu.** Tách xảy ra/công bố/thu thập/biết/hiệu lực/thẩm định.
   Replay chỉ dùng điều đã biết lúc đó; hiện trạng hồ sơ không được giả làm lịch sử as-of.
6. **Sửa lỗi tổng quát.** Tìm lớp lỗi trong ontology, dữ liệu, phạm vi, trích xuất, thời gian, xếp hạng
   hoặc giao diện. Sửa theo lớp và kiểm tra ca phản ví dụ, không vá từng headline để vượt benchmark.
7. **Đánh giá không rò rỉ.** Freeze trước gán nhãn, chia theo cụm sự kiện/kỳ, giữ riêng development/
   calibration/holdout. Tập đã xem trở thành regression. AI labels không phải human gold;
   nhiều bài cùng nguồn không thành nhiều xác nhận độc lập.
8. **Tối ưu hữu ích cho người dùng.** Coverage, precision, recall, giải thích và ưu tiên đều quan trọng.
   Lượt sửa hạ tầng phải phục vụ rủi ro cụ thể; không coi thêm công cụ/kiểm tra là hoàn thiện sản phẩm.
9. **Đo đúng điều đã làm.** Tests chứng minh hành vi phần mềm trong phạm vi test. Chỉ số thực nghiệm
   phải có cohort, mẫu số, mức unresolved và giới hạn; không biến pilot thành chất lượng toàn thị trường.
10. **Học có kiểm chứng.** Giữ kết quả thất bại, nguồn và phiên bản; supersede quyết định khi có bằng
    chứng mới. Không điều chỉnh target, đổi nhãn hoặc gộp cohort để làm đẹp số liệu.

## Sổ bài học đã tổng hợp

Ngày dưới đây là ngày ghi sổ. Bằng chứng chi tiết ở tài liệu liên kết; trạng thái “đã quan sát”
không có nghĩa đã giải quyết xong.

| ID / trạng thái | Quan sát và căn cứ | Quy tắc áp dụng / cách kiểm chứng |
|---|---|---|
| L001 · 2026-11-25 · định hướng người dùng | Nhiều lượt chỉnh ca nhỏ làm lệch ưu tiên database/bản đồ; [kế hoạch atlas](../docs/impact-atlas-plan.md) | Mỗi task nêu giá trị sản phẩm và lớp lỗi; đo theo nhóm tin trên nhiều công ty, không số bài được vá |
| L002 · 2026-11-25 · đã quan sát | Pilot trích xuất cũ có recall khoảng27–28%,25bất đồng chưa thẩm định; [benchmark](../docs/source-first-extraction-benchmark.md), checkpoint | Cải thiện lớp phát biểu/role/phase; cohort cũ chỉ regression, dùng cohort mới để đo tăng trưởng |
| L003 · 2026-11-25 · đã quan sát | RSS inbox có603items/771revisions/70items nhiều phiên bản tại lần audit; [báo cáo lifecycle](../reports/scope-source-lifecycle-progress.json) | Giữ ID/version và vô hiệu bản duyệt cũ; test sửa→đổi lại, retry và không churn epoch do poll lặp |
| L004 · 2026-11-25 · giới hạn thiết kế | Poll RSS mới không chứng minh toàn văn còn nguyên; mất bài không chứng minh rút; [lifecycle](../docs/scope-source-lifecycle.md) | Phân biệt freshness, lỗi fetch, disappearance, correction, confirmed withdrawal; cần revalidation toàn văn |
| L005 · 2026-11-25 · giới hạn thiết kế | R05 đòi cùng năm facet có thể giữ quá nhiều tin giá/nhu cầu rộng; [quality review](QUALITY_REVIEW.md) | Cần ma trận scope theo cơ chế. Đây là rủi ro đã nhận diện, CHƯA đo được mức recall bị mất; dùng ca rộng và near-miss để kiểm chứng |
| L006 · 2026-11-25 · đã kiểm chứng bằng synthetic | R05PASS không đủ R06/R07; nguồn rút làm bản duyệt cũ mất hiệu lực; [R05](../docs/scope-review-v1.md) | Test các tầng riêng; không biến source integrity hoặc local reviewer IDs thành causal proof/nhãn độc lập |
| L007 · 2026-11-25 · giới hạn dữ liệu | Tỷ trọng doanh thu, tồn kho, chuyển giá chỉ có nghĩa trong phạm vi/mẫu số/kỳ; [financial context](../docs/atlas-financial-context.md) | Kiểm tra đơn vị, segment, kỳ so sánh và thời điểm biết; không pooling tham số giữa quan hệ khác nhau |
| L008 · 2026-11-25 · giới hạn đánh giá | Nhiều bài/pair cùng sự kiện tương quan; current-profile archive khác backtest; [acceptance](../docs/product-v1-acceptance.md) | Báo theo cụm/công ty/cơ chế và giữ riêng kiểu replay; số pair không phải số sự kiện độc lập |
| L009 · 2026-11-25 · đã quan sát | README/start guide còn gọi dự án là seed và phụ thuộc Threadnote dù định hướng đã đổi | Điểm vào rõ, một nguồn mục tiêu hiện hành, lịch sử được gắn nhãn; kiểm tra link và xung đột khi thay quyết định |
| L010 · 2026-11-25 · giới hạn vận hành | Hash chain không chống rollback toàn store; hai lần đọc không là distributed transaction; [lifecycle](../docs/scope-source-lifecycle.md) | Trước delivery cần kiểm tra tại thời điểm dùng/durable invalidation; không gọi local snapshot là bảo đảm gửi thật |
| L011 · 2026-11-25 · đã kiểm chứng bằng synthetic | Một tin có phạm vi bối cảnh đủ căn cứ vẫn có thể chưa xác minh truyền tác động; [context scope](../docs/mechanism-context-scope.md) tạo CONTEXT/card riêng, giữ R05/R07UNKNOWN | Phân tầng output/gates, không nới gate tác động để cứu recall. Missing khác NA có căn cứ. L005 được xử lý một phần về phần mềm, chưa chứng minh cải thiện recall trên tin thật |

## Cách bổ sung và sửa bài học

Sau task, hỏi: có lỗi tái diễn, giả định bị bác bỏ, hiểu biết mới về người dùng/dữ liệu hoặc
quy tắc giảm lỗi có tính tái sử dụng không? Nếu có, thêm ID tăng dần với:

```text
ID — ngày ghi — trạng thái: giả thuyết / đã quan sát / đã kiểm chứng / bị thay thế
Quan sát: điều thực sự xảy ra; phân biệt synthetic và dữ liệu thật.
Bằng chứng: đường dẫn artifact/test/cohort/commit; chi tiết nhạy cảm để cục bộ.
Bài học: quy tắc tổng quát, phạm vi áp dụng và ngoại lệ.
Thay đổi đề xuất: dữ liệu, rule, workflow hoặc UX nào cần sửa.
Kiểm chứng: ca dương/âm, chỉ số và điều kiện bác bỏ bài học.
Liên kết: task/QUALITY_REVIEW; ID bị thay thế nếu có.
```

Gộp bài học trùng bằng liên kết; không ghi một quy tắc mới cho từng bài tin. Giữ ID cũ và đánh
dấu superseded kèm lý do khi bị bác bỏ. Chỉ nâng giả thuyết thành nguyên tắc ổn định khi có bằng
chứng hoặc quyết định rõ của người dùng. Không có bài học mới thì ghi “đã rà soát, không bổ sung”.
Rà soát định kỳ theo mốc phát triển, không tự tạo scheduler hay gửi thông báo vì yêu cầu này.
