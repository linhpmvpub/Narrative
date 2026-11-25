# Phạm vi theo cơ chế và thẻ bối cảnh liên quan

Bản 2026-11-25. Mục tiêu: không buộc mọi tin hữu ích phải chứng minh một ảnh hưởng kinh tế
đã xảy ra. Bổ sung một tầng bối cảnh có nguồn; giữ nguyên điều kiện strict R05/R07 về truyền
tác động. Chưa nối vào feed/map đang chạy; đầu ra là JSON card trong workbench cục bộ.

## Ma trận thực thi

`config/mechanism-scope.json` là policy có phiên bản/hash; `engine.mechanism_scope` kiểm tra
contract và các chiều phạm vi. Đây là thiết kế kỹ thuật ban đầu, chưa được hiệu chỉnh bằng
nhãn độc lập. Luôn phải nêu trạng thái cho cả năm chiều, không có mặc định bỏ qua.

| Cơ chế | Bắt buộc khớp | Có điều kiện |
|---|---|---|
| Gián đoạn cung | Pháp nhân, sản phẩm, cơ sở, địa lý, kỳ | Không |
| Giá đầu vào | Pháp nhân, sản phẩm, địa lý, kỳ | Cơ sở |
| Công suất | Pháp nhân, sản phẩm, địa lý, kỳ | Cơ sở |
| Nhu cầu | Pháp nhân, sản phẩm, kỳ | Cơ sở, địa lý |
| Công nghệ | Pháp nhân, sản phẩm, kỳ | Cơ sở, địa lý |
| Tài trợ | Pháp nhân, kỳ | Sản phẩm, cơ sở, địa lý |
| Chính sách | Pháp nhân, sản phẩm, địa lý, kỳ | Cơ sở |

“Có điều kiện” nghĩa là vẫn phải khớp, **hoặc** có quyết định không áp dụng kèm trích dẫn ở cả
bài sự kiện và bằng chứng quan hệ, lý do cụ thể, và hai phiếu đồng ý với đúng đề xuất. Thiếu
thông tin không có nghĩa là không áp dụng. Engine kiểm tra trích dẫn và phiên bản; ý nghĩa của
lý do vẫn là diễn giải của reviewer, chưa phải chứng minh ngữ nghĩa tự động.

V1 vẫn yêu cầu tham chiếu pháp nhân hợp lệ ở đầu đường. Tin chỉ nói về giá hàng hóa chung mà
không có pháp nhân được ghép đúng chưa được giải quyết. Không dùng tên gần giống hoặc tự
đổi node hàng hóa thành công ty để vượt điều kiện. Gián đoạn cung vẫn giữ đủ năm chiều trong
policy này; các trường hợp logistics rộng cần một contract được đánh giá riêng sau đó.

## Dữ liệu và cách dùng

Proposal của `engine.scope_review` có thể thêm trường tùy chọn:

```json
{
  "context_scope": {
    "policy_sha256": "HASH_CUA_MECHANISM_SCOPE_POLICY",
    "mechanism_id": "input_price",
    "not_applicable": {
      "facility": {
        "event_quote": "TRICH_DAN_NGUYEN_VAN_TU_SU_KIEN",
        "exposure_quote": "TRICH_DAN_NGUYEN_VAN_TU_BANG_CHUNG_QUAN_HE",
        "rationale": "LY_DO_CO_CAN_CU_VI_SAO_CO_SO_KHONG_AP_DUNG_CHO_BOI_CANH_NAY"
      }
    }
  }
}
```

Ví dụ là schema minh họa với placeholder, không phải bản duyệt hợp lệ. Hash policy được tính
bằng `engine.ingestion.contracts.digest(engine.mechanism_scope.load())`. Chỉ giữ trong `facets`
các chiều thực sự khớp. Không được khai báo một chiều vừa khớp vừa không áp dụng, bỏ trống một
chiều, hoặc gắn NOT_APPLICABLE vào chiều bắt buộc. Tạo lại canonical proposal hash và phiếu
duyệt sau khi thay đổi bất kỳ trường nào.

Toàn bộ kiểm tra nguồn/epoch, event/selection/atlas/playbook hash, legal identity, đường quan
hệ, thời gian, reviewer và thu hồi vẫn áp dụng. Khi có ingestion binding, phải chạy với
`--news-current`; nguồn quá hạn/lỗi/đã sửa/rút không tạo context card. Ledger thay đổi trong lúc
đánh giá cũng giữ lại. Không dùng đường chưa duyệt hoặc graph bị cắt ngắn để tạo thẻ.

Proposal cũ không có `context_scope` vẫn dùng hợp đồng strict năm chiều; canonical serialization
không chèn field null nên hash phiếu cũ không đổi. Không nâng cấp thầm bản duyệt cũ sang context.
Đổi policy context làm bản duyệt context cũ không hợp lệ cho lần chạy mới.

## Đầu ra đến thẻ tin

Scope result `CONTEXT` khác `PASS`. Workbench xuất `related_context_cards` cho từng đường đã
được duyệt context, gồm narrative, nguồn/packet, phát biểu gốc, phase, đường với nhãn node và
trích dẫn cạnh, ma trận facet, lý do không áp dụng, điều kiện và phần chưa biết.

- Nhãn: **Bối cảnh liên quan — chưa xác minh tác động**.
- `strength`, `horizon`, `financial_magnitude`: UNKNOWN; `price_prediction`: null.
- `delivery`: disabled; `active_feed_changed`: false.
- Context không làm R05 PASS, không điền tham số R06, không vượt R07.
- Tin kế hoạch có thể có context card với phase PROPOSED trong khi R04 vẫn FAIL. Không biến
  kế hoạch thành công suất/doanh thu đã thực hiện.

Ví dụ synthetic: Alpha Foundry tăng giá wafer trên thị trường Texas trong2026; không xác định
một nhà máy riêng. Các nguồn giả lập và hai phiếu fixture cho phép một context card, vẫn dừng
R05. Khi source epoch bị rút, thẻ không xuất hiện trong lần đánh giá mới. Đây là kiểm thử giao
thức, không phải tin thật hoặc hai agent đã gán nhãn độc lập.

## Rà soát và bước tiếp

Chưa chứng minh recall tăng: chưa có cohort mới, nhãn độc lập hoặc source facts mới. Vẫn literal
matching, pháp nhân đầu đường và kỳ khai báo; thiếu ontology hàng hóa/địa lý và diễn giải thời gian.
Một nguồn rộng không tự chứng minh công ty mua đúng benchmark hoặc hợp đồng chịu giá đó.

Ưu tiên sau lượt này: điền nguồn thật về sản phẩm/đầu vào/segment, bổ sung reference cho loại yếu tố
phi pháp nhân với contract riêng; chuẩn bị nhóm tin giá/nhu cầu/gián đoạn có ca near-miss; freeze
dữ liệu/rules trước review độc lập. Đo relevance/context riêng với verified impact. Chỉ nối UI/feed
khi lifecycle tại thời điểm dùng và nhãn UX không khiến người dùng hiểu nhầm mức bằng chứng.
