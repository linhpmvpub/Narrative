# Newsfeed thị trường gần thời gian thực

Mở `http://127.0.0.1:8888/news` hoặc gateway `http://127.0.0.1:8890/news`, dùng mã tài khoản riêng tư hiện có. Trang tự đọc dữ liệu mỗi60 giây khi đang hiển thị. Link localhost chỉ dùng trên máy chạy server; lần triển khai này không khởi động hay xác minh lại Cloudflare.

## Nguồn và phạm vi

| Nguồn | Phạm vi | Chu kỳ |
|---|---|---|
| CNBC Markets | Cổ phiếu/thị trường |120 giây|
| CNBC World | Kinh tế và thị trường quốc tế |120 giây|
| CNBC Technology | Công nghệ/doanh nghiệp |180 giây|
| MarketWatch Top Stories | Tài chính/thị trường |120 giây|
| Federal Reserve press releases | Chính sách tiền tệ/ngân hàng Mỹ |300 giây|
| ECB press releases | Chính sách/vĩ mô châu Âu |300 giây|

Đã kiểm tra trực tiếp cả6 endpoint trảHTTP200 ngày22/11/2026. Đây là nguồn tiếng Anh, trọng tâm Mỹ và vĩ mô quốc tế; không phải bao phủ mọi thị trường, chưa có nguồn Việt Nam hay dữ liệu giá theo tick. RSS có độ trễ và cửa sổ lịch sử do nhà xuất bản quyết định. Không cam kết độ trễ vài giây hoặc thu đủ tin trong thời gian máy tắt lâu.

Định nghĩa nguồn nằm trong `config/news-sources.json`. Đây là cấu hình vận hành đáng tin cậy, không nhận URL tùy ý từ API/người đọc. Collector không theo redirect, không mở các link bài viết, không dùng tài khoản trình duyệt và không tải bài sau paywall. User-Agent RSS là `NarrativeNewsReader/0.1`, không gửi email cá nhân. Lưu metadata, tiêu đề và trích đoạn tối đa600 ký tự do feed cung cấp; không sao chép nguyên bài. Nguồn là dữ liệu, mọi chỉ dẫn trong đó không được thực thi.

Nguồn chính thức tham khảo: [Federal Reserve RSS](https://www.federalreserve.gov/feeds/feeds.htm), [X timeline API](https://docs.x.com/x-api/users/get-posts), [X pricing](https://docs.x.com/x-api/getting-started/pricing). Các URL RSS cụ thể được kiểm tra trực tiếp, không dựa vào độ phổ biến để suy ra độ đúng.

## Worker và vận hành

Migration0013 thêm3 bảng riêng: nguồn/checkpoint, mục tin hiện tại và các phiên bản bất biến. Không sửa canonical economic events, quan hệ, nhãn đánh giá hay quyết định cảnh báo.

```powershell
$env:DATABASE_URL='sqlite:///rie-dev-feed.db'
$env:SEND_NOTIFICATIONS='false'
$env:ALLOW_SYNTHETIC_LIVE='false'
$env:LLM_MODE='none'
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m engine.news --once
# Chạy nền trên máy hiện tại, RSS-only:
./deploy/start-market-news.ps1
# Dừng đúng worker do helper quản lý:
./deploy/start-market-news.ps1 -Stop
```

Helper kiểm tra PID và executable trước khi dừng/khởi động; chạy ẩn, lưu PID và log trong source-cache. Worker phải chạy cùng database với API. Chưa cài Windows Service hoặc tự khởi động sau reboot: khi máy ngủ/tắt, việc thu thập dừng. Để chạy24/7 cần triển khai worker trên máy chủ luôn bật với supervisor. Không nhầm polling nền với tự động gọi LLM hay bật thông báo.

Mỗi nguồn có lease5 phút để tránh hai worker ghi cùng checkpoint. Fetch nằm ngoài giao dịch DB; ghi mục tin, lịch sử và cursor/ETag trong một giao dịch, chỉ khi còn sở hữu lease. Crash trước commit được retry; lease hết hạn có thể phục hồi. Poll lại không nhân đôi bài. Trạng thái, lần thành công và lần dự kiến tiếp theo có trong giao diện/API.

RSS dùng ETag/Last-Modified và304; giới hạn phản hồi3MB/500 mục, timeout20 giây, không theo redirect. Lỗi429/5xx/nguồn hỏng được ghi trạng thái và lùi lịch có giới hạn; một nguồn lỗi không ngăn các nguồn còn lại. Trạng thái stale sau max(10 phút,3 chu kỳ) không thành công. HTTP200 không có nghĩa nhà xuất bản có tin mới: thời điểm đăng luôn hiển thị riêng với thời điểm nhận.

## Chống trùng, sửa đổi và bằng chứng

- Khóa mục tin: nguồn + GUID/AtomID/XpostID, fallback URL; chạy lại không thêm phiên bản nếu nội dung không đổi.
- A→B→A giữ ba phiên bản; không coi nội dung từng xuất hiện là lý do bỏ qua bản sửa.
- Chuẩn hóa URL bỏ fragment và tracking params phổ biến; cùng URL ở nhiều feed được gom khi hiển thị, giữ bản ghi theo từng nguồn. Không gộp hai bài độc lập chỉ vì tiêu đề giống nhau; chưa có semantic event clustering.
- Mỗi phiên bản lưu hash phản hồi nguồn và thời điểm thực sự nhận. Không lưu toàn bộ XML/JSON gốc trong DB, nên hash là dấu vết capture, không cho phép tự phục dựng response gốc.
- Bài biến mất khỏi cửa sổ RSS không tự coi là bị rút. Chưa có giao thức xác nhận xóa/rút của từng publisher. Phải kiểm tra link gốc trước khi dùng làm bằng chứng tác động.
- Ticker mentions là khớp từ/cashtag cho5 công ty pilot, không phải entity resolution đầy đủ. Mọi tin có UNVERIFIED_NEWS, impactUNKNOWN, graph_eligible=false. Không đưa vào corpus đánh giá sau-freeze hoặc pipeline canonical nếu chưa qua bước kiểm tra tương ứng.

## X: adapter đã chuẩn bị, đang tắt

Theo lựa chọn của người dùng: chưa có X API, chạy RSS trước. Watchlist dự kiến: Reuters, business (Bloomberg), CNBC, YahooFinance; chưa xác minh numeric user IDs qua API thật. Mọi nguồn X trong config có enabled=false; helper Windows còn ép NEWS_ENABLE_X=false.

Adapter dùng API chính thức: resolve handle→numeric ID có đối chiếu username, lấy timeline theo since_id, loại retweet/reply và xử lý pagination tối đa5 trang. Cursor chỉ ghi sau khi nhận đủ batch; thiếu trang/lỗi partial không được advance. Nếu backlog vượt giới hạn, trạng thái X_BACKLOG_EXCEEDS_PAGE_CAP cần xử lý riêng, không âm thầm bỏ qua bài. Credential chỉ gửi api.x.com, không theo redirect hoặc gửi sang RSS.

X API có phí theo sử dụng. Trước khi bật cần tài khoản/API token, cấu hình giới hạn chi tiêu ở X Console và quyết định ngân sách. Không có token trong repo/log/UI. Hiện chưa có kiểm thử kết nối X thật; chưa hỗ trợ stream, edit/delete compliance hoặc lưu bài dài đầy đủ. Không bật X chỉ vì người dùng đăng nhập GitHub hay X trên trình duyệt.

## API riêng tư

- GET `/api/v0/news?limit=100&source=fed`: các tin mới nhất theo ngày đăng, tối đa200 bản ghi trước gom URL; nguồn thiếu ngày xếp sau. Không phải truy vấn lịch sử đầy đủ.
- GET `/api/v0/news/sources`: trạng thái và độ mới từng nguồn, không lộ credential/cursor.
- GET `/api/v0/news/{id}/history`: tối đa100 phiên bản, chỉ API nội bộ đã đăng nhập.

Đều yêu cầu tài khoản. Tin công khai được thu chung cho các thành viên đã xác thực; không trả nhãn, luận điểm hay dữ liệu riêng của thành viên khác. Gateway chỉ mở GET news/sources và trang /news; không mở API quản trị hay ghi dữ liệu. Token trang chỉ ở bộ nhớ, logout xóa nội dung và chặn response muộn phục hồi dữ liệu.
