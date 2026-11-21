# Checkpoint tiếp tục phiên sau — cập nhật 2026-11-21

## Feed phát triển riêng tư — ưu tiên chỉ đạo mới 2026-11-21

- Người dùng đã yêu cầu tạm bỏ gate quyền nguồn, graph đã xác minh và materiality để xây hệ thống. Đã thực hiện bằng luồng **development informational feed** riêng, mặc định tắt; chỉ đạo này thay thế yêu cầu gate feed ở checkpoint cũ trong phạm vi phát triển riêng tư. Không cấp quyền/approval giả và không bật thông báo.
- `engine/development_feed.py`: lấy metadata từ SEC submissions API miễn phí, kiểm tra CIK/ticker/capture hash/time, lưu canonical notice theo issuer/accession; retry không trùng, sửa metadata tạo version/correction, chặn capture cũ ghi đè. Không trích xuất sự kiện kinh tế từ toàn văn. Nguồn vẫn pending, graph không được nâng thành verified, materiality UNKNOWN, stance INSUFFICIENT_EVIDENCE, score/path trống.
- Opt-in `DEV_INFORMATIONAL_FEED=true`; các cờ `SEND_NOTIFICATIONS=false`, `ALLOW_SYNTHETIC_LIVE=false`, `LLM_MODE=none` giữ nguyên. Không đổi migration: schema head vẫn 0006. Không gọi dispatcher, không có alerts.
- Projection theo đúng issuer vào stock/narrative của chủ tài khoản; card/version/correction riêng tư và as-of theo lúc hệ thống thực sự xử lý. Public stories lọc loại event phát triển trước pagination, kể cả link chia sẻ có sẵn. Tắt cờ thì private feed cũng ẩn các card này. UI có nhãn chưa kiểm duyệt và link nguồn.
- API mới `POST /api/v0/development-feed/refresh`: token thành viên, chỉ project cho chính chủ, retry idempotent, không gọi internet. UI gọi khi tải/làm mới feed để nhận cả các mục vừa subscribe. Thu thập internet là CLI chủ động, chưa có lịch tự chạy.
- Đã thu thập thật 50 canonical filing notices (10 mỗi MU/NVDA/AMD/DELL/SNDK), 50 versions, 30 cards riêng tư và 40 thread links; 0 alerts/reviews/permissions. Chạy lại collector toàn bộ duplicate và 0 link mới. Đây là metadata hồ sơ, không phải 50 economic claims đã xác minh. Báo cáo `reports/development-feed-{collection,retry,state,preview}.json`.
- DB mới ignored `rie-dev-feed.db`; cache ignored `source-cache/development-feed/`; preview loopback **http://127.0.0.1:8888** (đã restart code cuối; kiểm tra PID và command line trước khi dừng). Token 30 ngày ở ignored `secrets/development-feed-access-token.txt`, không in token/log/URL. Tài khoản preview theo dõi DELL, NVDA, MU, N08. Không chiếm cổng8765. SEC review DB vẫn 50 captures và 0 canonical/review/permission; synthetic DB không đổi.
- Chrome desktop/mobile: đăng nhập, 4 feeds mỗi feed10 notices, nhãn chưa kiểm duyệt, không tràn ngang/mobile, 0 JS errors; ảnh `reports/development-feed-{desktop,mobile}.png`. Ruff/mypy49 files/node syntax đạt; 15 file manifest gốc không đổi.
- Test cuối trên code đã sửa A → B → A: **237 passed SQLite (239.74s), 237 passed PostgreSQL (290.99s)**; mỗi suite 1 warning deprecation Starlette/httpx đã biết, 0 failures. Có 9 test mới. Báo cáo XML trong reports/development-feed-{sqlite,postgresql}-tests.xml. PostgreSQL disposable rie-release-validation được stop sau kiểm tra; preview8888 để chạy.
- Hướng dẫn chạy, API, nguồn SEC và giới hạn: `docs/development-feed.md`; OpenAPI và `.env.example` cập nhật. Container image chưa rebuild/Scout lại trong bước này; findings scan trước và production NO_GO vẫn còn. Không có remote/push/CI từ xa.
- Bước tiếp theo đề xuất: **thu thập tăng dần và xử lý hồ sơ bị sửa/rút**, thêm bộ lọc nguồn/thời gian; sau đó mở rộng tin IR chính thức. Chưa làm withdrawal detection/cross-accession grouping; projection hiện phù hợp pilot nhỏ. Luồng impact-feed đã kiểm duyệt thật và benchmark có nhãn độc lập vẫn là công việc riêng chưa hoàn thành.
- Lệnh tiếp tục: **“Đọc codex/CHECKPOINT.md, tiếp tục thu thập tăng dần và xử lý sửa/rút hồ sơ cho private development feed; giữ thông báo thật tắt.”**

## Ingestion đã triển khai — cập nhật sau workspace SEC, 2026-11-21

- Yêu cầu mới đã thực hiện: nối extraction đã được kiểm duyệt vào canonical ingestion, giữ thông báo thật tắt. Module `engine/ingestion/reviewed.py`, API `engine/api/sec_ingestion.py`, schema/migration `0006`. Hướng dẫn: `docs/reviewed-ingestion.md`; báo cáo: `reports/reviewed-ingestion-checkpoint.md`.
- Quyền nguồn/định danh là attestation riêng, có version, capture hash, CIK, bằng chứng, thời điểm server ghi và hạn sử dụng. Review nội dung không tự cấp quyền. Có API thu hồi và đọc lịch sử quyền.
- Ingestion kiểm tra lại source/review/version/quyền/as-of, commit nguyên tử event/document/evidence/receipt, xử lý retry/dedup/correction. Canonical available_at là lúc xử lý thật; không backdate về filing date. Snapshot operator theo as-of không dùng để tự động xuất bản feed.
- Endpoints mới: POST `/api/v0/admin/sec/filings/{id}/permissions`; GET cùng đường dẫn; POST `/api/v0/admin/sec/drafts/{id}/ingest`; GET `/api/v0/admin/sec/events`. Mutations yêu cầu operator token và Idempotency-Key. UI chưa có form cho permission/ingest; dùng OpenAPI/guide.
- Review store thật được backup trong ignored backups/ và migrate 0006. Preview cổng 8886 đã restart. Vẫn 50 captures, 0 real drafts/reviews/permissions/promotions/events/alerts/cards. Không tự cấp quyền hoặc tạo review cho hồ sơ thật để demo.
- Test mới: 20 acceptance cases cho permission, stale version, temporal gates, rollback, correction/reprint và concurrent operators. SQLite full rerun trên code sửa cuối: 228 passed. PostgreSQL full rerun: 228 passed (246.97s); SQLite 225.99s; mỗi suite một cảnh báo Starlette/httpx, không lỗi. Ruff/mypy 48 file đạt; full flow trong Docker bằng dữ liệu giả đạt và không có alerts/cards.
- Đã sửa một variable collision trong nhánh correction được phát hiện bởi full regression, rồi chạy lại tests. Image đã rebuild với bản sửa; Docker smoke import installed wheel từ /tmp, schema 0006.
- Các giới hạn còn lại: same-capture extraction amendment chưa hỗ trợ (correction hiện cross-capture); nguồn/graph/materiality/gold labels vẫn cần người duyệt thật; image-security findings của phiên trước còn mở; GitHub chưa push. Không tự bật notifications.
- Bước tiếp theo: **private-feed projection có gate từ canonical records**, kiểm tra current rights/review, verified graph và materiality trước khi đưa vào feed. Giữ decision và delivery tách biệt, delivery disabled.
- Lệnh nhắc: **“Đọc codex/CHECKPOINT.md và tiếp tục private-feed projection từ canonical events đã kiểm duyệt; giữ thông báo thật tắt.”**

Phần cập nhật workspace SEC dưới đây là mốc trước ingestion; không xây lại adapter đã hoàn thành.

## Cập nhật mới nhất — ưu tiên phần này khi tiếp tục

- Đã hoàn thành màn hình kiểm duyệt SEC: `engine/sec_review.py`, `engine/api/sec_review.py`, `engine/web/review.*`; migration `0005` / schema_v5. Chi tiết và giới hạn: `docs/sec-review.md`, bằng chứng: `reports/sec-review-checkpoint.md`.
- Database thật riêng `rie-sec-review.db`: nhập 50 capture, import retry không thêm bản trùng; 0 bản nháp thật, 0 review thật, 0 canonical event/feed card. Không sửa database demo cũ. Mode production chỉ có nghĩa nguồn không-synthetic, không phải go-live.
- Preview kiểm duyệt được để chạy ở `http://127.0.0.1:8886/review`; token operator trong `secrets/sec-review-access-token.txt` (Git ignore). Không in token, không đưa vào URL. Chưa tạo người duyệt thứ hai cho hồ sơ thật. Tài khoản thứ hai trong browser test chỉ tồn tại trong database test riêng dùng văn bản giả.
- Khi khởi động lại phải migrate head 0005 trước. Preview cũ cổng 8876 có thể vẫn chạy mã phiên trước; nếu khởi động lại thì dùng hướng dẫn đã cập nhật trong `docs/standalone-product.md`. Không chiếm cổng 8765.
- SQLite full suite: 206 passed, 161.24s; sau đó SEC-focused suite 19 passed, 35.62s, gồm 2 test bổ sung. PostgreSQL full suite mới: 208 passed, 217.60s. Tất cả chỉ có cảnh báo deprecation Starlette/httpx đã biết. Ruff/mypy 45 file/JS syntax đạt. Chrome workflow và desktop/mobile đạt.
- Đã sửa UTC serialization trên SQLite và race khi nhập form trong lúc đổi hồ sơ; workspace bị khóa tương tác trong lúc request, logout xóa form cũ. Giữ các regression này.
- Import chỉ staging. Review yêu cầu operator khác tác giả, quyền/citation/định danh/basis được xác nhận; approval lưu receipt bất biến nhưng `feed_eligible=false`. Không dùng receipt để tự vượt quyền nguồn, graph hoặc materiality.
- Form UI hiện sửa claim định tính; bản định lượng chỉ xem/duyệt. Một chuỗi draft/claim mỗi hồ sơ. Citation offset theo Unicode trong normalized text; bảng số phải đối chiếu nguồn gốc.
- GitHub repository tools vẫn không expose trong phiên này; không push/CI từ xa. Docker Scout đã chạy thành công sau quyền egress đã cấp; đăng nhập không còn là blocker. Đã vá zlib và bỏ pip runtime; scan còn 56 findings/13 packages (5 HIGH, 15 MEDIUM, 36 LOW), chưa có fixed version theo báo cáo. Xem reports/image-audit-status.json; production NO_GO. Giữ toàn bộ chỉ đạo và email đã có ở phần dưới.
- Công việc tiếp theo: **adapter đưa extraction đã duyệt vào canonical ingestion**, kiểm tra receipt/version còn hiệu lực, quyền nguồn/định danh thực sự được duyệt và as-of. Dùng test data giả để phát triển; không tự trích xuất/phê duyệt 50 hồ sơ thật thay người duyệt. Sau đó mới nối private feed và chuẩn bị benchmark với nhãn độc lập.
- Lệnh nhắc: **“Đọc codex/CHECKPOINT.md, tiếp tục adapter ingestion cho nguồn đã kiểm duyệt; giữ thông báo thật tắt.”**

Phần bên dưới là checkpoint nền của phiên 2026-11-20. Các mục “xây màn hình kiểm duyệt” và số lượng test cũ đã được thay thế bằng cập nhật ở trên.

## Đọc trước khi làm việc

Project root: `C:/Users/Admin/Desktop/Narrative/relationship_impact_engine_v0_codex_handoff/relationship_impact_engine_v0` (nằm bên trong workspace bên ngoài cùng tên handoff).

Đọc `codex/STATUS.md`, `reports/release-v0.md`, `docs/standalone-product.md`, rồi các module liên quan. `codex/TASKS.md` và tài liệu bàn giao gốc là đặc tả ban đầu, không phải sổ tiến độ hiện tại. Không triển khai lại P0–P4 chỉ vì checkbox gốc chưa đánh dấu. Giữ nguyên 15 file được bảo vệ bởi `MANIFEST_SHA256.txt`.

## Chỉ đạo đã xác nhận

- Không tồn tại repository Threadnote; phát triển Narrative độc lập, không yêu cầu lại repository đó.
- Người dùng muốn chủ động tiếp tục công việc và đề xuất bước tiếp theo sau khi xong.
- Email được cung cấp: `linhpm.vpub@gmail.com`; đã dùng cho SEC User-Agent và danh tính commit cục bộ. Chưa có tên tác giả riêng, nên tên hiển thị commit dùng đúng email, không suy đoán tên.
- Người dùng đã cho phép Docker Scout truyền dữ liệu từ image đến dịch vụ Docker. Không hỏi lại quyền truyền này. Lần thử vẫn bị chặn bởi yêu cầu đăng nhập Docker.
- Giữ `SEND_NOTIFICATIONS=false`, `ALLOW_SYNTHETIC_LIVE=false`, `LLM_MODE=none`. Không tự bật thông báo hay phát hành production.

## Đã hoàn thành

- Backend P0–P4: ingestion fixture, dedup/correction, graph có bằng chứng tối đa 2 hop, scoring/stance/trace, tài khoản riêng tư, subscription, phiên bản luận điểm, feed, feedback và chia sẻ chủ động.
- P5: công cụ evaluation, security và kiểm tra vận hành; đánh giá lịch sử bằng dữ liệu thật có nhãn chưa hoàn thành.
- UI tiếng Việt độc lập trong `engine/web/`; `/` phục vụ giao diện, demo F021/N08 chỉ đọc và ghi rõ synthetic. API mới `GET /api/v0/narratives` chỉ trả luận điểm của chủ tài khoản.
- Đóng gói UI trong wheel/Docker; CSP và allowlist asset không cho tải mã Python. Token trình duyệt chỉ ở bộ nhớ, không lưu localStorage/sessionStorage.
- Thu thập 50 hồ sơ SEC thật, 10 hồ sơ mỗi mã MU/NVDA/AMD/DELL/SNDK, 0 lỗi. Lưu trong `source-cache/sec-review-2026-11-20/` (Git ignore). Xem `collection.json` và `reports/sec-collection-summary.json`.
- Đây là 50 hồ sơ, KHÔNG phải 50 sự kiện canonical đã duyệt. Quyền sử dụng/nhãn vẫn pending; số sự kiện thật đã đánh giá = 0. Không lấy filing date để giả lập thời điểm engine đã biết dữ liệu trong quá khứ.
- Commit triển khai cục bộ: `a6945a6`, branch `main`. Không có remote/push/CI từ xa. Working tree sạch khi bắt đầu lưu checkpoint này.

## Bằng chứng kiểm tra đã chạy

- SQLite: 189 passed, 1 cảnh báo deprecation Starlette/httpx, 156.13s; `reports/standalone-sqlite-tests.xml`.
- PostgreSQL 16: 189 passed, cùng cảnh báo, 390.64s; `reports/standalone-postgresql-tests.xml`. Lần đầu database chưa khởi động xong; lần chạy lại sau readiness đã đạt đầy đủ.
- Sau sửa asset cuối: 2 test standalone đạt. Ruff, mypy (42 file engine), `node --check engine/web/app.js` đạt.
- Chrome/Playwright: demo desktop/mobile, đăng nhập, theo dõi cổ phiếu, tạo/xác nhận/theo dõi luận điểm, đăng xuất đạt; không lỗi JavaScript. `reports/browser-smoke.json`, `ui-desktop.png`, `ui-mobile.png`.
- Docker wheel đủ 4 asset; TLS shell/assets/readiness đạt, private API 401 và Python asset 404; `reports/standalone-container-smoke.json`.
- Trước đó: backup/restore so khớp 36 bảng, ingress/rate limit/log redaction đạt, Python dependency audit không có lỗ hổng đã biết sau cập nhật pip. OS/image scan chưa hoàn tất.
- 15 file gốc giữ nguyên checksum; `reports/original-package-integrity.json`.

## Trạng thái môi trường cục bộ

- Python 3.13; `.venv` cho app/test; `.audit-venv` cho pip-audit/Playwright, dùng Chrome đã cài.
- Preview được để chạy ở `http://127.0.0.1:8876`, DB `sqlite:///rie-p4-demo.db`, kiểm tra cuối `/healthz` trả ok/delivery disabled. Không giả định process còn sống ở phiên sau; kiểm tra trước khi khởi động lại. Cổng 8765 thuộc dịch vụ khác, không dừng/chiếm cổng đó.
- Khởi động nếu cần: đặt `$env:DATABASE_URL='sqlite:///rie-p4-demo.db'`, chạy `.venv/Scripts/python -m uvicorn engine.api:app --host 127.0.0.1 --port 8876 --no-access-log`. Nếu dùng Start-Process, chạy WindowStyle Hidden.
- Token preview trong `secrets/local-access-token.txt`, không in ra log/chat, không commit; hết hạn 30 ngày sau cấp. Tài khoản này đã chứa thao tác kiểm thử. Browser smoke yêu cầu tài khoản thử mới, không chạy lại với tài khoản thật/đã có dữ liệu.
- Docker Desktop được để chạy; container PostgreSQL `rie-release-validation` và Compose project `rie-staging-validation` đã STOP sau kiểm tra, dữ liệu/image giữ lại. DB `rie_test` chỉ để test phá hủy, `rie_demo` và `rie_restore` riêng biệt. Chờ pg_isready trước chạy tests; không dùng database của người dùng làm TEST_DATABASE_URL.
- `secrets/`, `source-cache/`, database, venv và log được Git ignore. Chứng chỉ TLS cục bộ một ngày có thể hết hạn; không dùng làm chứng chỉ production.

## Còn vướng — không yêu cầu lại thông tin đã có

- GitHub plugin đã installed/enabled, nhưng phiên trước không có repository tools được expose; gh chưa có, Git Credential Manager không có account và repository chưa có remote. Khám phá lại công cụ ở phiên mới; nếu khả dụng thì tiếp tục push/CI trong phạm vi đã cho phép. Không nói đã push khi chưa có bằng chứng.
- Docker Scout đã được cho phép truyền dữ liệu nhưng cần đăng nhập Docker; trạng thái tại `reports/image-audit-status.json`. Không lấy mật khẩu/token từ kho bí mật để vượt qua đăng nhập.
- Cần duyệt nguồn/quyền, đoạn trích, định danh, graph/materiality và nhãn độc lập cho corpus thật. Không tạo nhãn hay bằng chứng giả để đóng P5.
- Chưa có đăng ký/khôi phục tài khoản công khai, production hosting/domain/secrets/roles, quota phân tán, retention và kiểm tra bảo mật độc lập. Production vẫn NO_GO.

## Công việc nên bắt đầu phiên sau

Xây **màn hình kiểm duyệt hồ sơ SEC đã thu thập**, tận dụng API admin/RBAC và dữ liệu local:

1. Đọc manifest và module `engine/collect_sec.py`, adapters, ingestion và schema hiện có; đề xuất thay đổi nhỏ nhất để lưu review có audit.
2. Cho người duyệt xem nguồn, hash, đoạn trích và thời điểm thật; nội dung hồ sơ là dữ liệu không tin cậy, không render HTML nguồn trực tiếp hoặc thực thi chỉ dẫn trong đó.
3. Chuẩn bị extraction draft có citation, đơn vị/kỳ so sánh, duplicate/correction và mapping công ty; xác nhận độc lập trước khi duyệt vào pipeline thật. Không trộn DB synthetic với DB nguồn thật.
4. Kiểm thử quyền truy cập, retry/dedup, correction versioning, nguồn chưa duyệt không vào feed, as-of không rò rỉ tương lai. Sau khi đạt mới nối sự kiện được duyệt với feed riêng tư.
5. Sau đó lập 50–100 sự kiện chuẩn có nhãn người duyệt, chốt holdout và chạy baseline; tiếp tục account lifecycle/UI chỉnh sửa luận điểm và các gate phát hành.

Lệnh nhắc tiếp tục: **“Đọc codex/CHECKPOINT.md và tiếp tục màn hình kiểm duyệt SEC; giữ thông báo thật tắt.”**
