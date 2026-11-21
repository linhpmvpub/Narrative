# Đợt gán nhãn độc lập 204 ca

**Điều chỉnh theo yêu cầu mới:** đợt hiện tại chạy mô phỏng bằng ba agent (nhà đầu tư cá nhân, nhà quản lý quỹ, chuyên gia tài chính). Xem [quy trình AI mô phỏng](ai-review-pilot-vi.md). Ba tài khoản dưới đây đã chuẩn bị nhưng chưa bàn giao cho người thật; agent dùng tệp nguồn riêng, không được cấp token và không nhập kết quả vào kho nhãn người thật. Phần hướng dẫn thao tác bằng tài khoản được giữ cho một đợt kiểm chứng bởi con người sau này.

## Đã chuẩn bị

Hai tài khoản người đánh giá **A** và **B**, mỗi người được phân công **toàn bộ204 ca** (132 đoạn văn,72 so sánh chỉ tiêu). Tổng cộng cần **408 nhãn độc lập**, không chia mỗi người102 ca. Tài khoản thứ ba chỉ thẩm định bộ này, không có quyền quản trị chung, không được gán nhãn vòng đầu và không được xuất toàn bộ dữ liệu nhãn.

Ba tài khoản hiện là các vị trí chờ bàn giao cho ba người thật. Chưa có tên/email được xác nhận, chưa gửi thông tin đăng nhập và chưa tạo nhãn thay người. Người điều phối xác nhận ba người khác nhau trước khi giao mã. Lưu tên/email và ngày bàn giao trong hồ sơ riêng dưới `secrets/annotation-campaign-204/`, không đưa lên GitHub. Không dùng chung tài khoản hoặc mã truy cập.

| Vai trò | Tệp mã truy cập trên máy dự án | Trang thao tác |
|---|---|---|
| Người đánh giá A | `secrets/annotation-campaign-204/reviewer_a.txt` | http://127.0.0.1:8888/label |
| Người đánh giá B | `secrets/annotation-campaign-204/reviewer_b.txt` | http://127.0.0.1:8888/label |
| Người thẩm định | `secrets/annotation-campaign-204/adjudicator.txt` | http://127.0.0.1:8888/adjudicate |

Mỗi tệp chỉ chứa mã của một người. Người điều phối giao riêng đúng tệp, không giao cả thư mục hoặc manifest. Không dán mã vào chat, URL, ảnh chụp, GitHub hay tài liệu dùng chung. Mã hết hạn sau30 ngày; thời điểm chính xác ở manifest riêng. Đăng xuất sau mỗi phiên, nhất là khi dùng chung máy. Không xem đáp án thuật toán hoặc nhãn người khác trước khi hoàn thành đánh giá độc lập.

Các URL127.0.0.1 chỉ dùng trên máy chạy dự án. Truy cập từ xa hiện vẫn qua Cloudflare giới hạn email đã được cho phép; chưa mở thêm email cho người tham gia. Người thẩm định dùng máy dự án vì gateway chặn trang/API thẩm định. Có thể thực hiện ba phiên riêng trên cùng máy với ba người thật. Không dùng mã quản trị toàn hệ thống cho người thẩm định. Tài khoản xem feed cũ vẫn xem feed/bản đồ nhưng không còn phân công gán nhãn đợt này.

## Người đánh giá A và B thao tác

1. Mở `/label`, nhập mã riêng và chọn bộ204 ca. Không nhập email vào ô mã truy cập. Chọn bộ lọc **Chưa gán nhãn** để tiếp tục phần chưa làm.
2. Đọc đoạn văn hoặc mở hồ sơ nguồn, đối chiếu URL, mã hồ sơ, hash nguồn và vị trí fact/context. Nếu hồ sơ trực tuyến khác bản đóng băng, ghi nhận vấn đề cho người điều phối; không tự suy ra số thay thế.
3. Với đoạn văn, chọn đúng loại: doanh nghiệp giải thích nguyên nhân đã xảy ra; thông tin có điều kiện/hướng tới tương lai; hoặc không có khẳng định nguyên nhân. Phân biệt doanh nghiệp nói “do nhu cầu tăng” với chứng minh nhân quả bằng nguồn độc lập. Dự báo hoặc kế hoạch không được gán thành kết quả đã xảy ra.
4. Với chỉ tiêu phân khúc, tự đọc giá trị, đơn vị, hệ số scale, kỳ hiện tại/kỳ so sánh và phân khúc. Nếu so sánh được, nhập hai giá trị đã quy đổi USD và bốn ngày đầu/cuối kỳ. Không tự gán số hợp nhất cho phân khúc; không suy ra biên lợi nhuận từ doanh thu. Nếu khác kỳ, khác phạm vi, trình bày lại không rõ hoặc thiếu bằng chứng, chọn **không thể so sánh** hoặc **chưa đủ bằng chứng** và giải thích.
5. Viết lý do đủ cụ thể để người khác kiểm tra lại: đoạn/fact nào, kỳ nào, điểm còn mơ hồ. Tích xác nhận độc lập chỉ khi đã tự đối chiếu. Lưu nhãn và chờ thông báo lưu thành công.
6. Nếu phát hiện sai, sửa nhãn của chính mình. Hệ thống giữ lịch sử; mỗi người vẫn chỉ được tính một phiếu mới nhất. Khi gặp lỗi409, tải lại ca và đối chiếu phiên bản/nguồn trước khi gửi lại. Nguồn đã sửa/rút có thể chặn gán nhãn và cần bộ ca thay thế.

Gợi ý chia17 phiên, mỗi phiên12 ca cho mỗi người. Sau12 ca đầu, điều phối chỉ kiểm tra việc lưu, quyền truy cập, thao tác và độ đầy đủ của lý do; không trao đổi đáp án của các ca đang dùng để đánh giá độc lập. Không cần đạt tốc độ cố định; ưu tiên đọc nguồn đúng. Các ví dụ huấn luyện có đáp án phải nằm ngoài bộ204 ca này.

## Người thẩm định thao tác

1. Dùng mã thẩm định riêng tại `/adjudicate`. Mặc định chỉ hiện ca bất đồng hoặc đã hoãn. Không có ca nào là bình thường khi chưa đủ hai nhãn.
2. Đọc lại nguồn trước khi đọc lý do của từng bên; kiểm tra cách phân loại, số, scale, kỳ và phạm vi phân khúc. Không chọn theo đa số hoặc theo kết quả thuật toán.
3. Nếu đủ bằng chứng, chọn **Chốt nhãn tham chiếu**, tự nhập kết luận và giải thích vì sao. Nếu chưa đủ, chọn **Chưa đủ căn cứ — hoãn**; không tạo nhãn tham chiếu để lấp đầy tiến độ.
4. Tích xác nhận độc lập và lưu. Khi người đánh giá sửa nhãn hoặc nguồn đổi, quyết định cũ có thể hết hiệu lực; thẩm định lại trên phiên bản mới. Nếu409, tải lại trước khi quyết định.

Đồng thuận và thẩm định không tự xác minh quan hệ trong graph, không thay đổi feed và không gửi thông báo thật.

## Người điều phối theo dõi

Mở `/adjudicate` bằng tài khoản thẩm định hoặc tài khoản quản trị hiện có, bấm **Cập nhật báo cáo**. Đây là bảng tiến độ theo yêu cầu, không có lịch nhắc/gửi thông báo tự động.

- Mỗi người: số ca đã gửi, số ca còn hiệu lực, số cần làm và số đang chờ nguồn. Sửa cùng một ca không tăng số ca hoàn thành. API/CLI còn cung cấp thời điểm lưu gần nhất và số hoàn thành theo loại ca.
- Toàn bộ đợt: số ca có hai phiếu, bất đồng chưa xử lý, số thẩm định hết hiệu lực, đồng thuận/chốt nhãn/hoãn và ca bị loại do nguồn.
- Chất lượng: độ phủ của75 ca holdout (60 văn bản,15 chỉ tiêu), tỷ lệ đồng thuận ban đầu và điểm sau khi có nhãn tham chiếu. Chưa có nhãn thì điểm lànull; không phải0% chính xác.

Kiểm tra mỗi khi kết thúc một phiên gán nhãn. Đợt có thể chuyển sang phân tích khi tất cả ca nguồn hợp lệ có hai phiếu và mọi bất đồng đã được chốt hoặc ghi rõ lý do hoãn. Ca hoãn/nguồn lỗi phải xuất hiện trong mẫu số và báo cáo tồn đọng; không giấu chúng để làm đẹp điểm. Chỉ quản trị gốc được xuất lịch sử đầy đủ; lưu xuất riêng dưới source-cache, không commit nhãn thật.

## Lệnh vận hành

```powershell
$env:DATABASE_URL='sqlite:///rie-dev-feed.db'
$env:DEV_INFORMATIONAL_FEED='true'
$env:SEND_NOTIFICATIONS='false'
$env:ALLOW_SYNTHETIC_LIVE='false'
$env:LLM_MODE='none'
.venv/Scripts/python -m engine.evaluation.campaign --packet 526bd6298883375e06874ca83a78069104f1411ad5e103455f0c357d5b70ac9f
```

Lệnh trên chỉ đọc tiến độ. Việc thiết lập đã thực hiện bằng `--prepare secrets/annotation-campaign-204`; chạy lại với cùng bộ/thư mục kiểm tra tính nhất quán, không tạo thêm tài khoản hay xoay mã. Nếu mã hết hạn/bị thu hồi/mất tệp, cần thao tác gia hạn/đổi mã có chủ đích của người quản trị; không tạo tài khoản mới thay một người đã có nhãn. Sau lỗi ghi tệp khi thiết lập, giao dịch DB rollback; thư mục riêng có thể còn tệp chưa dùng và cần người vận hành kiểm tra trước khi thử lại.

Tiếp theo: xác nhận người nhận cho ba vai trò, bàn giao riêng mã, thực hiện12 ca đầu mỗi người, kiểm tra tiến độ rồi hoàn thành các phiên còn lại. Dữ liệu kỳ mới và ca chỉ tiêu bị bỏ sót vẫn cần cho đánh giá khả năng khái quát sau đợt này.
