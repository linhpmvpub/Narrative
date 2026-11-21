# Đợt đánh giá bằng ba agent mô phỏng

Theo yêu cầu của người dùng, đợt204 ca đã chạy bằng ba agent riêng, không kế thừa lịch sử hội thoại của nhau:

| Agent | Vai trò | Công việc hoàn thành |
|---|---|---|
| A | Mô phỏng nhà đầu tư cá nhân | Đọc và gán nhãn độc lập204 ca |
| B | Mô phỏng nhà quản lý quỹ | Đọc và gán nhãn độc lập204 ca |
| C | Mô phỏng chuyên gia tài chính | Đối chiếu nguồn, thẩm định3 ca bất đồng |

Hai người gán nhãn nhận cùng đoạn nguồn và các fact/context/unit XML nguyên gốc, không nhận giá trị chuẩn hóa hay kết quả phân loại của thuật toán. Mỗi agent tự đọc132 đoạn văn và kiểm tra72 cặp chỉ tiêu. Vai trò thay đổi góc nhìn và cách giải thích, không ép agent bất đồng hoặc thay đổi tiêu chuẩn sự thật. Agent chuyên gia chỉ nhận nguồn và hai nhận định cho các ca bất đồng, không thấy dự đoán thuật toán.

Hash nguồn được đối chiếu theo quy ước nhập liệu gốc: SHA256 của văn bản UTF-8 đã chuẩn hóa xuống dòng. Tệp HTML cache trên Windows có thể có CRLF nên hash byte trực tiếp khác; không coi sự khác biệt xuống dòng này là thay đổi nội dung nguồn. Các lý do gán nhãn giữ lưu ý về kỳ52/53 tuần,13/14 tuần và chỉ tiêu lũy kế so với quý.

## Kết quả và giới hạn

-204 nhãn từ A và204 nhãn từ B, mỗi ca đúng một nhãn mỗi agent.
-201 ca đồng ý ban đầu;3 ca khác nhau được chuyên gia xử lý,0 ca hoãn.
-204 nhãn tham chiếu **AI mô phỏng**, **0 nhãn người thật** được tạo.
-Trong holdout, thuật toán khớp nhãn AI34/60 ca ngôn ngữ (56,7%) và15/15 ca chỉ tiêu đã trích xuất. Độ phủ75/75 ca; đây là tỷ lệ khớp nhãn AI, không phải độ chính xác đã được kiểm chứng độc lập.

Ba agent có thể chia sẻ cùng nền tảng mô hình và cùng sai lệch. Tỷ lệ đồng thuận cao không chứng minh tính đúng đắn; ba persona không tương đương ba chuyên gia tài chính độc lập. Bộ chỉ tiêu gồm các ca đã được bộ trích xuất tìm thấy nên15/15 không đo được số liệu bị bỏ sót. Corpus cũng đã được xem trong phát triển. Không dùng những tỷ lệ này để tuyên bố khả năng dự báo giá cổ phiếu hay chứng minh quan hệ nhân quả.

Kết quả chỉ dùng để phát hiện lỗi, phân nhóm các ca cần xem lại và hoàn thiện quy trình. Không đưa nhãn AI vào bảng nhãn người thật, không tự duyệt quan hệ graph, không thay đổi feed, không bật thông báo. Mô hình ứng dụng vẫn ở `LLM_MODE=none`; ba agent chạy trong phiên Codex được người dùng yêu cầu, không tạo tác vụ LLM nền trong sản phẩm.

## Xem và tiếp tục

Mở http://127.0.0.1:8888/adjudicate trên máy dự án bằng tài khoản thẩm định đã chuẩn bị hoặc mã quản trị gốc. Mục **AI MÔ PHỎNG** hiển thị kết quả agent riêng; phần tài khoản người thật vẫn0/204 mỗi người vì chưa có người thật gán nhãn. Ba tài khoản dự phòng được giữ theo [hướng dẫn bàn giao](campaign-204-guide-vi.md), chưa gửi mã hoặc mở thêm truy cập Cloudflare. Các agent không được cấp mã tài khoản.

Artifact riêng dưới `source-cache/ai-campaign-204/`:

- `blind-input.json`: nguồn và XML gốc, không dự đoán.
- `reviewer-a.json`, `reviewer-b.json`: nhãn AI, lý do theo ca, hash nguồn, persona và khai báo không xem dự đoán.
- `disputes.json`: nguồn và hai phiếu của3 ca bất đồng, gắn hash hai phiếu.
- `expert.json`: kết luận thẩm định, lý do và hash phiếu; phiếu đổi sẽ làm kết luận không còn hợp lệ.

Không commit các tệp nguyên văn nguồn/nhãn riêng. Chỉ báo cáo tổng hợp `reports/ai-campaign-204-summary.json` được đưa lên GitHub; báo cáo lưu hash đầu vào/đầu ra để truy vết. Bảng tiến độ đọc snapshot báo cáo này, không tự chạy lại agent hoặc nhắc việc.

```powershell
# Chuẩn bị/kiểm tra lại đầu vào; không dùng dự đoán khi tạo đầu vào agent.
.venv/Scripts/python -m engine.evaluation.agent_pilot --prepare-input
# Kiểm tra toàn bộ204 nhãn mỗi bên, tạo danh sách bất đồng và tổng hợp báo cáo.
.venv/Scripts/python -m engine.evaluation.agent_pilot
```

Lần chạy mới nên dùng thư mục riêng với `--directory` và hai agent không được đọc nhãn cũ. Chỉ đưa `disputes.json` cho agent thẩm định sau khi hai bên đã nộp. Module từ chối thiếu/trùng ca, sai nguồn, sai bộ dữ liệu, thiếu khai báo AI hoặc thẩm định cũ không khớp phiếu. Nó không có bước nhập nhãn vào DB người thật.

**Bước tiếp theo:** xem26 ca văn bản không khớp nhãn AI, nhóm lỗi theo khẳng định đã xảy ra/dự báo/không có nhân quả, kiểm tra lại căn cứ trước khi sửa thuật toán. Sau đó đánh giá trên hồ sơ kỳ mới chưa được xem, bao gồm ca chỉ tiêu bị bỏ sót hoặc không thể so sánh. Nếu cần xác nhận chất lượng độc lập thực sự, vẫn cần nguồn tham chiếu hoặc kiểm tra bên ngoài không phụ thuộc cùng mô hình.
