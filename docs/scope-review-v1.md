# R05 — sổ thẩm định phạm vi cục bộ

Bản 2026-11-25 nối `engine.scope_review` vào workbench `engine.mechanism_playbook`.
Mục đích: kiểm soát việc một sự kiện có cùng phạm vi với một đường quan hệ cụ thể.
Không xác nhận nhân quả, mức tác động, thời gian tác động hoặc giá cổ phiếu.
Không thay đổi feed đang hoạt động; delivery luôn disabled, R07 luôn UNKNOWN.

## Dữ liệu và quy tắc

| Thành phần | Điều kiện bắt buộc |
|---|---|
| Đề xuất | Hash chính xác của EventFrame, selection bài nguồn, atlas và playbook; narrative và thứ tự cạnh của đúng một đường |
| Nguồn sự kiện | Phiên bản trạng thái mới nhất trong ledger phải CURRENT, cùng packet hash và source_epoch; quan sát trước khi lập đề xuất |
| Quan hệ | Từng cạnh SOURCE_BACKED, đủ điều kiện tại snapshot, hiệu lực bao trùm khoảng sự kiện khai báo |
| Bằng chứng phơi nhiễm | Trích dẫn có nguồn nằm trên cạnh đầu, cùng yếu tố đầu vào của sự kiện |
| Pháp nhân | Tham chiếu EXACT_ENTITY/LEGAL_ENTITY có nguồn, còn hạn, cho phép đúng cạnh đầu và đúng tên |
| Phạm vi | Đủ pháp nhân, sản phẩm, cơ sở, địa lý, kỳ; từng từ/cụm có ranh giới từ trong hai trích dẫn; bốn phạm vi sau khớp nguyên nghĩa đen sau chuẩn hóa |
| Phiếu duyệt | Ít nhất hai ID khác nhau, được policy cục bộ cho phép; khác tác giả đề xuất và người tạo EventFrame; tất cả APPROVE, ký nhận đúng hash đề xuất |
| Thời gian duyệt | Sau khi rà soát EventFrame, không ở tương lai, tối đa 90 ngày; dùng bản duyệt mới nhất, không quay về bản cũ khi bị thu hồi |
| Nhiều đường | Tất cả đường ứng viên phải có bản duyệt riêng hợp lệ để R05 tổng thể PASS |

V1 chỉ hỗ trợ khoảng sự kiện đã kết thúc trước khi lập đề xuất. Khoảng tương lai/đang tiếp diễn,
từ đồng nghĩa, sản phẩm bao hàm/đè lấn, yếu tố không có pháp nhân và đường không cạnh chưa được
hỗ trợ. Những ca này giữ UNKNOWN. Khoảng thời gian vẫn do người duyệt khai báo; engine kiểm
tra thứ tự/hiệu lực và trích dẫn kỳ, chưa tự chứng minh diễn giải ngày tháng đúng về ngữ nghĩa.

## Thao tác cục bộ

Đặt toàn bộ hồ sơ/phiếu/SQLite trong `source-cache/`, không commit. Các file dưới đây do
operator chuẩn bị từ bằng chứng đã kiểm tra; không tự điền nhãn độc lập bằng agent triển khai.

```powershell
python -m engine.scope_review init --store source-cache/reviews.sqlite
python -m engine.scope_review append --store source-cache/reviews.sqlite --kind source --id OBSERVATION_ID --input source-cache/source-state.json
python -m engine.scope_review proposal-hash --input source-cache/proposal.json
python -m engine.scope_review append --store source-cache/reviews.sqlite --kind review --id REVIEW_ID --input source-cache/review.json
python -m engine.scope_review history --store source-cache/reviews.sqlite --kind review --id REVIEW_ID
```

Source state gồm đúng `packet_sha256`, `status` (CURRENT/WITHDRAWN/DISPUTED), `observed_at`.
Review gồm `proposal`, `votes`, `status` (REVIEWED/DISPUTED/REVOKED), `recorded_at`.
Cấu trúc đầy đủ và giới hạn trường nằm trong các model Proposal/Facet/Vote/Review.
Lấy hash bằng lệnh `proposal-hash` trước khi duyệt: hash dùng model chuẩn hóa, bao gồm cách
biểu diễn thời gian UTC. Mọi thay đổi đề xuất đòi hỏi phiếu mới.

Cập nhật dùng append và `--expected-head HASH_MOI_NHAT`, không sửa/xóa hàng cũ. Đăng ký một
source_epoch mới làm bản duyệt cũ hết hiệu lực, kể cả khôi phục CURRENT cùng packet sau khi rút.
SQLite transaction ngăn ghi đồng thời đè nhau; hash chain phát hiện hàng bị sửa/mất.

Khi chạy `mechanism_playbook evaluate`, truyền cả ba tùy chọn:
`--scope-store`, `--scope-reviews`, `--reviewer-policy`.
Bindings là object `{digest([narrative_id, ordered_relation_ids]): review_id}`.
Policy là `{"reviewers":{"id-a":"AI_INDEPENDENT","id-b":"HUMAN"}}`.
ID lạ, tự duyệt, phiếu từ chối/không chắc chắn hoặc ledger đổi trong lúc đánh giá đều không PASS.
Trace lưu hash/version bản duyệt, source_epoch, reviewer kinds và policy hash; `human_gold=false`.

## Ranh giới tin cậy và bước tiếp theo

- Đây là local trusted-operator store, chưa có đăng nhập/chữ ký xác minh danh tính hay chứng minh
  các agent thực sự độc lập. Nhãn AI_INDEPENDENT là khai báo của operator, không phải chứng thực.
- Trạng thái nguồn do operator ghi vào ledger. Chưa nối tự động với ingestion correction/withdrawal;
  do đó không bảo đảm website nguồn chưa thay đổi kể từ lần kiểm tra. Trước feed phải nối lifecycle
  và thêm giới hạn độ mới nguồn.
- Hash chain không chống operator có quyền thay toàn bộ database bằng bản cũ. Cần receipt ngoài
  store nếu dùng nhiều người hoặc vận hành thật; chưa mở API quản trị mới.
- Trích dẫn khớp từ không chứng minh hai phạm vi kinh tế tương đương; trách nhiệm nằm ở thẩm định.
  Cần tập nhãn mù theo từng chiều phạm vi, ca phủ định và ca thiếu dữ liệu trước mở rộng coverage.
- Chưa thay đổi thuật toán trích xuất/độ chính xác trên tin thật. 25 bất đồng của tập cũ còn chờ
  thẩm định. Không dùng cohort đã xem như holdout mới.

## Kiểm chứng

Các tests và demo Alpha Foundry đều **synthetic**, phiếu do fixture tạo để kiểm tra giao thức;
không có người/agent độc lập tham gia gán nhãn trong lượt này. Luồng đầy đủ từ capture có hash,
atlas có nguồn đến R05 PASS dừng ở R06 vì thiếu tham số; thử nghiệm R06 đủ vẫn dừng R07.
Kiểm tra thêm sai phiên bản/phạm vi/phiếu, rút nguồn, epoch mới, thu hồi, stale writer, sửa hàng,
nhiều đường và ledger thay đổi đồng thời. Đây là độ đúng phần mềm, không phải độ chính xác đầu tư.

Ưu tiên tiếp: nối trạng thái sửa/rút từ ingestion bằng ID/revision ổn định; bổ sung thời điểm
sự kiện và giới hạn freshness; thu thập phạm vi thật đủ bằng chứng rồi thẩm định độc lập;
sau đó mới thêm tham số đúng mẫu số/kỳ cho R06 và kiểm chứng nhân quả ở R07.
