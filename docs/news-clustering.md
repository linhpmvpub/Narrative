# Nhóm tin ứng viên và đối chiếu trước Impact Engine

Trang `/news` có mục **Nhóm sự kiện & đối chiếu nguồn**. Đây là các nhóm cần thẩm định, chưa phải canonical economic events. Hiện engine không tự chuyển nhóm thành kết luận tác động hoặc cảnh báo.

## Quy tắc phiên bản news-grouping-v1

1. Đọc tối đa500 mục có phiên bản nhận được trước `as_of`; chọn đúng bản mới nhất tại thời điểm đó từ bảng revision. Không đọc payload hiện tại để dựng lại quá khứ. Báo `truncated=true` nếu vượt cửa sổ.
2. Cùng URL chuẩn hóa được gom như bản sao của cùng bài. Khác URL cần có ngày đăng cách nhau không quá48 giờ. Không gom khi hai tập ticker rõ ràng không giao nhau.
3. Gom khi tiêu đề gần như trùng (Jaccard từ >=0,8 và ít nhất5 từ chung), hoặc có chung ticker + loại sự kiện + ít nhất4 từ chung, Jaccard>=0,55. Loại sự kiện gồm earnings/acquisition/legal/monetary_policy/trade_policy/product.
4. Mỗi bài mới phải khớp **mọi** bài trong nhóm, không chỉ một bài trung gian. Thứ tự cố định theo ID để có thể chạy lại; cách chia nhóm vẫn là heuristic, không phải hiểu ngữ nghĩa đầy đủ.
5. So sánh các số và từ chỉ hướng trong tiêu đề. Khác biệt là tín hiệu cần đọc ngữ cảnh, không khẳng định mâu thuẫn: hai số có thể thuộc kỳ/chỉ tiêu khác nhau. Phần tóm tắt và toàn văn chưa được dùng để xác nhận claims.

Mỗi nhóm giữ itemID, version, revisionID, hash capture/payload, URL, thời điểm đăng/nhận và lý do gom. ID nhóm là hash thành viên/phiên bản, thay khi thành viên đổi; không dùng ID này làm mã sự kiện kinh tế bền vững. Snapshot hash khóa toàn bộ kết quả, không bao gồm thời điểm truy vấn. Nếu cùng kết quả, CLI giữ snapshot đầu tiên thay vì ghi đè.

## Đếm nguồn đúng phạm vi

CNBC Markets/World/Technology và tài khoản X CNBC thuộc cùng nhóm CNBC. MarketWatch/WSJ cùng nhóm Dow Jones. Fed/ECB được ghi loại primary_institution khi URL đúng domain đã biết. Domain chưa biết không tự được tính là nhà xuất bản độc lập. Bản đồ ownership này có phạm vi giới hạn, gắn với phiên bản thuật toán và cần cập nhật khi thay đổi.

**Số nhóm nhà xuất bản không phải số nguồn xác nhận độc lập.** Hai báo có thể đăng lại cùng thông cáo hoặc dẫn cùng một bên. `reporting_independence=NOT_ESTABLISHED` và `claim_verified=false` luôn được thể hiện; không suy ra độ tin cậy từ số lượng bài. Đối chiếu hiện tại là so sánh metadata/tiêu đề, không phải kiểm chứng điều tra hoặc đo tác động nhân quả.

## Hồ sơ chuyển tiếp để thẩm định

Mỗi nhóm có `impact_handoff` và mức ưu tiên: CONFLICT_REVIEW, MULTI_PUBLISHER_REVIEW hoặc SOURCE_REVIEW. Các điều kiện còn thiếu được liệt kê:

- Claim có cấu trúc và bản trích xuất được kiểm duyệt.
- Đoạn nguồn, chỉ tiêu, đơn vị và kỳ so sánh đã xác minh.
- Danh tính công ty, phơi nhiễm và mức trọng yếu.
- Đường quan hệ đủ điều kiện cùng các phản chứng/điều kiện.
- Giải quyết khác biệt số liệu hoặc chiều biến động nếu có.

Trong phiên bản này **ready=false**: chỉ tạo hồ sơ thẩm định có bằng chứng và lý do chặn. Chưa có endpoint phê duyệt claim news hay bridge tự động sang `engine.ingestion.reviewed` (hiện chuyên cho SEC). Không giả lập phê duyệt để làm đủ pipeline. Bước tiếp theo là thiết kế và kiểm thử claim review cho nguồn news, rồi dùng lại điều kiện canonical/graph hiện có khi đủ bằng chứng. Không sửa gate của SEC, không nhập RSS vào tập đánh giá sau-freeze.

## Chạy và xem lại

```powershell
$env:DATABASE_URL='sqlite:///rie-dev-feed.db'
.venv/Scripts/python -m engine.news_clusters
```

API GET `/api/v0/news/clusters` yêu cầu tài khoản; gateway chỉ cho GET. API tính từ revision hiện có, không gọi mạng, không ghi DB; sử dụng toàn bộ nguồn trong cửa sổ, không chịu bộ lọc bài viết trên trang. CLI lưu chi tiết riêng vào `source-cache/news-clusters/<snapshot_hash>.json`, chỉ số liệu tổng hợp vào `reports/news-cluster-summary.json`.

Lần chạy22/11/2026:135 mục→100 nhóm, đều chỉ có một URL bài trong mỗi nhóm; chưa có nhóm đa nhà xuất bản hoặc nhóm đủ điều kiện Impact Engine. Không trình bày dữ liệu kiểm thử tổng hợp như kết quả đối chiếu thật. Mẫu hiện tại chưa đo được độ chính xác của gom các cách diễn đạt khác nhau; cần gán nhãn các cặp bài cùng/khác sự kiện và kiểm tra false merge/missed merge trước khi mở rộng tự động hóa.
