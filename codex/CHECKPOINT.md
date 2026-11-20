# Checkpoint tiếp tục phiên sau — 2026-11-20

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
