# Benchmark chất lượng và bước cải thiện tiếp theo — 2026-11-28

Benchmark v1 gồm **10 cohort / 3.040 cặp tin–narrative**, 411 URL khác nhau và 486 biểu diễn tiêu đề/nội dung. Số cặp và tổng cụm theo cohort không phải số sự kiện kinh tế độc lập. Nhãn AI đã lộ được dùng cho hồi quy; không phải đánh giá mù mới hoặc nhãn con người.

## Kết quả hiện tại

TP = chọn đúng; FP = chọn sai; FN = bỏ sót. Priority được đo bằng nhãn ưu tiên riêng. Không gộp các cohort thành một điểm accuracy.

| Tập | Cặp | Relevance TP/FP/FN | Precision | Recall | Unresolved | Priority TP/FP/FN |
|---|---:|---:|---:|---:|---:|---:|
| framework121 | 121 | 31/0/17 | 100.0% | 64.6% | 5 | 9/0/19 |
| actor77 | 77 | 6/0/6 | 100.0% | 50.0% | 4 | 3/0/2 |
| rss120 | 120 | 8/0/4 | 100.0% | 66.7% | 8 | 6/0/3 |
| infra160 | 160 | 8/0/15 | 100.0% | 34.8% | 20 | 2/0/7 |
| memory-unseen-2026-11-27 | 150 | 25/0/13 | 100.0% | 65.8% | 5 | 9/0/23 |
| priority-blind-2026-11-26 | 216 | 5/0/2 | 100.0% | 71.4% | 56 | 5/0/0 |
| priority-issuer-archive-2026-11-26 | 30 | 2/0/0 | 100.0% | 100.0% | 3 | 2/0/0 |
| older-rss | 1716 | 54/3/42 | 94.7% | 56.2% | 258 | Chưa có nhãn |
| older-archive | 300 | 5/0/7 | 100.0% | 41.7% | 13 | Chưa có nhãn |
| older-full_article | 150 | 25/1/3 | 96.2% | 89.3% | 13 | Chưa có nhãn |

Chi tiết mẫu số, số cụm có nhãn dương/âm, lựa chọn chưa rõ, từng nhóm tin và từng công ty nằm trong [báo cáo tổng hợp](quality-benchmark-review.json). Precision cao trên ít lựa chọn không bù cho recall thấp.

## Đã triển khai

- CLI `create/run/check`: khóa corpus, nhãn, provenance, nguồn bài đầy đủ; chạy engine hiện tại; lưu run bất biến và so sánh từng quyết định.
- Dấu vân tay runtime/config, hồ sơ, nguồn và target; từ chối dữ liệu bị sửa, target khác hoặc kết quả stale. Mốc thời gian replay được ghi rõ.
- Hook trước commit cho engine/config/dependencies; `quality_gate --all` cho cập nhật database cục bộ. Hướng dẫn bắt buộc đã nối vào AGENTS/direction/workflow.
- Quy tắc chung nhận diện gián đoạn hoạt động qua hành động–đối tượng, thể chủ động/bị động và kế hoạch. Không vá theo ticker, không suy tác động lợi nhuận, không đổi trọng số số học.

## Trước và sau

Toàn bộ 3.040 quyết định relevance giữ nguyên. Trên infra160, priority tăng từ **1 TP / 0 FP / 8 FN** lên **2 TP / 0 FP / 7 FN**: khôi phục một tin công trình bị đình chỉ. Các cohort có nhãn priority khác không đổi. Trong 7 ca ưu tiên còn bỏ sót của infra160, 5 ca chưa ghép được narrative và 2 ca đã ghép nhưng chưa được ưu tiên. Vì vậy chỉ thay trọng số không giải quyết được phần lớn thiếu sót ở tập này.

Hai lựa chọn của một bài giải thích kinh tế xây dựng trong older-full_article chuyển xuống bối cảnh. Tập này chưa có nhãn priority, nên **chưa kết luận đây là cải thiện hay regression**; độ liên quan vẫn giữ. Không đổi hoặc tự bổ sung nhãn để làm đẹp điểm.

Luồng cục bộ sau làm mới RSS: **46 thẻ chính / 44 thẻ bối cảnh**, NVDA19/DELL27 thẻ chính, 0 cảnh báo giá, không cắt bớt scan. 10 lần kiểm tra nguồn: 7 OK, 3 Not Modified, 0 tin mới/0 sửa; đây là kiểm tra lại luồng, không phải tuyên bố thu thập dữ liệu mới. Delivery disabled.

## Tồn tại và bước tiếp theo

1. **Coverage/recall:** infra160 còn 15 cặp liên quan bị bỏ sót, 7 ưu tiên bị bỏ sót. Tiếp tục contract chung cho hạn chế quyền truy cập, tài trợ/vốn và điều kiện triển khai hạ tầng; phải có đường graph đúng narrative, không tự nối nhu cầu thành nguồn cung.
2. **Vai trò doanh nghiệp:** đối thủ ở một sản phẩm có thể đồng thời là khách hàng hoặc chủ vận hành. Phân biệt project actor với technology supplier; tránh loại cả dự án chỉ vì tên một đối thủ xuất hiện.
3. **Priority:** hai thẻ bị hạ chưa có nhãn riêng. Cần tập nhãn priority độc lập ở vòng mới; phân biệt danh từ “delay” và sự kiện vận hành, kế hoạch và điều kiện giả định.
4. **Độ đại diện:** corpus đã exposed, không ngẫu nhiên, RSS/full-body/archive khác nhau và còn tương quan sự kiện. Dùng gia đình sự kiện chưa dùng cho kiểm định độc lập sau thay đổi framework.
5. **Nghiệm thu sản phẩm:** chưa đo magnitude/horizon tài chính, causal truth, utility cá nhân hóa hay đạt giám sát vận hành 7 ngày/validation con người. **V1 chưa hoàn chỉnh; chưa được mở push/cloud.**

## Kiểm chứng

92 focused tests cuối đạt; Ruff và mypy167 files đạt. Lịch sử tests thất bại ban đầu được giữ cục bộ, gồm lỗi phạm vi đối tượng và fallback đã sửa. CI [46115181508](https://github.com/linhpmvpub/Narrative/actions/runs/46115181508) đạt trên commit `39b9d4d`: 1642 passed, 1 warning in 191.67s (0:03:11); 1642 passed, 1 warning in 339.80s (0:05:39); migration, JS, dependency audit và model smoke8 đạt.

Contract/lệnh vận hành: [quality-benchmark](../docs/quality-benchmark.md). Dữ liệu chi tiết, nguồn, nhãn, predictions và database nằm cục bộ trong vùng ignore; GitHub chỉ nhận code, tests synthetic, docs và aggregate.
