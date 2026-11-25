# Bộ khung tri thức và quy tắc tác động v1

Mục tiêu: một bản tin được gắn với công ty/narrative bằng dữ liệu có nguồn, phạm vi đúng và quy tắc có phiên bản. Hệ thống giúp người dùng nhận ra vấn đề đáng theo dõi; không dự báo giá cổ phiếu.

Nguồn cấu hình thực thi: `config/mechanism-playbook.json`. Bộ thực thi: `engine/mechanism_playbook.py`. Đây là workbench cục bộ đọc atlas hiện có, chưa thay matcher/feed đang chạy.

## 1. Phân nhóm cụ thể

| Nhóm | Các loại sự kiện v1 | Kênh cần kiểm tra |
| --- | --- | --- |
| Gián đoạn nguồn cung (`supply_disruption`) | Dừng/gián đoạn sản xuất; Gián đoạn vận chuyển; Khôi phục nguồn cung | `input_availability` |
| Thay đổi giá đầu vào (`input_price`) | Biến động giá giao ngay; Điều chỉnh giá hợp đồng; Thuế/phí làm đổi giá đầu vào | `unit_cost` |
| Mở rộng/thu hẹp công suất (`capacity`) | Kế hoạch công suất; Đưa công suất vào vận hành; Đóng/thu hẹp công suất | `production_capacity` |
| Thay đổi nhu cầu (`demand`) | Nhu cầu thị trường đầu ra; Đơn hàng/hủy đơn hàng; Chi đầu tư của khách hàng | `order_opportunity` |
| Thay đổi công nghệ (`technology`) | Mẫu thử/thông số công nghệ; Chứng nhận/đạt chuẩn khách hàng; Triển khai công nghệ quy mô sản xuất | `technical_capability` |
| Tài trợ/cam kết vốn (`financing`) | Cam kết tài trợ; Giải ngân; Tái cấp vốn/điều kiện vốn | `funded_capacity_option` |
| Chính sách/cấp phép (`policy`) | Hạn chế tiếp cận thị trường; Cấp/thu hồi giấy phép; Ngoại lệ và thời hạn | `market_access` |

Các loại sự kiện được người duyệt khai báo, chưa phải bộ phân loại ngôn ngữ tự động. Động đất có thể đi qua gián đoạn nguồn cung; giá khí có thể đi qua giá đầu vào; chi đầu tư của khách hàng có thể đi qua nhu cầu. Mỗi đường vẫn cần bằng chứng công ty thực sự phơi nhiễm. Tin ngoài danh mục (ví dụ giao dịch nội bộ chưa có cơ chế được thẩm định) cần giữ ở nhóm chưa phân loại, không ép thành tác động tích cực/tiêu cực.

Mỗi nhóm có định nghĩa driver, kênh, chiều tác động có điều kiện, điều kiện cần và dữ liệu giảm nhẹ. Ví dụ giá đầu vào tăng => áp lực lên chi phí đơn vị tăng, không đồng nghĩa giá cổ phiếu giảm. Với policy, driver là mức hạn chế: hạn chế tăng => khả năng tiếp cận thị trường giảm. Không nhân dấu qua các cạnh để suy ra giá cổ phiếu.

## 2. Từ điển dữ liệu có ý nghĩa và đơn vị

Mỗi số liệu phải gắn với đúng cạnh quan hệ, sản phẩm/phạm vi, mẫu số và kỳ; có nguồn, trích dẫn, phiên bản, thời điểm biết và thời hạn hiệu lực. Không trộn kỳ hoặc lấy tỷ trọng doanh thu phân khúc làm tỷ trọng chi phí đầu vào. Một trường có nguồn vẫn cần kiểm tra khả năng áp dụng với sự kiện hiện tại.

| Tham số | Đơn vị | Ý nghĩa / giới hạn diễn giải |
| --- | --- | --- |
| `exposure_share` | `fraction` | Tỷ trọng phơi nhiễm; phải ghi rõ mẫu số, sản phẩm và kỳ. |
| `supplier_concentration` | `fraction` | Tỷ trọng mua từ nhà cung cấp trong cùng mẫu số/kỳ. |
| `supplier_concentration_qualitative` | `category` | Mô tả phụ thuộc nhà cung cấp, không quy đổi thành tỷ lệ. |
| `customer_concentration` | `fraction` | Tỷ trọng doanh thu khách hàng, đúng pháp nhân và kỳ. |
| `customer_concentration_qualitative` | `category` | Mô tả tập trung khách hàng; không suy ra tỷ trọng. |
| `substitutability` | `category` | Nguồn thay thế đã xác định và điều kiện sử dụng; không mặc định có thể thay ngay. |
| `inventory_days` | `days` | Số ngày đầu vào sử dụng được để bù gián đoạn; không dùng DIO kế toán thay thế. |
| `contract_reset_days` | `days` | Thời gian đến khi giá hợp đồng áp dụng lại. |
| `pass_through` | `fraction` | Phần biến động chi phí được chuyển cho khách hàng; cần điều khoản và mẫu số. |
| `hedging` | `category` | Công cụ/phạm vi/phần được bảo hiểm giá, không mặc định toàn bộ. |
| `ramp_days` | `days` | Thời gian tăng công suất đến mức mục tiêu có định nghĩa. |
| `utilization` | `fraction` | Công suất đang sử dụng / công suất khả dụng, cùng phạm vi. |
| `yield` | `fraction` | Sản phẩm đạt chuẩn / đầu vào sản xuất, cùng công nghệ và kỳ. |
| `market_share` | `fraction` | Doanh số công ty / thị trường có định nghĩa, cùng kỳ. |
| `competition` | `category` | Đối thủ và khả năng thay thế có nguồn; không tự cho điểm cạnh tranh. |
| `qualification_days` | `days` | Thời gian kiểm định/phê duyệt khách hàng có nguồn. |
| `funding_conditions` | `category` | Điều kiện giải ngân/sử dụng vốn còn phải đáp ứng. |
| `permit_status` | `category` | Tình trạng giấy phép; không đồng nhất nộp hồ sơ và được duyệt. |
| `exemptions` | `category` | Ngoại lệ chính sách đúng hàng hóa/pháp nhân/thời hạn. |
| `geographic_mix` | `fraction` | Tỷ trọng theo vùng; cần phân biệt nơi bán, sản xuất và xuất xứ. |
| `duration_days` | `days` | Thời lượng tác động được nguồn hỗ trợ; không lấy thời hạn hợp đồng thay thế. |
| `procurement_terms` | `category` | Điều khoản mua hàng: khối lượng, định giá, tối thiểu và điều kiện. |
| `customer_contract_terms` | `category` | Điều khoản với khách hàng, chưa đồng nghĩa đơn hàng chắc chắn. |
| `manufacturing_model` | `category` | Tự sản xuất, thuê ngoài hay liên doanh và phạm vi sở hữu. |
| `utility_dependency` | `category` | Phụ thuộc điện/nước/khí theo cơ sở sản xuất. |
| `pricing_reset_frequency` | `category` | Tần suất định giá, không suy ra ngay ngày hiệu lực. |
| `net_cost_basis` | `category` | Cơ sở chi phí ròng, loại chi phí và khoản bù trừ. |
| `contract_term` | `category` | Thời hạn hợp đồng, không phải thời lượng tác động. |
| `inventory_context` | `category` | Tồn kho kế toán/đặc điểm lưu kho, chưa là số ngày nguồn cung. |
| `pass_through_terms` | `category` | Điều khoản chuyển giá định tính, không tự chuyển thành phần trăm. |

`fraction` nằm trong [0,1], `days` không âm, `category` là thông tin định tính. Thiếu dữ liệu giữ UNKNOWN, không điền 0. Số liệu định lượng phải có kỳ, cơ sở đo/mẫu số, độ chính xác báo cáo và bằng chứng. Bộ kiểm kê không cộng gộp dữ liệu giữa các cạnh hoặc các công ty.

## 3. Bảy quy tắc theo thứ tự

| Quy tắc | Kiểm tra | Khi không đạt / chưa biết |
| --- | --- | --- |
| R01 | Hash nguồn, trích dẫn, phiên bản sự kiện, thời điểm | Từ chối đầu vào; không tạo quyết định hợp lệ |
| R02 | Tìm đường không bị cắt cụt bởi giới hạn | Giữ lại, không chọn một đường chưa đầy đủ |
| R03 | Có đường có hướng qua cạnh đủ điều kiện tới narrative | Không có đường liên quan |
| R04 | Sự kiện đã vận hành, hay còn là kế hoạch/cam kết? | Theo dõi kế hoạch/cam kết |
| R05 | Phạm vi sự kiện trùng với phần phơi nhiễm đã được thẩm định độc lập? | REVIEW_SCOPE |
| R06 | Có các tham số cần thiết trên đúng cạnh? | REVIEW_DATA |
| R07 | Có xác minh quan hệ nhân quả, độ lớn và thời gian? | REVIEW_CAUSALITY |

R01–R04 và kiểm kê R06 được thực thi trên dữ liệu hiện có. Từ 2026-11-25, R05 có sổ thẩm định cục bộ có phiên bản, nguồn và hai phiếu duyệt; xem [scope-review-v1.md](scope-review-v1.md). Không có bản duyệt hợp lệ thì R05 vẫn UNKNOWN. R07 luôn UNKNOWN; không có nhánh tự chấp nhận impact. R06 PASS chỉ có nghĩa các trường ngữ cảnh có nguồn được điền, không chứng minh mẫu số/kỳ/phạm vi phù hợp với sự kiện. Tất cả kết quả giữ thông báo tắt và độ lớn tài chính UNKNOWN.

Một lỗi nguồn bị bộ kiểm tra hiện có từ chối bằng ngoại lệ; trace bảy bước chỉ được xuất cho đầu vào đã qua kiểm tra nguồn. Mã nguồn thực thi các điều kiện đã biết, không dùng eval hoặc thực thi chuỗi công thức từ file. Thay đổi ngữ nghĩa công thức/đơn vị cần phiên bản và tests tương ứng; chỉnh mô tả không được lén đổi hành vi.

## 4. Tham số thời gian và công thức minh họa

Mốc hiển thị ban đầu: ngắn hạn <=90ngày, trung hạn91–365ngày, dài hạn>365ngày. Đây là cách phân loại biên tập có thể xem lại, không phải thời gian tác động đã học từ dữ liệu. Khoảng thời gian cắt qua hai nhóm được đánh dấu CROSSES_BANDS. Không có khoảng được hỗ trợ thì UNKNOWN. Hàm này không tự gán thời hạn cho thẻ tin.

Một mô hình nhạy cảm chi phí được định nghĩa rõ:

`Δchi_phí_ròng / chi_phí_nền = input_cost_share × unhedged_share × reset_share × price_change × (1 − pass_through)`

| Đầu vào giả định | Ý nghĩa |
| --- | --- |
| input_cost_share | Chi phí đầu vào bị ảnh hưởng / cùng tổng chi phí nền, không phải tỷ trọng doanh thu |
| unhedged_share | Phần của đầu vào đó chưa được bảo vệ giá |
| reset_share | Phần trong nhóm chưa bảo vệ được điều chỉnh giá trong kỳ giả định |
| price_change | Mức đổi giá tương đối; miền [-1,10], trần10 chỉ là giới hạn tính toán |
| pass_through | Khoản thực sự thu hồi từ khách hàng / chi phí tăng thêm của cùng phần phơi nhiễm |

Ví dụ **hoàn toàn giả lập**:20% ×50% ×80% ×10% ×(1−25%) =0,6% của chi phí nền. Nếu nền bằng100đơn vị tiền thì chi phí ròng tăng0,6đơn vị trong giả định này. Các tỷ lệ có điều kiện phải cùng phạm vi/kỳ; không nhân các tỷ lệ biên không liên quan. Khối lượng, tỷ giá và phản ứng nhu cầu giữ cố định. Đây không phải dự báo lợi nhuận/EPS/biên lợi nhuận/giá cổ phiếu. Chưa nối dữ liệu nguồn vào công thức; mọi đầu vào hiện là giả định của người vận hành.

Trọng số xếp hạng và ngưỡng mức tác động mạnh/yếu hiện chưa hiệu chỉnh. Không có điểm tổng hợp bịa đặt. Các ngưỡng precision/recall trong impact-group-acceptance.json là mục tiêu nghiệm thu đã khai báo, không phải kết quả đạt được.

## 5. Luồng mẫu và kiểm kê thật

Luồng mẫu giả lập: "Alpha Foundry plans to build wafer factories in Texas." -> capacity.announcement -> yếu tố trong hồ sơ giả lập -> đường hai cạnh tới narrative -> R01/R02/R03PASS, R04FAIL, R05/R06/R07UNKNOWN -> WATCH_PLAN_OR_COMMITMENT. Không biến kế hoạch thành công suất hoạt động. Nguồn, hồ sơ và kết quả mẫu đều được đánh dấu/đặt tên synthetic; không đưa vào feed thật.

Workbench đã đọc atlas cục bộ hiện có:6hồ sơ (gồm một hồ sơ lịch sử),5công ty,83quan hệ.581tổ hợp quan hệ×cơ chế được kiểm kê;21tổ hợp có ít nhất một trường ngữ cảnh có nguồn. Đây là ma trận kiểm kê khả năng có thể áp dụng, không phải581tác động thật hoặc mẫu số để tính độ hoàn thiện bắt buộc. Không phải mọi cơ chế đều áp dụng cho mọi cạnh.

## 6. Vai trò của LLM và lợi thế cần xây

LLM/parser hỗ trợ đề xuất phát biểu, thực thể và cơ chế. Đầu ra chỉ là ứng viên. Engine giữ các tài sản có thể kiểm tra: hồ sơ công ty có nguồn và phiên bản; danh tính/phạm vi sản phẩm; cạnh quan hệ có hiệu lực; từ điển đơn vị/mẫu số/kỳ; quy tắc chung; trace; nhãn đánh giá độc lập và lịch sử sửa/rút nguồn.

Lợi thế kỳ vọng đến từ chất lượng và độ phủ của dữ liệu này, cùng khả năng áp dụng nhất quán và đo sai số qua thời gian. Chỉ viết thêm quy tắc hoặc sử dụng đồ thị chưa chứng minh lợi thế cạnh tranh. Một LLM được cung cấp cùng dữ liệu/công cụ cũng có thể làm tốt hơn LLM chỉ nhận câu hỏi. Chưa chạy so sánh trên cùng benchmark với LLM độc lập, nên chưa tuyên bố hệ thống vượt LLM. Kết quả extractor gần nhất vẫn có recall~27–28% theo nhãn AI trên tập thí điểm hẹp.

## 7. Cách chạy và các bước tiếp theo

```powershell
.venv/Scripts/python -m engine.mechanism_playbook inventory --atlas <local-atlas-directory> --output <new-inventory.json>
.venv/Scripts/python -m engine.mechanism_playbook evaluate --atlas <local-atlas-directory> --input <reviewed-frame.json> --selection <reviewed-selection.json> --articles <local-article-store> --subtype capacity.announcement --output <new-decision.json>
.venv/Scripts/python -m engine.mechanism_playbook cost-scenario --input <five-explicit-assumptions.json> --output <new-scenario.json>
```

Ưu tiên sau giao thức R05: nối tự động trạng thái sửa/rút nguồn từ ingestion vào ledger và kiểm tra độ mới; bổ sung dữ liệu đúng mẫu số/kỳ cho từng cơ chế/công ty; mở rộng nhận diện trạng thái/thay đổi kinh tế và lời dẫn; đánh giá nhóm sự kiện mới và so sánh công bằng với baseline.25bất đồng nhãn của đợt trước còn chờ thẩm định. Chưa hiệu chỉnh trọng số, bật push hoặc thay thế matcher hiện tại.

## Kiểm tra bổ sung với nguồn thật đã lưu

Thông cáo TSMC về động đất tháng4/2024 được đối chiếu với hồ sơ AMD hiện có trong atlas.
Khung sự kiện do AI_OPERATOR khai báo giữ nguyên cả thông tin gián đoạn, hồi phục và phần
thiết bị quan trọng không bị hỏng trong đoạn nguồn. Engine tìm được một đường tới narrative,
nhưng dừngR05REVIEW_SCOPE: sản phẩm/node công nghệ của AMD bị ảnh hưởng chưa xác minh.
Mức tác động tài chính UNKNOWN. Đây là chẩn đoán trên nguồn đã xem và hồ sơ hiện có, không
phải đánh giá mù, backtest đúng thời điểm hay thông báo sự cố đang diễn ra. Không tạo thẻ feed.

EventFrame hiện phân biệt thời điểm nguồn được biết/rà soát nhưng chưa có đầy đủ thời điểm
xảy ra, công bố và bắt đầu hiệu lực tách biệt. Phải bổ sung chúng cùng kiểm tra độ mới/rút nguồn
trước tích hợp feed; nhãnOPERATING trong ví dụ diễn tả sự kiện được báo cáo lúc nguồn công bố,
không chứng minh đang gián đoạn ở thời điểm chạy thử.

## Kết quả kiểm thử

48tests tập trung đạt97,81giây, gồm32tests mới. Ruff/mypy136files đạt. CI45429638803 tại92155f7 đạt1080testsSQLite132,51giây và1080testsPostgreSQL266,31giây,8ca model thật giả lập, dependency audit và migration/seed/replay/downgrade. Ba CLI đã chạy; hash cấu hình, baseline và các đầu ra cục bộ đã kiểm tra lại. Tests đạt không chứng minh mức chính xác tác động hoặc lợi thế so với LLM.
