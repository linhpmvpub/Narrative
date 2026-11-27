# Nguyên tắc và bài học phát triển

## L018 — Đo đúng tầng lỗi và công khai thiếu coverage

- Đợt mới2026-11-26: RSS bỏ sót7cặp liên quan dù hạ ngưỡng; không có match đầu vào thì trọng số không khắc phục được. Tập đầy đủ3bài cho thấy phương án rộng tăng FP mà không tăng TP, liên quan đến nhầm phạm vi công ty/sản phẩm.
- Ưu tiên event role/action/phase và đường nối factor có nguồn, không tiếp tục tăng/giảm điểm để chữa lỗi upstream. Tin triển khai cụ thể cho đối thủ không tự thành nhu cầu khách hàng của công ty; cơ chế cạnh tranh và cơ chế dùng chung cần đường riêng.
- Quota nguồn không phải quota nhãn dương tính. Thu20bản tin issuer mới vào DB nhưng loại dữ liệu đã dùng còn0AMD/1Sandisk; báo đúng thiếu hụt, không lấp bằng bài cũ hoặc đổi tiêu chí sau khi nhìn nhãn.
- Kiểm chứng: hai reviewer độc lập, nhãn relevance/priority riêng, giữ bất đồng, source-body/packet/prediction hashes, tests chống drift và nới cửa sổ tin thật. Tập đã đo trở thành regression. Khắc phục tiếp cần corpus mới và positive support thật, không coi agreement AI hoặc tests là chất lượng sản phẩm.

## L017 — Nhãn liên quan không hiệu chỉnh được độ mạnh hoặc mức ưu tiên

- Bằng chứng2026-11-26: trên1716cặp RSS đã lộ nhãn, routing tìm54/96cặp liên quan, priority chỉ giữ19/96. Không có động từ chỉ hướng thay đổi không đồng nghĩa tin không hữu ích; quy tắc này bỏ sót cả bối cảnh có đường quan hệ.
- Tuy nhiên, đưa toàn bộ match lên thẻ chính chưa được chứng minh: reference đánh giá relevance, không đánh giá độ mới, mức quan trọng hay nhu cầu push. Phương án ngưỡng20đạt recall69.7%trên development validation, chưa đạt mục tiêu và không phải holdout mù mới.
- Hệ số không nhận diện được khi feature không biến thiên hoặc quyết định do hard gate; không gọi bộ40/30/20/20giữ nguyên là trọng số tác động đã học. Độ mạnh tài chính/độ trễ cần nhãn và dữ liệu riêng.
- Kiểm chứng: evaluator khóa split/predictions trước labels, tests chặn trộn validation, đếm cụm thay vì tăng support bằng nhiều narrative, giữ unresolved và kiểm hash. Thực hiện tiếp: tập mới cân bằng coverage, nhãn relevance/importance riêng, đánh giá candidate trước đổi chính sách feed.

## L015 — Chốt lõi dùng lại trước khi mở rộng coverage

- Quyết định người dùng 2026-11-25: khung v1 gọn, hoàn thiện database/thuật toán trước; hoãn đánh giá riêng priors và thực hiện đánh giá tổng thể ở giai đoạn sau. L014 giữ bài học về ranh giới bằng chứng nhưng đề xuất đánh giá riêng không còn là task ngay.
- Chia mã đầu vào dùng chung khỏi phạm vi sản phẩm công ty và thị trường báo giá. DDR5, HBM3 và HBM3e không phải alias của nhau; chip spot, module và hợp đồng mua không đồng nghĩa.
- Bằng chứng triển khai:7quan hệ đầu vào,4mã hàng hóa,2thị trường,3liên kết proxy; HBM3 dùng chung cho hai công ty nhưng mỗi quan hệ có nguồn riêng. Đây là inventory/routing, không phải completeness hoặc accuracy.
- Thêm công ty bằng hồ sơ + evidence + exposure, không thêm regex ticker. Duy trì7nhóm/10quan hệ cốt lõi; phần ngành đặc thù là extension, không bắt buộc mọi hồ sơ đầy đủ42component.
- Kiểm chứng: tests/test_input_markets.py kiểm tra ranh giới mã/đơn vị/nguồn, threshold và withdrawal; đánh giá hiệu suất toàn diện deferred theo chỉ đạo, không thay bằng số tests.

## L014 — Đo đúng giá trị bổ sung của tri thức nền

- Quan sát 2026-11-25: tích hợp prior hiện tại chỉ bổ sung giải thích cho thẻ đã ghép qua quan hệ có nguồn; quyết định ghép tin giữ nguyên theo contract. Synthetic CLI cho1thẻ ở cả hai nhánh, thêm1giải thích; không phải thử nghiệm thị trường.
- Phân biệt kiểm tra tiền đề nguồn với xác minh kết luận LLM.16prior khớp snapshot không đồng nghĩa16kết luận được nguồn xác nhận độc lập.
- Khi predictions giống nhau, không dùng precision/recall để tuyên bố prior tăng chất lượng. Đánh giá tính đúng/hữu ích của lời giải thích riêng; muốn đo coverage phải có dữ liệu quan hệ/đường ghép mới và tập tin mới phù hợp.
- Bằng chứng: engine/prior_context.py, tests/test_prior_context.py, báo cáo aggregate prior-context-progress.json. Chưa có nhãn độc lập; next ưu tiên nguồn bổ sung và gói đánh giá giải thích, không tạo cohort giả hoặc nâng trọng số để tạo chênh lệch.

## L013 — Ước lượng có nhãn khác với bịa dữ kiện

- Quyết định người dùng 2026-11-25: cho phép tri thức LLM phổ biến, không mơ hồ, suy luận tối đa một bước để bổ sung database. Sửa phạm vi L012: không cấm mọi ước lượng, chỉ cấm giả làm dữ kiện thật hoặc suy luận thiếu cơ sở.
- Giữ hai lớp: nguồn công bố và LLM_PRIOR_UNVERIFIED. Ưu tiên nguồn; không ghi đè UNKNOWN bằng một số được gọi là sourced. Prior có rule/version, tiền đề, scope, điều kiện, ngoại lệ, tác giả, thời điểm biết và hạn rà soát.
- Một bước nghĩa là từ quan hệ SOURCE_REPORTED tới kết luận có điều kiện; không lấy prior, cơ chế suy ra hoặc kết luận đối thủ làm tiền đề tiếp. Không suy từ đối thủ gián đoạn → công ty hưởng lợi → doanh thu tăng.
- Số ước lượng phải có khoảng, đơn vị/mẫu số và cách tính/ước lượng rõ. Mức định tính không chuyển thành xác suất hoặc phần trăm tùy ý. “Phổ biến/rõ ràng” là phán đoán của người/LLM biên soạn rule, chưa được phần mềm xác minh về ngữ nghĩa.
- Bằng chứng phần mềm: tests/test_knowledge_priors.py; dữ liệu thực bổ sung là prior chưa kiểm chứng, không phải nhãn độc lập. Tiếp theo đối chiếu prior với nguồn mới và đánh giá riêng sai lệch do tri thức nền.

## L012 — Dữ liệu thật, quan hệ đầu vào và độ lớn biến động

- Trạng thái: quyết định người dùng 2026-11-25; hành vi phần mềm có tests synthetic, chưa có đánh giá thị trường độc lập.
- Không bịa số liệu hoặc ngữ cảnh: giữ nguyên quote/span, đơn vị, tiền tệ, kỳ và phiên bản nguồn; phép tính phải có toán hạng thật và công thức. Tin chỉ nêu phần trăm thì không tự dựng giá gốc/giá mới. Kỳ tương đối giữ nguyên nhãn, không bịa ngày đầu/cuối.
- Database quan hệ có nguồn là nền tảng ghép tin; commodity không phải pháp nhân. Quan hệ USES_INPUT/DEPENDS_ON có nguồn đủ để tạo liên quan có điều kiện, không cần tên doanh nghiệp trong tin.
- Phân biệt observed / derived / inferred / unknown. Ngưỡng 5–10% phản ánh biến động giá hàng hóa; không suy ra lợi nhuận đổi cùng tỷ lệ hoặc xác suất tác động khi thiếu tỷ trọng, tồn kho, phòng hộ, hợp đồng và chuyển giá.
- Bằng chứng: tests/test_commodity_context.py; kiểm tra biên ngưỡng, tăng/giảm, sai đơn vị, nguồn rút, nguồn thay đổi và nhiều công ty cùng đầu vào. Các ca đều synthetic, không phải nhãn độc lập.
- Khắc phục tiếp: bổ sung danh mục đầu vào chuẩn hóa có nguồn và benchmark/grade/thị trường; đánh giá nhóm tin mới trước khi hiệu chỉnh ngưỡng hoặc đưa vào feed thật.

Cập nhật: 2026-11-25. Sổ kiến thức sống, được rà soát sau mỗi task; không phải mọi quan sát đều
là quy luật. Mục tiêu gốc nằm trong [PRODUCT_DIRECTION](PRODUCT_DIRECTION.md).

## Nguyên tắc ổn định

1. **Database có nguồn trước.** Pháp nhân, sản phẩm, quan hệ, phạm vi, kỳ và nguồn phải rõ trước
   khi ghép tin/định lượng. SNDK không phải WDC; cùng thương hiệu/tên gần nhau không chứng minh cùng pháp nhân.
2. **Phân biệt bằng chứng và kết luận.** Đồng xuất hiện tên, đường graph, trích dẫn đúng chữ hoặc
   hai phiếu duyệt chưa chứng minh nhân quả. Kế hoạch/cam kết không phải hoạt động/doanh thu thực hiện.
3. **Thiếu khác với bằng không.** UNKNOWN, NOT_APPLICABLE có căn cứ, chưa công bố, mâu thuẫn và
   đã bị thay thế phải khác nhau; không suy ra một tỷ lệ từ mô tả định tính.
4. **Phạm vi theo cơ chế.** Tin giá hàng hóa rộng và gián đoạn một cơ sở cần điều kiện khác nhau.
   Không bịa facility để đủ năm trường; không dùng thiếu magnitude để loại mọi tin bối cảnh.
5. **Thời gian và phiên bản là dữ liệu.** Tách xảy ra/công bố/thu thập/biết/hiệu lực/thẩm định.
   Replay chỉ dùng điều đã biết lúc đó; hiện trạng hồ sơ không được giả làm lịch sử as-of.
6. **Sửa lỗi tổng quát.** Tìm lớp lỗi trong ontology, dữ liệu, phạm vi, trích xuất, thời gian, xếp hạng
   hoặc giao diện. Sửa theo lớp và kiểm tra ca phản ví dụ, không vá từng headline để vượt benchmark.
7. **Đánh giá không rò rỉ.** Freeze trước gán nhãn, chia theo cụm sự kiện/kỳ, giữ riêng development/
   calibration/holdout. Tập đã xem trở thành regression. AI labels không phải human gold;
   nhiều bài cùng nguồn không thành nhiều xác nhận độc lập.
8. **Tối ưu hữu ích cho người dùng.** Coverage, precision, recall, giải thích và ưu tiên đều quan trọng.
   Lượt sửa hạ tầng phải phục vụ rủi ro cụ thể; không coi thêm công cụ/kiểm tra là hoàn thiện sản phẩm.
9. **Đo đúng điều đã làm.** Tests chứng minh hành vi phần mềm trong phạm vi test. Chỉ số thực nghiệm
   phải có cohort, mẫu số, mức unresolved và giới hạn; không biến pilot thành chất lượng toàn thị trường.
10. **Học có kiểm chứng.** Giữ kết quả thất bại, nguồn và phiên bản; supersede quyết định khi có bằng
    chứng mới. Không điều chỉnh target, đổi nhãn hoặc gộp cohort để làm đẹp số liệu.

## Sổ bài học đã tổng hợp

Ngày dưới đây là ngày ghi sổ. Bằng chứng chi tiết ở tài liệu liên kết; trạng thái “đã quan sát”
không có nghĩa đã giải quyết xong.

| ID / trạng thái | Quan sát và căn cứ | Quy tắc áp dụng / cách kiểm chứng |
|---|---|---|
| L001 · 2026-11-25 · định hướng người dùng | Nhiều lượt chỉnh ca nhỏ làm lệch ưu tiên database/bản đồ; [kế hoạch atlas](../docs/impact-atlas-plan.md) | Mỗi task nêu giá trị sản phẩm và lớp lỗi; đo theo nhóm tin trên nhiều công ty, không số bài được vá |
| L002 · 2026-11-25 · đã quan sát | Pilot trích xuất cũ có recall khoảng27–28%,25bất đồng chưa thẩm định; [benchmark](../docs/source-first-extraction-benchmark.md), checkpoint | Cải thiện lớp phát biểu/role/phase; cohort cũ chỉ regression, dùng cohort mới để đo tăng trưởng |
| L003 · 2026-11-25 · đã quan sát | RSS inbox có603items/771revisions/70items nhiều phiên bản tại lần audit; [báo cáo lifecycle](../reports/scope-source-lifecycle-progress.json) | Giữ ID/version và vô hiệu bản duyệt cũ; test sửa→đổi lại, retry và không churn epoch do poll lặp |
| L004 · 2026-11-25 · giới hạn thiết kế | Poll RSS mới không chứng minh toàn văn còn nguyên; mất bài không chứng minh rút; [lifecycle](../docs/scope-source-lifecycle.md) | Phân biệt freshness, lỗi fetch, disappearance, correction, confirmed withdrawal; cần revalidation toàn văn |
| L005 · 2026-11-25 · giới hạn thiết kế | R05 đòi cùng năm facet có thể giữ quá nhiều tin giá/nhu cầu rộng; [quality review](QUALITY_REVIEW.md) | Cần ma trận scope theo cơ chế. Đây là rủi ro đã nhận diện, CHƯA đo được mức recall bị mất; dùng ca rộng và near-miss để kiểm chứng |
| L006 · 2026-11-25 · đã kiểm chứng bằng synthetic | R05PASS không đủ R06/R07; nguồn rút làm bản duyệt cũ mất hiệu lực; [R05](../docs/scope-review-v1.md) | Test các tầng riêng; không biến source integrity hoặc local reviewer IDs thành causal proof/nhãn độc lập |
| L007 · 2026-11-25 · giới hạn dữ liệu | Tỷ trọng doanh thu, tồn kho, chuyển giá chỉ có nghĩa trong phạm vi/mẫu số/kỳ; [financial context](../docs/atlas-financial-context.md) | Kiểm tra đơn vị, segment, kỳ so sánh và thời điểm biết; không pooling tham số giữa quan hệ khác nhau |
| L008 · 2026-11-25 · giới hạn đánh giá | Nhiều bài/pair cùng sự kiện tương quan; current-profile archive khác backtest; [acceptance](../docs/product-v1-acceptance.md) | Báo theo cụm/công ty/cơ chế và giữ riêng kiểu replay; số pair không phải số sự kiện độc lập |
| L009 · 2026-11-25 · đã quan sát | README/start guide còn gọi dự án là seed và phụ thuộc Threadnote dù định hướng đã đổi | Điểm vào rõ, một nguồn mục tiêu hiện hành, lịch sử được gắn nhãn; kiểm tra link và xung đột khi thay quyết định |
| L010 · 2026-11-25 · giới hạn vận hành | Hash chain không chống rollback toàn store; hai lần đọc không là distributed transaction; [lifecycle](../docs/scope-source-lifecycle.md) | Trước delivery cần kiểm tra tại thời điểm dùng/durable invalidation; không gọi local snapshot là bảo đảm gửi thật |
| L011 · 2026-11-25 · đã kiểm chứng bằng synthetic | Một tin có phạm vi bối cảnh đủ căn cứ vẫn có thể chưa xác minh truyền tác động; [context scope](../docs/mechanism-context-scope.md) tạo CONTEXT/card riêng, giữ R05/R07UNKNOWN | Phân tầng output/gates, không nới gate tác động để cứu recall. Missing khác NA có căn cứ. L005 được xử lý một phần về phần mềm, chưa chứng minh cải thiện recall trên tin thật |

## Cách bổ sung và sửa bài học

Sau task, hỏi: có lỗi tái diễn, giả định bị bác bỏ, hiểu biết mới về người dùng/dữ liệu hoặc
quy tắc giảm lỗi có tính tái sử dụng không? Nếu có, thêm ID tăng dần với:

```text
ID — ngày ghi — trạng thái: giả thuyết / đã quan sát / đã kiểm chứng / bị thay thế
Quan sát: điều thực sự xảy ra; phân biệt synthetic và dữ liệu thật.
Bằng chứng: đường dẫn artifact/test/cohort/commit; chi tiết nhạy cảm để cục bộ.
Bài học: quy tắc tổng quát, phạm vi áp dụng và ngoại lệ.
Thay đổi đề xuất: dữ liệu, rule, workflow hoặc UX nào cần sửa.
Kiểm chứng: ca dương/âm, chỉ số và điều kiện bác bỏ bài học.
Liên kết: task/QUALITY_REVIEW; ID bị thay thế nếu có.
```

Gộp bài học trùng bằng liên kết; không ghi một quy tắc mới cho từng bài tin. Giữ ID cũ và đánh
dấu superseded kèm lý do khi bị bác bỏ. Chỉ nâng giả thuyết thành nguyên tắc ổn định khi có bằng
chứng hoặc quyết định rõ của người dùng. Không có bài học mới thì ghi “đã rà soát, không bổ sung”.
Rà soát định kỳ theo mốc phát triển, không tự tạo scheduler hay gửi thông báo vì yêu cầu này.

## L016 — 2026-11-26 — cross-source price inference authorized

User permits inferring price context by comparison with other sources. Match instrument,
capacity/grade, chip versus module, spot versus contract/retail and observation period
before treating prices as comparable. Similar numerical levels alone do not establish
identity or units. Preserve the original quote and separate observed values from a
one-step inferred unit convention; propagate CROSS_SOURCE_INFERRED and unit_verified=false.
Do not chain priors into invented profit/EPS effects. A secondary page can repeat the
primary source, so agreement is not automatically independent corroboration.

Observed example: the exact DDR5 chip is described as USD/die on a secondary page, but
its row date differs from its page update date. Use it only as labeled unit context,
not confirmation of today's price. Tests cover inferred-unit labeling, rejection of
multi-step metadata, correction/withdrawal, exact instrument and threshold suppression.
No independent market accuracy claim. Existing no-fabrication/source-period principles remain.


## L019 — 2026-11-26 — scope fixes require broad regression

Evidence: typed activity routing recovers6recent resolved positive pairs and removes2false positives,
but loses9previously positive older RSS pairs. A latest-cohort win is not overall improvement.
Keep a candidate local/experimental when broad regression worsens. Preserve labels, previous
predictions and selected unresolved counts; do not silently resolve a competitor-context
ambiguity in favor of a preferred score. Distinguish shared industry context, customer demand
and sourced competitor mechanisms in the database. Validate source-backed applicability and
all exposed cohorts before a fresh holdout. Event phase and editorial priority never establish
orders, profit direction or financial impact magnitude.


## L020 — 2026-11-27 — market applicability belongs to a sourced path

Component capacity and software capability are not additional infrastructure demand.
Restrict the target path, not the entire article: retain relevant input/competition
context through supported relationships. A title can constrain applicability but
cannot donate an assertion to another sentence. Record exact window evidence.

Evidence: a global component interpretation lost useful competitor context; adding
its sourced product path recovered it. A GPU guard also lowered a valid deployment
priority match until a general quantified deployment assertion was supported.
Verify both near-miss negatives and deployment positives, broad exposed regression
and unchanged unresolved counts. Announced capacity remains announced, never proof
of realized orders or financial effect. This does not establish independent accuracy.


## L021 — 2026-11-27 — sourced database coverage is not routing coverage

Observed: an unseen memory-company challenge contains10resolved MU positives, yet
none routes. Its profile already holds manufacturing/customer/competition facts,
while its two bindings cover narrow material terms and first-person supplier text.
Database completeness and executable news coverage must be checked separately.

For each relevant core group, trace source-backed factor -> applicable activity/market
scope -> traversable typed route -> narrative/card role. Mark missing routing explicitly;
do not add nodes or adjust weights as a substitute. Conditional component-readiness and
competitive context may be useful without proving a customer order or infrastructure demand.

Evidence: memory-unseen-2026-11-27 locked150pair two-AI challenge; aggregate report and
quality review. This is an observed development failure, not human-validated market truth.
Verify a repair on both exposed positives and scope near misses, retain earlier cohorts,
then evaluate a newly frozen candidate on unseen events. Never relabel failures to match rules.
