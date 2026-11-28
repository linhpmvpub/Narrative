# Nguyên tắc và bài học phát triển

## L034 — Sản phẩm công ty độc lập với narrative mẫu (2026-11-28)

- Căn cứ là chỉ đạo sản phẩm của người dùng, không phải kết quả đo mới: company intelligence là nền, narrative tùy chọn là sản phẩm nâng cao. Không để ví dụ thử nghiệm trở thành biên giới nhận diện tin, database hay hàm mục tiêu.
- Company relevance, đánh giá cơ chế và ưu tiên công ty phải tồn tại khi không có narrative. Thêm/xóa narrative không được đổi kết quả công ty trên cùng nguồn/phiên bản. Tin có liên quan không nên chỉ tồn tại như phần phụ “chưa gắn narrative”; kiểm tra cả ranking/API/UI, không chỉ matcher.
- Chọn benchmark đúng sản phẩm: direct company truth và company priority, giải thích, nhóm tin và độ phủ. Giữ nhãn/điểm mixed cũ để hồi quy; tạo chuẩn có phiên bản trước nhãn cho mục tiêu mới, không hồi tố thay trọng số để báo tăng điểm.
- Theo dõi luận điểm cần giữ bản gốc, lần sửa, tiêu chí quan sát và thời hạn. Evidence support khác outcome correctness; nhiều tin cùng nói một điều không phải nhiều bằng chứng độc lập hay phần trăm dự đoán đúng. Lưu phản bác và phần chưa biết, không chỉ tin xác nhận quan điểm.
- Chấm lịch sử chỉ dùng những gì có thể biết ở thời điểm đó; correction/supersession không xóa lịch sử cũ. Tách cơ chế, kết quả kinh doanh và diễn biến giá. Chuẩn bị provenance/thời gian ngay ở nền; chưa chuyển nguồn lực sang tối ưu catalog narrative mẫu.


## L033 — Preserve relevant unassigned company context without inventing a narrative (2026-11-28)

- Separate company discovery from narrative attribution in runtime as well as measurement. A bounded issuer event or sourced exposure may be useful company context with no watched endpoint. Keep that state explicit; never manufacture demand→supply links. Evidence:3company recoveries with all3240narrative/priority decisions unchanged;25.18vs21.82fixed-anchor index.
- A factor route needs an independent company-membership proof to its product/segment/metric. Limit membership to sourced ownership/metric links; customer/competitor edges are not ownership. Require exact current mechanism IDs and review/effective time. Company-only bindings need explicit discovery scope and no narrative target; test both model loading and staging, since a stage-only validator left an orphan gap.
- Broader company truth must not be evaluated against old narrow narrative-union negatives. Score new discovery only where direct company references were frozen; preserve old proxy and all target errors. Legacy historical/current profiles can differ for the same source-company; enforce prediction consistency only for direct reference units. This is a scope correction, not relabelling or changing score weights.
- More background cards are not automatically useful news.22unassigned cards include19MU infrastructure contexts with no independent labels. Keep source-reported statements, conditional product exposure and unknown financial consequences separate in UI; do not promote context to alert. Directed diagrams must show actual edge direction, not reverse membership as a causal claim.
- Validate source lifecycle, corrections, withdrawals, freshness, pins, deduplication and mobile/logout for the complete path. A headless routed snapshot validates rendering, not running-server availability or remote access. Continue fuller source/context review and new event-family evaluation; do not tune a growing list of ticker/headline exceptions against exposed labels.


## L032 — Company discovery needs its own truth and denominator (2026-11-28)

- A narrative error and an undiscovered company event are different. Keep pair-level target errors even when another narrative finds the article. Conversely, independently label company relevance outside watched narratives; a union of narrative labels cannot reveal those misses. Evidence: new20article benchmark has24company misses,5outside all watched narratives; legacy infra160 has9target misses but only2company-proxy misses. These are different questions, not gains from relabelling.
- Aggregate company decisions by exact article/source representation, then company; never merge unrelated versions/articles just because event clustering connects them. A negative legacy union needs complete observed target inventory. Missing/ambiguous references remain unresolved. Validate duplicate targets and direct company/narrative contradictions.
- An understandable scalar is a reporting aid. Lock formula/sample/predictions before labels; include unresolved coverage and disclose the evidence ceiling. First21.82/100 has a68/100 ceiling from this fixed reference's uncertainty. Do not normalize it upward after seeing labels, compare different samples as algorithm gains, or hide group/ticker regressions behind a net score. Future changed labels require a new benchmark version.
- Zero false positives over very few selections can coexist with poor usefulness. Here4company positives were found and24missed;3priority pairs found and8missed.44company units unresolved, including26reviewer disagreements, show evidence/reference limits as well. Report counts and positive support, not an unqualified100%precision claim. AI agreement is not human gold; company dossiers can constrain both reviewers' view.
- Improve the shared discovery→classification→graph→narrative→explanation flow. A source-backed company-context candidate may remain unassigned to narrative; never manufacture a demand→supply link to force assignment. Next validate renamed-company cases, explicit issuer identity, absent/withdrawn exposures, multiple article versions and relevant company events outside current narratives. Keep fixed exposed regression plus genuinely unused-content evaluation; no ticker/headline branches.


## L031 — Preserve source references and distinguish target misses from discovery misses (2026-11-28)

- Resolve only an explicit typed role/asset from an unambiguous adjacent source sentence, at most one hop. Preserve both spans; never rewrite source text or combine title and body to manufacture an assertion. A role reference does not verify legal identity, and a data-center reference does not make its operator a supplier/customer. Keep ambiguous, canceled and remote antecedents withheld.
- A matcher should identify the reviewed mechanism it consumes. Another valid demand edge cannot replace a revoked exact access/finance edge. Capital plus a physical deployment purpose differs from funding software, a component startup, disbursement or delivered capacity. Each route still needs its own source and narrative intent; no demand→supply shortcut.
- Measure narrative relevance separately from company-level discovery. In infra160, seven of nine missed target pairs already select another relevant narrative for the same company/event; all four missed priority pairs already have priority there. This does not repair the original target or justify changing its labels. Use the diagnosis to review scope/endpoints and prioritize truly undiscovered events, not to optimize a misleading aggregate.
- All 3,040 exposed pair decisions and the refreshed94card selection stayed unchanged this turn; synthetic tests establish capability, not real-world improvement. After repeated zero-change iterations, prioritize unused real families and source-backed database gaps over further grammar expansion. Keep narrative and company-discovery metrics separate and frozen before new independent review.
- Verify same-source/full-body parity, literal offsets, role/asset ambiguity, canceled antecedents, exact-edge lifecycle with alternative paths, RSS corrections/withdrawal and finance/supply negatives using renamed companies. No fresh/human or financial-impact claim follows from these checks.


## L030 — Unknown publication is explicit evidence, not an invented date (2026-11-28)

- Official product/technical pages can substantiate structural exposure without establishing original publication or historical effective dates. Store original publication as null with source kind, uncertainty basis and review note. A displayed update is separate from publication; acquisition/review is when the system learned, not when the real-world relationship began.
- Keep literal source bytes/hash/URL/quote review. A metadata label does not authenticate a publisher. Require graph validity/knowledge no earlier than capture; no undated backfill into dated events, metric observations or financial extraction/scope bindings. Preserve legacy dated serialization and expose uncertainty in the atlas.
- A product capability may support conditional customer deployment and a shared resource context path. It does not establish a current incident, realized demand change, financial magnitude or construction-permit dependency. Source each declared resource/mechanism; do not reuse a demand path as a supply path to satisfy an exposed label.
- Evidence: DELL source-backed power/cooling profile adds1factor/2edges;3040pair benchmark improves1relevance decision and changes no priority decisions. The current feed snapshot remains unchanged. Distinguish database completeness, measured regression improvement and live usefulness; do not imply one proves the others.
- Verify with source-time invalidity cases, financial/event rejection, atlas serialization, renamed companies and unrelated-market/component/negation cases; rerun benchmark independently after runtime and profile updates. Fresh-family/human and financial-impact evaluation remain separate future work.


## L029 — A capability description is not a new operating event (2026-11-28)

- A sourced company path plus resource words can surface an unrelated article when the matched passage merely describes a persistent state. Classify the statement role after its own literal evidence matches; a title may retain relevant descriptive context but must not supply missing actors/resources or bridge unrelated clauses.
- A specialization/capability marker must govern the matched activity. Do not let company-description modifiers suppress a separate project action, or return the first descriptive candidate before checking later substantive ones. Retained descriptions remain context_only/BACKGROUND through priority and explanation.
- Evidence: new shared guard preserves all3040exposed benchmark decisions and removes1unlabelled background card from the same local snapshot. This is a behavior change, not a demonstrated market-accuracy gain. Keep zero-gain results, old failures and unknown labels visible; tests establish contracts, not user usefulness.
- Source discovery has its own boundary: an HTTP200redirect to a listing is not the requested release, and a displayed article date can coexist with older prospective wording. Preserve URL/status/hash/retrieval time and unknown effective dates; do not backdate new profile knowledge or promote a search snippet to source evidence.
- Verify with renamed companies/resources, headline/body separation, secondary substantive statements, original offsets, RSS correction/withdrawal and unchanged full-body benchmark references. Add independently labelled unused families for generalization; no ticker/headline exclusions.


## L028 — Resource availability is distinct from component efficiency (2026-11-28)

- Evidence: the first readiness matcher improved4exposed relevance decisions but added1false positive by mixing component power efficiency with memory capacity. Same-sentence co-occurrence was insufficient. Requiring a bounded resource-condition phrase removed the regression while preserving the4recoveries; no ticker or headline exception was added.
- Put source-backed exposure and mechanism into data first; declare resource, operating scope and exact mechanism in an opt-in binding. Customer deployment requires a demand path, manufacturing utility dependence a supply path. Do not substitute one to satisfy broad labels.
- Generic engineering explainers can be conditional background without verified company facilities, identity, orders or quantified financial effects. Keep context_only through priority; a graph match does not prove a company incident or merit push.
- Background remains subject to quality review: current-feed sponsored facility descriptions can match even when the primary news concerns something else. One such example lacks independent labels. Next review primary-event/paragraph scope and incidental descriptions as a shared failure class; do not credit an unlabelled selection as correct.
- Keep initial failed runs and compare the final result to the original task baseline. Here0→4improvements is the cumulative outcome, not5by adding the correction of the newly introduced error. Tests and exposed AI labels do not establish fresh generalization or causal truth.


## L027 — Graph roles, source event roles and economic outcomes are distinct (2026-11-28)

- One node can be a sourced competitor, buyer and supplier through different directed, scoped edges. Product competition does not establish a company-wide identity or the technology vendor of every facility it operates. Preserve all current roles and their source IDs; do not infer customer/supplier edges from a name in news.
- Operator-only infrastructure context can remain conditional. Explicit other-vendor technology and a third-party collaboration still need their own applicability checks; a conservative exclusion is not proof of exclusive supply. Step1changed no3040benchmark decisions, so its generalization benefit is not independently demonstrated.
- An access restriction must bind access to the actual resource in the same clause, not a building entrance or unrelated analyst/company mention. Current implementation routes sourced demand/deployment paths only; do not fabricate supply effects from a demand-side event. Optional typed matchers must reject overlapping guards and foreign company aliases rather than silently bypass them.
- Capital backing plus operating purpose is distinct from disbursed funds, new capacity, ownership and customer orders. Keep source spans/planned phase, reject litigation/conferences/software/other clauses and do not borrow amounts across fields. Existing graph relevance is still required before editorial priority.
- Evidence: step2recovers1exposed relevance+2priority decisions,step3adds1priority decision; other3040pair decisions unchanged. These are exposed AI references, not independent holdout/human gold. After each step retain benchmark, tests, losses and cumulative comparison to task-start baseline; final hardening must also be rerun.
- Remaining4infra160priority misses are all unmatched upstream. Next work should address sourced profile/graph applicability and implicit subjects, not simply lower ranking thresholds. A successful software test or clearer trace is not proof of financial magnitude or causal impact.


## L026 — Benchmark freshness and dimensions must be explicit (2026-11-28)

- Evidence: importing10previous cohorts and rerunning3040pairs reproduced every stored relevance/priority decision. Relevance labels cannot substitute for priority labels; three older cohorts intentionally report priority unmeasured. Exposed AI references are regression, not fresh holdout/human truth.
- Pin original packets, reviews/consensus, source bodies, targets and normalized membership. Version inputs separately from runtime/database runs; never overwrite baselines. Final runtime/profile/source fingerprints must match the actual run. A passing freshness gate does not mean release acceptance.
- Preserve individual gains, losses and unknown outcomes instead of reporting only net counts. One priority recovery on infra160 coexists with two older full-body downgrades without priority labels; the latter cannot be called correct or harmless from these references.
- Tests found that an old generic change-word fallback could rescue a rejected interruption object (conference about production). Typed rejection must retain its boundary through fallback; validate active/passive/planned forms, unrelated objects and renamed companies. Conservative withholding also needs recall review; no ticker/headline exception.
- Keep current-profile replay timestamps explicit. Do not pretend new database knowledge existed at the event date. After any runtime/config/profile update, rerun/check the local suite and document temporal/data effects; retain old exposed suites and add independently reviewed event families separately.


## L025 — Event roles constrain shared-market applicability

- Evidence2026-11-28: adding sourced participant/competitor scope removes one exposed full-body relevance/priority false positive while leaving the other2879pair decisions unchanged. A valid infrastructure event plus a general demand edge is insufficient when the source assigns the project to another vendor. Generic market context may remain useful without identifying a beneficiary.
- Store own names and competition scope in reviewed profile data with source evidence, graph references, versions and validity. Parse roles/asset links in the source window. A company merely mentioned as analyst/employer/in another clause is not a project actor; an operator is not necessarily the technology supplier. Joint participation is not exclusive supply or a verified order.
- Keep first rejected sentence from suppressing a later independently valid sentence. Never rescue an inapplicable asset using a headline or unrelated company activity. Verify renamed companies, coordinated subjects, foreign/unknown technology, correction and source/relationship withdrawal.
- URL/text novelty alone missed three already-used economic-family articles in the prelabel sample. Exclude known repeated events before labels, retain exclusion records, and report cluster sensitivity for correlated fresh stories. Frozen independent AI review can expose new coverage gaps; it must not become a same-turn tuning set. No human-gold or public-acceptance claim.


### L024 follow-up — purpose recovery and market scope costs (2026-11-28)

- Source-local action/object/purpose semantics recover4exposed memory priority positives without extra resolved FP there; allocations, changed input access and agreements are distinct from delivered capacity or realized financial benefit. Preserve exact spans and phase rather than requiring absent amounts or inferring terms.
- Opt-in sourced market-demand paths recover7RSS120 relevance positives but add1FP in another full-body cohort. A valid generic infrastructure event plus a company demand edge still does not prove that vendor participates. Address actor/asset/platform applicability as shared graph data/contract, not ticker exceptions or a lower score threshold.
- Keep four unsupported supply-target misses and original negative labels. Do not manufacture demand-to-supply causality, quietly move a target, or reinterpret unresolved selections to improve metrics. Validate renamed actors, vendor-specific versus broad-market scope, expiry/withdrawal, and unused-family relevance/priority separately. Development gain is not independent acceptance.


## L024 — Conditional relevance and editorial priority need separate contracts

- Evidence2026-11-28: scoped actor/event/phase/route eligibility adds3priority TP on actor77,6on framework121 and2on memory150 without new resolved priority FP; all relevance decisions unchanged. These exposed AI references are development evidence, not independent market acceptance. Five framework priority FP remain in legacy change-word/deployment paths.
- Keep context_only as conditional relation evidence; it need not suppress every concrete source development. Conversely, recognizing a sourced party is not an event. Record why a specific source assertion merits attention, while identity, realized operational results and financial magnitude remain unverified/UNKNOWN.
- Do not bypass upstream source/revision/freshness/withdrawal/graph gates or commodity thresholds through a new priority branch. Archived content priority is not today's news. Apply generic event/phase/object rules, not ticker/headline exceptions; preserve unresolved and downgraded-but-relevant background items.
- Verify both selection and false promotions. Numeric weights may stay unchanged while feature eligibility changes; do not call this learned impact calibration. Improve remaining legacy semantics, then use untouched families/publishers for independent evaluation.


### L024 follow-up — operating evidence and coverage costs (2026-11-28)

- Explicit action/object priority removes5exposed framework false promotions while retaining9correct selections, but withholds4memory priority positives across2articles. Preserve these costs and their background cards; a stricter gate is not automatically better quality. A demonstration/definition differs from a realized deployment; a concrete planned experiment can still be useful and needs its own phase, not a blanket research-content exclusion.
- The resolved-entity feature must come from the qualifying link, not another article link. Even that is relationship context, not verified causal actor identity. Keep source spans and financial UNKNOWN.
- Fresh12RSS/120pairs yield the same1TP/0FP/11FN relevance for old/new runtime;8priority misses are unmatched upstream. Fix source-backed applicability and narrative scope before weights. Two AI contexts and lexical novelty are limited evidence, not human truth or proven family independence. Freeze both actual runtimes before labels and do not tune after review; the new packet becomes exposed regression.


## L023 — Preserve source boundaries and diagnose priority independently

- Evidence2026-11-28: seven archived articles had302regex segments versus257shared-source segments; all2760exposed pair decisions stayed unchanged. A parser correction is not measured recall improvement. Keep exact spans and original quotes across RSS, article cards and review.
- Resolve actor references only from explicit source evidence, at most one hop within a bounded source block; trace antecedent, declaration and use. Never borrow a headline actor, infer an ambiguous pronoun or replace financial UNKNOWN with a naming heuristic. Test renamed actors, unrelated markets, absent declarations and withdrawn/expired routes.
- A concrete, relevant source claim may still be context-only. In actor77,4of5resolved priority-positive pairs match but are blocked by this policy. Audit every matched unit even if another unit wins a score tie; separate routing failure from editorial withholding before changing weights. Future promotion needs a reusable event/phase contract and held-out evidence, not per-ticker exceptions or removal of all context guards.


## L022 — Shared taxonomy needs scoped graph applicability, not ticker exceptions

- User direction2026-11-27: prioritize a reusable crawl→deduplicate→classify→bind→graph→rank→explain→deliver workflow. Company-specific content belongs in sourced profiles/relations, not headline-specific code branches. The shared signal API has no ticker input; renamed-company tests preserve decisions.
- Evidence: fresh121pairs/11articles, two independent AI contexts. On110 unchanged targets, new component-readiness bindings add4TP and3FP; source-backed generic memory dependency does not prove compatibility with a named platform. A shared classifier can still overgeneralize even without ticker branches.
- Diagnose scope in database/graph: actor, product/technology, end market, platform, broad industry constraint versus bilateral announcement, event phase. Missing scope stays unknown; do not replace it with confidence or adjust numerical weights to conceal a hard-routing error. Five legacy wafer-supply FPs likewise need source-party/operating-scope attribution, not a blacklist of publishers.
- Competition target migration retains4 old articles at company level but creates4 misses on the unchanged supply reference. Preserve those labels/misses and report target coverage separately; do not call movement between narratives a recall improvement. New competitor coverage needs materialized sourced relations, not merely a name buried in a source quote.
- Validation: same-sentence signal spans, no title donation, source withdrawal/expired-edge tests, unchanged legacy hashes, freeze-before-review and scope-transfer audit. New cohort is now exposed regression; do not tune it and call it holdout again. Only5 connected family components under conservative sensitivity; not enough for market acceptance. Next: shared assertion frame and typed applicability constraints, then a predeclared fresh event-family sample.


- Follow-up2026-11-27: shared actor/platform scope and complete peer materialization improve exposed121from24TP/8FP to30TP/0FP but lose3older supply positives. Generic joint/finance/agreement synthetic tests passed while those3losses remained. Report both; grammar support is not demonstrated real coverage. Require fresh-family evaluation before promotion and preserve source gates when a synthetic paragraph is too short for extraction.

- Follow-up2026-11-27, actor resolution: a typed accepted predicate and an independent legacy verb list were contradictory action gates. Use one authoritative action contract, retaining separate product/actor/graph/lifecycle gates. Sourced product/facility scope and traced acronym normalization recovered all3known supply misses;7other resolved positives are still missed on the new77pairset. Recovering regressions is not new-set improvement: candidate and actual previous runtime both5TP/0FP/7FN. Archive and execute the real previous runtime before labels when code changes; previous profiles executed by new code are not a valid previous-engine baseline. Keep unresolved labels and all prior targets. Next: typed consolidation/asset and explicit financing-purpose coverage, then genuinely unused multi-publisher families.

- Follow-up2026-11-27, asset/purpose scope: actor+transaction keyword+product somewhere in a sentence is insufficient. Bind the asset or use-of-proceeds object to the actual predicate; reject recipient/other-clause donation and silent object truncation. Sourced component classes limit applicability,not identity or verified output. Uniform6peer-binding migration recovers1exposed asset case; financing-purpose synthetic tests pass but recover0real financing cards. Report this distinction,keep6remaining misses and priority gap,then improve shared source boundaries/explicit references instead of expanding headline-specific vocabulary.

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
