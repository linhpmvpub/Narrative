# Hồ sơ doanh nghiệp → đường liên quan → narrative → thẻ tin

Khung `company-profile-v1` mô tả liên hệ kinh tế và giải thích mức liên quan của
tin. Không dự báo giá, không đòi có số tác động mới được hiển thị tin và không
tự đưa quan hệ vào graph dùng để gửi cảnh báo. Runtime giữ thông báo thật tắt.

## Hợp đồng dữ liệu

`schemas/company-profile-v1.json` chứa42nhóm thành phần,23loại quan hệ và JSON
Schema của bundle. Mã kiểm tra nằm trong `engine/company_profiles.py`.

- `ProfileBundle`: danh tính pháp nhân/ticker/identifiers, phiên bản, thời điểm
  snapshot và availability thực tế, mô-đun ngành, nguồn, thành phần, nodes,
  relationships, observations, narratives, events. Hồ sơ có thể tồn tại trước khi có narrative hoặc sự kiện; không bắt buộc tạo tin giả để khởi tạo. Không giới hạn thêm ticker
  bằng danh sách hardcode; không sửa5mã/10narrative seed của engine cũ.
- `Component`: key chuẩn, summary, evidence và trạng thái SOURCED/UNKNOWN/
  NOT_DISCLOSED/NOT_APPLICABLE/STALE/DISPUTED. Thành phần thiếu được bổ sung
  UNKNOWN khi đọc. SOURCED phải có nguồn; không coi thiếu số liệu là0.
- `Node`: ID ổn định, nhãn và loại company/security/segment/product/customer/
  supplier/input/facility/market/location/factor/metric/partner/person/channel/
  contract. ID yếu tố có thể tái sử dụng giữa bundle; chưa có kho entity toàn
  cục hoặc bộ giải quyết tên đồng nghĩa tự động.
- `Relationship`: loại, đầu/cuối có kiểm tra kiểu, scope, hiệu lực từ/đến,
  known_at, status, basis, điều kiện, unknowns, direction, lag và trích nguồn.
  Không gán độ nhạy tài chính hay xác suất bằng cách nhân điểm tùy ý.
- `MetricObservation`: giá trị Decimal hữu hạn, unit/currency, kỳ đầu/cuối,
  scope, GAAP/NON_GAAP/PHYSICAL/UNKNOWN và bằng chứng. Kiểm tra hợp đồng không
  chứng minh số được đọc/chuẩn hóa đúng; chưa dùng các quan sát này để tính impact.
- `Narrative`: version, thesis, company/scope/horizon, watched_nodes, assumptions,
  supporting/challenging evidence, reconsider_when, unknowns, event-type rules.
  Chỉ nhận SHARED_RESEARCH_EXAMPLE: không chứa ghi chú riêng hoặc thay đăng ký
  người dùng. Narrative cá nhân của API sản phẩm hiện hữu vẫn tách biệt.
- `Event`: ID canonical do người vận hành xác định, revision, type, headline,
  summary, anchors, occurred_at/available_at, bằng chứng và cờ historical.
  Chưa tự trích/ghép thực thể từ RSS; anchors là đầu vào đã chọn có nguồn.

## 42 thành phần

Danh tính, chứng khoán, sở hữu, phân khúc, sản phẩm, mô hình doanh thu, chiến
lược, giá bán, cơ cấu bán hàng, khách hàng, người dùng cuối, kênh, thị trường,
động lực nhu cầu, đơn hàng, cạnh tranh, đối tác, đầu vào, nhà cung cấp trực tiếp,
nhà cung cấp gián tiếp, giá đầu vào, mua hàng, cơ sở, công suất, tồn kho,
logistics, tiện ích, lao động, khả năng chống chịu, tài chính, nợ, FX/phòng hộ,
kế toán, quản trị, giao dịch người nội bộ, bên liên quan, sự kiện vốn, pháp lý,
địa chính trị, thời tiết, công nghệ/an ninh và lịch sự kiện.

Các thực thể/chỉ tiêu chi tiết dùng nodes/relationships/observations thay vì
chỉ chép thành một bài mô tả. Ví dụ: location cho tọa độ/địa bàn được định danh;
facility cho nhà máy; contract cho điều khoản/hợp đồng; input cho loại và cấp
đầu vào; metric cho giá, sản lượng hoặc chỉ tiêu tài chính có đơn vị và kỳ.
Phiên bản này chưa có validator chuyên ngành cho tọa độ, điều khoản hợp đồng,
mã giao dịch người nội bộ hoặc loại giá spot/contract. Các thông tin đó phải
giữ phạm vi rõ trong nhãn/scope và được mở rộng có kiểm thử khi có dữ liệu thật.

## Quan hệ cấu trúc và cơ chế

Cấu trúc: OWNS, ISSUES, HAS_SEGMENT, SELLS, USES_INPUT, SUPPLIES, BUYS,
SOLD_IN, LOCATED_IN, DISTRIBUTES, PARTNERS_WITH, COMPETES_WITH, HAS_METRIC,
APPLIES_TO, DEPENDS_ON.

Cơ chế: AFFECTS_COST, AFFECTS_SUPPLY, AFFECTS_DEMAND, AFFECTS_ACCESS,
AFFECTS_REVENUE, AFFECTS_MARGIN, AFFECTS_CASH, AFFECTS_FINANCING.

SOURCE_BACKED nghĩa là bản nhập được gán trạng thái có nguồn và đoạn trích
được kiểm tra tồn tại; không phải thẩm định nhân quả độc lập. Basis phân biệt
SOURCE_REPORTED, ISSUER_ATTRIBUTION và CONDITIONAL_MECHANISM. CANDIDATE,
DISPUTED, REVOKED, STALE không tham gia đường tạo thẻ tin.

Routing xác nhận anchor có liên hệ cấu trúc với công ty, rồi duyệt đường có
hướng không lặp node đến watched_node. Tối đa3cạnh cấu trúc +2cơ chế,5cạnh tổng,
20đường và2000lượt duyệt; báo truncated nếu còn hàng đợi. Ưu tiên đường có cơ
chế và ngắn trong các đường tìm được, không tuyên bố đường có xác suất cao nhất.
Điều kiện được hiển thị, chưa được tự động chứng minh đã thỏa mãn. Không tự
đảo dấu tác động hoặc suy luận mức độ tài chính từ một đường có liên quan.

Một thẻ cho mỗi event/narrative trong bundle, giữ số đường thay thế; không cộng
nhiều đường thành tác động lớn hơn. Đường chỉ có cấu trúc hoặc khớp anchor trực
tiếp cho RELATED_INFORMATION. Khi có cơ chế, event-type rule khai báo trong
narrative có thể cho SUPPORTS_ASSUMPTION/CHALLENGES_ASSUMPTION/MIXED. Đây là
đánh giá một giả định của mẫu nghiên cứu, không là quyết định push hay dự báo giá.

## Nguồn, phiên bản và vận hành cục bộ

`COMPANY_PROFILE_ROOT` mặc định `source-cache/company-profiles`. Mỗi thư mục
chứa source files, `profile-vN.json` bất biến và `current.json` trỏ phiên bản
hiện hành. Source path phải ở trong thư mục, nguồn<=5MB/bundle<=1MB, hash bytes
và quote trong text hiển thị phải khớp. Nguồn phải có HTTPS URL. Trình đọc HTML
dùng block text; không xác minh publisher signature hoặc ngữ nghĩa quote bằng
máy. Metadata doanh nghiệp và ý nghĩa quan hệ vẫn cần người vận hành kiểm tra.

Ngày công bố, ngày sự kiện, hiệu lực quan hệ, thời điểm thu thập và availability
được giữ riêng. known_at của quan hệ và event availability không thể trước lúc
thu thập bằng chứng. as_of trước bundle availability không thấy bundle. Pointer
rút/nguồn hỏng luôn ẩn dữ liệu, kể cả truy vấn thời điểm cũ: current-valid view,
không phải lịch sử replay đầy đủ của mọi lần duyệt/rút.

```powershell
python -m engine.company_profiles schema
python -m engine.company_profiles validate --directory source-cache/company-profiles/nvda-h20-historical
# Sau khi chuẩn bị nguồn và bản nháp trong thư mục riêng:
python -m engine.company_profiles stage --directory source-cache/company-profiles/example --input source-cache/example-draft.json
python -m engine.company_profiles withdraw --directory source-cache/company-profiles/example
```

Stage đòi version1 cho hồ sơ mới, sau đó tăng đúng1, cùngID và availability muộn
hơn; kiểm tra nguồn trước ghi. Version file tạo độc quyền, pointer thay nguyên
tử, writer.lock ngăn CLI ghi đồng thời. Khi tiến trình bị ngắt, có thể còn lock/
file tạm/phiên bản chưa kích hoạt: kiểm tra không có writer hoạt động và đối
chiếu nội dung trước khôi phục; không tự xóa/ghi đè lịch sử. Không có write API.

## API và giao diện

GET `/api/v0/news/profiles?as_of=<aware ISO datetime>` và
GET `/api/v0/news/profile-framework` yêu cầu tài khoản hiện có; gateway cho GET
hai route này, không mở quản trị. Chỉ trả bản chiếu cho thành viên, không trả
đường dẫn local hoặc raw source files. Tối đa30hồ sơ/lần, báo truncated. ID hồ sơ trùng giữa các thư mục bị ẩn toàn bộ để tránh chọn nhầm phiên bản.

`/news` có phần “Tin theo hồ sơ & narrative”, hồ sơ với42trạng thái, thẻ có
đường liên quan, giả định, unknowns, điều kiện xem xét lại và nguồn. Xóa nội dung
khi refresh/hide/logout; lỗi không giữ thẻ cũ. Mẫu dùng chung không chịu bộ lọc
nguồn RSS và không tự biến thành narrative/subscription cá nhân.

## Hồ sơ mẫu có nguồn

NVIDIA H20, hồ sơ SEC quý kết thúc27/04/2025. Snapshot/publication lấy
acceptanceDateTime2025-05-28T20:32:57Z trong submissions đã thu thập, không dùng
giờ giả định. Bản nháp2 sửa metadata giờ công bố của bản nháp1; version3 được nhập qua stage với availability mới và giữ các file cũ.
Raw nguồn tái sử dụng từ ca H20 cục bộ đã có; không lấy dữ liệu mới lên cloud.

6/42thành phần có bằng chứng chọn lọc: sản phẩm, thị trường, quy định, phân
khúc, định nghĩa khách hàng trực tiếp và động lực doanh thu;36UNKNOWN. Không
bịa tên khách hàng/nhà cung cấp hay tỷ trọng chi phí. Data Center không bị
đồng nhất với phân khúc báo cáo Compute & Networking.

Thẻ mẫu: yêu cầu giấy phép → H20 → thị trường liên quan → doanh thu. Kết luận
CHALLENGES_ASSUMPTION theo narrative mẫu về khả năng tiếp cận thị trường, với
ISSUER_ATTRIBUTION và các điều chưa biết. Hiển thị rõ lịch sử, không coi quy định
2025 còn hiệu lực hôm nay. Không dùng benchmark AI73.2% để xác nhận quan hệ này.

Tiếp theo: profile ngành có trường chuyên biệt, entity registry dùng chung,
ghép sự kiện RSS vào yếu tố có review, narrative riêng theo tenant, kiểm tra
điều kiện cơ chế, xếp hạng relevance/novelty và thêm hồ sơ đầu vào/chuỗi cung ứng
ngoài mẫu H20. Chưa có chất lượng push được kiểm chứng; notifications vẫn tắt.
