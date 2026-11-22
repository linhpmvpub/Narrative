# Đánh giá lịch sử cục bộ: 60 cụm công bố tài chính

## Phạm vi đợt v1

Đợt này kiểm tra cách engine đọc bằng chứng tài chính qua các hồ sơ SEC giai đoạn
2022–2025. Đơn vị cụm là doanh nghiệp/kỳ báo cáo, không phải từng đoạn văn. Tổng
60 cụm: MU17, AMD16, NVDA15, DELL8, SNDK4;180 đoạn (3 đoạn/cụm). Không bổ sung
WDC để giả lập lịch sử SNDK. Độ phủ theo doanh nghiệp không đồng đều do cửa sổ
submissions gần đây; chưa thu thập thêm trang submissions lưu trữ cũ của DELL.

Một 10-Q/10-K được coi là cụm thông tin của kỳ, không khẳng định mỗi đoạn là một
sự kiện kinh tế mới. Bản sửa trong metadata được gắn cùng kỳ; các bản sửa không
được dùng để ghi đè hồ sơ ban đầu. Chưa kiểm thử đầy đủ phản ứng trước hồ sơ sửa.

Lấy ba nhóm đoạn theo quy tắc định trước: thay đổi tài chính, rủi ro/phụ thuộc,
mô tả không có từ khóa thay đổi. Đây là tiêu chí lấy mẫu, không phải nhãn đúng.
Bao gồm đoạn khó, boilerplate và mô tả doanh nghiệp; không bảo đảm tỷ lệ lớp.
Lấy mẫu đoạn không thay cho đánh giá toàn văn hay phát hiện mọi tác động trọng yếu.

## Hai đồng hồ, hai chế độ

Ngày công bố/kỳ báo cáo phục vụ tái dựng lịch sử theo bản hồ sơ có accession SEC.
Ngày lấy dữ liệu vẫn là thời điểm thu thập thực tế năm2026. Không sửa `first_seen`
hoặc `available_at` của production thành ngày quá khứ. Đợt này có nhãn
`HISTORICAL_ARCHIVE_RECONSTRUCTION_AI`; không phải replay production cache-only.
Hash chứng minh tính toàn vẹn bản đã lấy, không chứng minh độc lập lịch sử máy chủ.
Metadata submissions hiện tại cũng có thể đã cập nhật; không giả lập độ trễ nhận tin.

Không có graph đã xác minh point-in-time cho các năm trước. Do đó đợt này không
chạy giả lập V0 push, không dựng quan hệ bằng kiến thức biết sau sự kiện, không
đưa cạnh AI vào graph chung. Push precision, two-hop recall và độ chính xác giá
cổ phiếu để `null`, không gán bằng độ chính xác phân loại câu.

## Khóa và gán nhãn mù

Chia theo thời gian:2022–2023 development25;2024 calibration16;2025 holdout19.
Hồ sơ H20 đã dùng phát triển bị loại trước thu thập. Cụm có đoạn trùng chính xác
giữa tập hoặc nhắc H20 được giữ trong mẫu đầy đủ nhưng loại khỏi tập con kiểm tra
sạch theo quy tắc đã khóa (13 cụm). “Sạch” chỉ theo các kiểm tra đó, không chứng
minh chưa nằm trong dữ liệu huấn luyện LLM hoặc không có boilerplate gần giống.

`freeze-receipt.json` khóa hash collection, blind packet và dự đoán shadow
v2.0.1 trước khi agent bắt đầu. Hash/count tổng hợp được commit và push trước
gán nhãn. Giữ nguyên classifier và tập kiểm tra trong suốt đợt này. Những thay
đổi evaluator sau freeze là kiểm tra toàn vẹn/thẩm định/thống kê, không thay dự đoán.

Ba agent có ngữ cảnh mới, lần lượt đóng vai nhà đầu tư cá nhân, quản lý quỹ và
chuyên gia tài chính; chỉ được đọc packet và nguồn cục bộ. Không xem classifier,
dự đoán, kết quả của nhau hoặc duyệt web. Mỗi người tự đọc180 đoạn, ghi nhãn,
trích dẫn chính xác, lý do và kiểm tra hash nguồn. Script chỉ chép các quyết định
đã đọc, không sinh nhãn bằng classifier. Việc tách này là quy trình, không phải
ACL hệ điều hành cô lập ba agent khỏi mọi file.

Mỗi đoạn nhận ba trường:

- `language`: ISSUER_ATTRIBUTION / UNCERTAIN_OR_FORWARD_LOOKING / NO_CAUSAL_CLAIM.
- `impact_sign`: POSITIVE / NEGATIVE / MIXED / UNKNOWN, theo hiệu quả tài chính
  doanh nghiệp được đoạn hỗ trợ; không phải dự báo giá cổ phiếu.
- `numeric_effect_supported`: có số tác động thực tế được gắn với nguyên nhân
  cụ thể; doanh thu tổng/so sánh đơn thuần hoặc vốn hóa không đủ.

Nếu vừa giải thích kết quả đã xảy ra vừa dự báo, ưu tiên giải thích kết quả,
sau đó triển vọng tài chính, rồi mô tả không nhân quả. Danh sách từ trong disclaimer
không tự là triển vọng tài chính có nội dung. Đây là rubric của nhãn, không lấy
theo đầu ra classifier. Hiện chỉ trường language có dự đoán khóa để chấm; hai
trường còn lại tạo tập tham chiếu cho phát triển tác động sau này.

Chuyên gia phải hoàn thành và khóa bản mù riêng trước khi đọc bất đồng. Sau đó
thẩm định tất cả bộ ba nhãn không nhất trí từ nguồn và phiếu đã khóa, vẫn không
xem dự đoán. Có thể `DEFERRED`; không ép có đáp án. Bộ thẩm định gắn hash phiếu,
quote nguồn và hash bản mù chuyên gia. Không được đổi phiếu ban đầu.

## Chạy lại bằng CLI

Từ repo, dùng một thư mục ignored mới cho mỗi đợt; các lệnh ghi độc quyền không
ghi đè hồ sơ đã khóa. Không chạy collect/freeze/evaluate đè lên đợt v1.

```powershell
python -m engine.evaluation.historical_replay collect --root source-cache/historical-replay-v2
python -m engine.evaluation.historical_replay freeze --root source-cache/historical-replay-v2
python -m engine.evaluation.historical_replay verify --root source-cache/historical-replay-v2
# Ba agent ghi retail_investor.json, fund_manager.json, financial_expert.json.
python -m engine.evaluation.historical_replay disagreements --root source-cache/historical-replay-v2
# Chuyên gia ghi adjudication.json sau khi khóa bản mù của mình.
python -m engine.evaluation.historical_replay evaluate --root source-cache/historical-replay-v2
```

Nguồn, packet, dự đoán, nhãn và so sánh từng ca nằm dưới
`source-cache/historical-replay-v1/`, không commit hoặc upload lên cloud. Chỉ
đẩy mã, tests tổng hợp giả lập, hash/count và báo cáo tổng hợp lên GitHub.
`text_sha256` là SHA256 canonical JSON của chuỗi, còn `source_sha256` là SHA256
bytes UTF-8 của hồ sơ. Không nhầm hai quy ước khi kiểm tra nguồn.

## Diễn giải kết quả và lộ trình sản phẩm

Tỷ lệ là mức khớp với tham chiếu AI, không phải độ chính xác đã xác nhận bằng
người hoặc bằng chứng nhân quả độc lập. Báo cả mẫu số, ca chưa giải quyết và
độ phủ. Khoảng95% bootstrap lấy lại mẫu theo cụm doanh nghiệp/kỳ,2000 lần, seed
cố định; vẫn chưa loại được phụ thuộc giữa các kỳ cùng doanh nghiệp và mô hình.
LLM có thể nhớ kết quả quá khứ dù không thấy dự đoán engine. Luồng prospective
đã khóa tiếp tục riêng, không thay protocol để đưa dữ liệu cũ vào.

Ước tính triển khai có điều kiện, không phải cam kết: với5 mã, nguồn SEC/IR/RSS
hiện tại và phạm vi cố định,2–4 tuần làm việc cho thử nghiệm riêng của bản đồ và
gợi ý tin;6–10 tuần để thử nghiệm push giới hạn sau khi các gate chất lượng đạt.
Không suy rộng thành bao phủ toàn thị trường. Dữ liệu lịch sử giúp bỏ thời gian
chờ tích lũy ca nhưng không bỏ công thẩm định quan hệ, đo cảnh báo sai và vận hành.

Các mốc phải đạt trước push:

1. Sửa lỗi đọc bằng chứng trên tập phát triển; kiểm tra bằng một tập chưa mở mới.
2. Bổ sung ca định lượng và quan hệ một/hai bước có nguồn, thời gian hiệu lực,
   phản chứng, phân khúc; xác định đúng lúc UNKNOWN, không dùng tỷ trọng nền làm
   hệ số tác động. Thêm tin ngoài báo cáo tài chính và ca sửa/rút/reprint.
3. Chạy feed/digest shadow theo watchlist, đo cảnh báo sai, mức tin trùng và việc
   bỏ sót tin trọng yếu theo người dùng; thống nhất ngưỡng phát hành dựa trên mẫu số.
4. Kiểm tra bảo mật/vận hành, nguồn, lịch chạy và chi phí; sau đó mới xin bật
   push giới hạn. Trong đợt hiện tại SEND_NOTIFICATIONS=false.
