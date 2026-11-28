# Quy trình phát triển, tự đánh giá và cải thiện

## Nhiều bước trong một task — bổ sung 2026-11-28

Theo yêu cầu người dùng, sau mỗi bước thay đổi chức năng/database phải chạy benchmark,
đọc kết quả rồi mới chuyển sang bước tiếp theo. Giữ run riêng cho từng bước, cả phiên bản
thất bại/superseded; so sánh với bước ngay trước và tổng thể với baseline đầu task.
Không thay baseline để che regression tích lũy. Đổi profile có available_at mới thì ghi
mốc replay mới rõ ràng; các bước chỉ đổi code sau đó dùng cùng mốc để so sánh. Sau hardening
cuối vẫn chạy lại và quality_gate --all trước commit. Chi tiết nguồn/nhãn/predictions cục bộ.


## Benchmark sau mỗi update — quyết định 2026-11-28

Áp dụng [quality-benchmark](../docs/quality-benchmark.md): chốt suite/target/labels,
kiểm tra run trước, sửa framework/data, chạy tests và benchmark so với baseline,
đọc từng quyết định đổi rồi chạy quality_gate --all sau lần sửa runtime/database cuối.
Ghi phiên bản và kết quả theo nhóm trong QUALITY_REVIEW/CHECKPOINT, giữ lần thất bại.
Hook commit kiểm tra freshness cho engine/config; CI dùng synthetic vì corpus riêng
ở cục bộ. Đổi database vẫn cần chạy gate dù Git không thấy file ignore. Chỉ cập nhật
current-run pointer sau khi đánh giá; không sửa run cũ. Nhãn AI exposed không chứng minh
chất lượng holdout hoặc mức độ/thời hạn tác động tài chính. Không cần mở lại đánh giá
riêng priors. Khi thay target hoặc bổ sung nhãn/cohort, tạo suite phiên bản mới.


## Kiểm tra khả năng dùng chung — 2026-11-27

Trước khi thêm rule, xác định tầng lỗi và đối chiếu contract của crawler/revision, classification, graph, narrative, explanation, ranking hoặc delivery. Tên doanh nghiệp, sản phẩm riêng, quan hệ và nguồn thuộc data/config của hồ sơ; mã matcher chung không rẽ nhánh theo ticker/headline. Kiểm thử cùng phát biểu trên ít nhất hai hồ sơ synthetic đổi tên, thêm ca khác thị trường và trường hợp không có/đã rút quan hệ. Khóa runtime/profile/predictions trước nhãn của tập mới; không chỉnh theo nhãn holdout trong cùng lượt. Báo riêng độ liên quan theo narrative và coverage tin cấp công ty; chuyển tin sang narrative khác không được tính là cứu recall của target cũ.

## Giai đoạn đang thực hiện — 2026-11-26

Người dùng đã kích hoạt đánh giá tổng thể theo nhóm tin và hiệu chỉnh. Trình tự hoãn benchmark
ở mục2 bên dưới đã hoàn tất vai trò; đánh giá riêng priors vẫn hoãn. Freeze kế hoạch, mục tiêu,
phiên bản và predictions trước labels; tách hiệu chỉnh/kiểm tra theo cụm. Các bộ cũ đã lộ nhãn
chỉ là development regression dù được chia lại. Giữ riêng RSS/full-body/hồ sơ lưu trữ.

Cập nhật: 2026-11-25. Áp dụng theo [AGENTS](../AGENTS.md). Dùng quy trình vừa đủ cho task;
không biến việc nhỏ thành một đợt đánh giá thị trường hay thêm thủ tục phê duyệt không cần thiết.

## 1. Khởi đầu: hiểu mục tiêu và hiện trạng

Đọc PRODUCT_DIRECTION, PRINCIPLES_AND_LESSONS, tài liệu này, phần mới nhất CHECKPOINT/
QUALITY_REVIEW rồi tài liệu kỹ thuật liên quan. Kiểm tra worktree và bằng chứng hiện tại.
Không ghi đè thay đổi ngoài phạm vi. STATUS, P0–P5 và báo cáo cũ không thay checkpoint hiện hành.

Trước khi code, nêu ngắn gọn:

- Vấn đề người dùng hoặc rủi ro chất lượng cụ thể cần giải quyết.
- Liên hệ với hồ sơ/database, cơ chế, đánh giá nhóm tin hoặc trải nghiệm feed/map.
- Phạm vi đầu ra, điều kiện nghiệm thu và điều chưa làm trong task này khi cần phân định.
- Bằng chứng sẵn có, điều chưa biết và loại kiểm tra phù hợp.

Không cần xin xác nhận cho lựa chọn kỹ thuật thông thường đã được ủy quyền. Chỉ hỏi khi có
quyết định sản phẩm/quyền/chi phí không thể suy ra; tiếp tục phần độc lập trong lúc chờ.

## 2. Chọn việc có giá trị

Ưu tiên giai đoạn hiện hành (người dùng 2026-11-25): hoàn thiện khung database v1 gọn và thuật toán.
Hoãn đánh giá riêng tri thức LLM; benchmark toàn diện/vòng lặp cải thiện thực hiện sau khi nền tảng
sẵn sàng. Không tự mở đợt đánh giá chỉ vì checklist cũ đề xuất. Kiểm chứng phần mềm và nguồn vẫn làm.

Ưu tiên lỗi tạo khẳng định sai, nhầm pháp nhân/phạm vi/kỳ, dùng nguồn đã bị thay thế; sau đó
thiếu dữ liệu và bỏ sót có tính hệ thống. Cân nhắc độ hữu ích, phạm vi tác động, mức bằng chứng
và công sức; không tự gán điểm ROI giả định như số liệu đo được.

Nếu nhiều lượt chỉ thêm review/control mà coverage hoặc chất lượng tin không tiến bộ, đánh
giá lại ưu tiên: chọn dữ liệu quan hệ thật, quy tắc chung hoặc luồng đến thẻ tin. Không bỏ các
kiểm soát cần thiết để lấy số lượng; cũng không đòi đủ định lượng mới hiển thị mọi tin liên quan.

## 3. Triển khai có thể truy vết

- Tách dữ kiện có nguồn, reviewer interpretation, giả định và kết luận.
- Giữ version/as-of, nguồn và điều kiện; không sửa baseline/capture/nhãn đã khóa.
- Thay rule theo lớp lỗi; cần ca âm tính/near-miss và trường hợp không đủ dữ liệu.
- Dữ liệu riêng tư nằm ở vùng ignore. Chỉ đẩy code/docs/fixture synthetic và aggregate phù hợp.
- Với thay đổi scoring/đánh giá, chốt target, cohort, exclusions, rule/database version trước khi xem nhãn.

## 4. Kiểm chứng theo loại thay đổi

| Loại task | Bằng chứng cần có |
|---|---|
| Chỉ tài liệu | Link nội bộ tồn tại, thứ tự đọc và nguồn quyết định nhất quán, không mâu thuẫn status/legacy, diff không chứa dữ liệu riêng |
| Code/ingestion/lifecycle | Tests hành vi liên quan, failure/retry/correction/withdrawal khi phù hợp; lint/type và CI theo repository; không dùng DB thật làm test DB |
| Hồ sơ/dữ liệu quan hệ | Đối chiếu trích dẫn/hash, pháp nhân, đơn vị/mẫu số/kỳ, scope/hiệu lực, phát hiện mâu thuẫn; snapshot mới có receipt |
| Matcher/cơ chế/scoring | Regression + nhóm sự kiện mới phù hợp; freeze trước review; báo FP/FN/unresolved theo công ty/cơ chế và giới hạn |
| Feed/map/UX | Luồng thực tế nguồn→đường quan hệ→thẻ, nhãn uncertainty/synthetic, desktop/mobile nếu bị ảnh hưởng; không suy ra deploy thành công từ code |

Không thêm tests chỉ lặp lại implementation. Không chạy lại cả suite cho sửa văn bản thuần túy.
Khi CI bắt buộc hoặc đã chạy để nghiệm thu, kiểm tra đúng commit và kết quả từng job; báo rõ
test chưa chạy/thất bại/bị dừng, không trộn số liệu CI cũ vào thay đổi mới.

## 5. Tự rà soát trước khi kết thúc

Trả lời dựa trên bằng chứng, có thể ngắn với task nhỏ:

1. Thay đổi giúp nhà đầu tư hoặc database quan hệ tốt hơn ở điểm nào? Đã tới feed/map hay chỉ workbench?
2. Kết quả là software correctness, coverage, relevance accuracy, causal support hay usability?
3. Đang có nguy cơ nhầm identity/scope/period, ghép tên đơn thuần, rò rỉ nhãn, nguồn stale hay quá nhiều điều kiện làm mất tin hữu ích không?
4. Còn thiếu gì; mức ảnh hưởng và điều kiện áp dụng? Phân biệt đã quan sát với rủi ro chưa đo.
5. Cách khắc phục khả thi và kiểm tra nào có thể xác nhận/bác bỏ hiệu quả?
6. Task tiếp có giải quyết nút thắt giá trị sản phẩm lớn nhất không?

Với đo chất lượng thực nghiệm: ghi ngày/cohort, số cụm và mẫu số, positive/negative/unresolved,
reviewer kind/độc lập, split và phiên bản, metric theo nhóm, so sánh baseline cùng tập, giới hạn.
Không có đánh giá mới thì nói rõ chưa chứng minh accuracy tăng; không ngụ ý tests đạt là sản phẩm hoàn chỉnh.

## 6. Cập nhật trí nhớ dự án

| File | Trách nhiệm |
|---|---|
| PRODUCT_DIRECTION | Mục tiêu/phạm vi/ưu tiên lâu dài; đổi khi có quyết định rõ, không sao chép mọi test count |
| PRINCIPLES_AND_LESSONS | Bài học tái sử dụng có bằng chứng, trạng thái và cách kiểm chứng; giữ lịch sử bị thay thế |
| QUALITY_REVIEW | Rà soát theo lượt: thay đổi, bằng chứng, tồn tại, remedy, acceptance gate và ưu tiên |
| CHECKPOINT | Trạng thái mới nhất, commit/test/artifact, ràng buộc, việc còn lại và điểm bắt đầu phiên sau |
| TASKS và docs kỹ thuật | Checklist/contract liên quan; không đánh dấu nghiệm thu chỉ vì code đã được viết |

Không xóa lịch sử thất bại, không biến “đề xuất” thành “đã triển khai”. Nếu task chỉ sửa tài liệu,
ghi phạm vi đó và kiểm tra tài liệu đã làm; không phát sinh cohort/benchmark giả. Khi chưa có bài học
mới, ghi đã rà soát và không thêm. Khi đổi nguyên tắc, rà lại điểm vào/README để tránh hướng dẫn lệch.

Mẫu mục QUALITY_REVIEW cho lượt mới:

```text
Ngày / task / commit hoặc artifact:
Mục tiêu sản phẩm và thay đổi:
Kết quả kiểm chứng (loại bằng chứng, số liệu/mẫu số nếu có):
Tồn tại — đã quan sát hay giả thuyết — ảnh hưởng:
Khắc phục khả thi — tiêu chí kiểm chứng — ưu tiên:
Bài học mới/sửa đổi: ID hoặc “đã rà soát, không bổ sung”.
Bước tiếp và lý do ưu tiên:
Ràng buộc/rủi ro/quyết định cần người dùng (nếu có):
```

## 7. Bàn giao

Báo cụ thể đã làm, đã kiểm chứng, giới hạn/chưa đạt và bước tiếp; liên kết tài liệu khi hữu ích.
Nếu push trong phạm vi được cho phép, kiểm tra nội dung staged, push và đồng bộ HEAD/origin.
Sửa docs thuần túy có thể dùng `[skip ci]` sau kiểm tra tài liệu; không dùng nó để che thay đổi code
chưa được kiểm thử. Giữ dữ liệu cục bộ, live notifications tắt theo chỉ đạo hiện hành.

Việc cập nhật liên tục được thực hiện khi agent làm task và ở các mốc bàn giao, không phải tác vụ
nền tự chạy khi không có phiên làm việc. AGENTS.md là điểm vào để agent có hỗ trợ đọc hướng dẫn;
không khẳng định mọi công cụ bên ngoài tự động tuân thủ nếu chưa được cấu hình đọc repository.
