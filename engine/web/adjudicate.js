"use strict";
const $ = id => document.getElementById(id);
let token = "", epoch = 0, items = [], dirty = false;
const prefix = "/api/v0/admin/evaluation";
const url = () => `${prefix}/${$("packet").value}`;
function notice(text) { $("notice").textContent = text; }
async function api(path, body) {
  const generation = epoch;
  const response = await fetch(path, {method: body ? "POST" : "GET", headers: {
    Authorization: `Bearer ${token}`, ...(body ? {"Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID()} : {})
  }, ...(body ? {body: JSON.stringify(body)} : {})});
  const data = await response.json();
  if (generation !== epoch) throw new Error("Phiên đã kết thúc.");
  if (!response.ok) throw new Error(data.message || `HTTP ${response.status}`);
  return data;
}
function element(tag, text) { const e = document.createElement(tag); e.textContent = text; return e; }
function renderQueue() {
  const visible = items.filter(c => $("filter").value === "all" || ["DISAGREEMENT", "ADJUDICATION_DEFERRED"].includes(c.status));
  $("count").textContent = `${visible.length} / ${items.length} ca · Chỉ hiển thị nhãn đã lưu, không tự tạo nhãn.`;
  $("cases").replaceChildren();
  for (const c of visible) {
    const button = element("button", `${c.ticker} · ${c.kind} · ${c.status} · ${c.vote_count} người`);
    button.onclick = () => openCase(c.id).catch(e => notice(e.message));
    $("cases").append(button);
  }
}
async function refresh() {
  const base = url();
  const [queue, report] = await Promise.all([api(base + "/cases"), api(base + "/quality")]);
  if (base !== url()) return;
  items = queue.items;
  const lines = [`${report.total_cases} ca · ${report.gold_cases} nhãn người thật · ${report.status}`];
  const ai = report.ai_simulation;
  if (ai) {
    lines.push("AI MÔ PHỎNG — KHÔNG PHẢI ĐÁNH GIÁ ĐỘC LẬP BỞI CON NGƯỜI",
      `Nhà đầu tư cá nhân: ${ai.profiles.retail_investor}/${ai.total_cases}; nhà quản lý quỹ: ${ai.profiles.fund_manager}/${ai.total_cases}`,
      `Bất đồng ban đầu: ${ai.initial_disagreements}; chuyên gia đã xử lý: ${ai.profiles.financial_expert}; còn chờ: ${ai.pending_adjudications}`,
      `Chốt AI: ${ai.resolved_disagreements}; hoãn: ${ai.deferred_disagreements}. Nhãn người thật được tạo: 0.`,
      "Các agent có thể chia sẻ sai lệch của cùng mô hình. Tỷ lệ khớp AI không xác nhận độ chính xác hay tác động giá cổ phiếu.");
    for (const [kind, m] of Object.entries(ai.holdout_diagnostics || {})) lines.push(`Khớp nhãn AI · ${kind}: ${m.matches_ai_reference}/${m.scored} ca đã đối chiếu; độ phủ ${m.scored}/${m.total_holdout}.`);
  }
  const campaign = report.campaign_progress;
  const audit = report.language_error_audit;
  if (audit) {
    const h = audit.splits.holdout;
    lines.push("PHÂN TÍCH HỒI CỨU · BẢN THỬ NGHIỆM CHƯA ÁP DỤNG VÀO FEED",
      `Khớp nhãn AI: bản cũ ${h.baseline_matches_ai}/${h.cases}, bản thử nghiệm ${h.candidate_matches_ai}/${h.cases}; ${h.regressed_against_ai} ca giảm so với bản cũ.`,
      `${h.cases} ca nhưng chỉ ${h.unique_texts} đoạn văn khác nhau. Tập này đã được xem khi phát triển, không còn là kiểm chứng độc lập.`,
      "Đang chờ hồ sơ sau thời điểm khóa phiên bản và gán nhãn kín cho đợt mới. Graph và thông báo thật không đổi.");
  }
  if (campaign && campaign.configured) {
    lines.push(`TÀI KHOẢN DỰ PHÒNG CHO NGƯỜI THẬT · cần ${campaign.required_independent_labels} nhãn độc lập`);
    for (const r of campaign.reviewers) lines.push(`${r.slot}: ${r.current_source_completed}/${r.total} ca còn hiệu lực · đã gửi ${r.submitted} · cần làm ${r.actionable_remaining} · chờ nguồn ${r.source_blocked} · ${r.credential_active ? "tài khoản hoạt động" : "cần gia hạn tài khoản"}`);
    lines.push(`Đủ hai phiếu: ${campaign.cases_with_two_votes}; bất đồng chưa xử lý: ${campaign.unresolved_disagreements}; thẩm định cũ hết hiệu lực: ${campaign.stale_decisions}`);
  }
  for (const [kind, m] of Object.entries(report.holdout)) {
    lines.push(`${kind}: ${m.scored}/${m.total} ca holdout được chấm; đúng ${m.accuracy_on_resolved === null ? "chưa đủ nhãn" : (100*m.accuracy_on_resolved).toFixed(1)+"%"}; loại do nguồn ${m.source_excluded}`);
    const a = report.agreement[kind];
    lines.push(`Đồng thuận ban đầu: ${a.rate === null ? "chưa có cặp nhãn" : (100*a.rate).toFixed(1)+"%"} (${a.reviewer_pairs} cặp).`);
  }
  lines.push("Chỉ tính ca trong tập kiểm tra đã có nhãn tham chiếu; độ phủ thấp có thể làm sai lệch điểm.",
    "Chỉ đo phân loại văn bản và độ đúng của chỉ tiêu đã trích xuất; chưa đo được các chỉ tiêu bị bỏ sót.",
    "Đồng thuận không chứng minh quan hệ nhân quả. Tính độc lập của người đánh giá cần được xác nhận thực tế.",
    "Dữ liệu này đã được xem trong quá trình phát triển; cần hồ sơ kỳ mới trước khi khái quát chất lượng.");
  $("quality").textContent = lines.join("\n");
  $("quality").style.whiteSpace = "pre-wrap";
  renderQueue();
}
async function openCase(cid) {
  if (dirty && !confirm("Bỏ bản thẩm định chưa lưu?")) return;
  const base = url(), request = ++epoch;
  const data = await api(`${base}/cases/${cid}`);
  if (request !== epoch || base !== url()) return;
  dirty = false;
  const panel = $("detail"); panel.replaceChildren(element("h2", `${data.case.ticker} · ${data.status}`));
  const source = element("a", "Mở hồ sơ nguồn ↗");
  if (/^https:\/\//.test(data.case.source_url)) source.href = data.case.source_url;
  source.target = "_blank"; source.rel = "noopener noreferrer"; panel.append(source);
  const evidence = element("pre", JSON.stringify(data.case, null, 2)); evidence.style.whiteSpace = "pre-wrap"; evidence.style.overflowWrap = "anywhere"; panel.append(evidence);
  for (const v of data.votes) {
    panel.append(element("h3", `Người ${v.user_id} · phiên bản ${v.version}`));
    const vote = element("pre", JSON.stringify(v.payload, null, 2)); vote.style.whiteSpace = "pre-wrap"; vote.style.overflowWrap = "anywhere"; panel.append(vote);
  }
  if (data.decision) panel.append(element("p", `Thẩm định v${data.decision_version}${data.stale_adjudication ? " — ĐÃ HẾT HIỆU LỰC" : ""}: ${data.decision.payload.reason}`));
  if (data.self_review_forbidden || !["DISAGREEMENT", "ADJUDICATION_DEFERRED", "ADJUDICATED"].includes(data.status)) {
    panel.append(element("p", "Ca này chưa đủ điều kiện hoặc cần tài khoản thẩm định khác.")); return;
  }
  panel.append($("form-template").content.cloneNode(true));
  const update = () => {
    const resolved = $("outcome").value === "RESOLVED", language = data.case.kind === "causal_language";
    $("language-fields").hidden = !resolved || !language; $("numeric-fields").hidden = !resolved || language;
    $("language").required = resolved && language; $("verdict").required = resolved && !language;
    for (const side of ["current", "prior"]) for (const field of ["value", "start", "end"]) {
      $(side+"_"+field).required = resolved && !language && $("verdict").value === "COMPARABLE";
    }
  };
  $("decision-form").oninput = () => { dirty = true; update(); }; update();
  $("decision-form").onsubmit = async event => {
    event.preventDefault(); $("save").disabled = true;
    const body = {expected_vote_hash: data.vote_hash, expected_decision_version: data.decision_version,
      outcome: $("outcome").value, independent_of_extractor: $("independent").checked, reason: $("reason").value};
    if (body.outcome === "RESOLVED") {
      if (data.case.kind === "causal_language") body.language = $("language").value;
      else {
        body.numeric = {verdict: $("verdict").value, unit: "USD"};
        if (body.numeric.verdict === "COMPARABLE") for (const side of ["current", "prior"]) for (const field of ["value", "start", "end"]) body.numeric[side+"_"+field] = $(side+"_"+field).value;
      }
    }
    try {
      await api(`${base}/cases/${cid}/adjudications`, body); dirty = false;
      notice("Đã lưu phiên bản thẩm định. Thông báo thật: tắt."); await refresh(); await openCase(cid);
    } catch (e) { notice(e.message); if ($("save")) $("save").disabled = false; }
  };
}
$("login").onsubmit = async event => {
  event.preventDefault(); ++epoch; token = $("token").value.trim(); $("token").value = "";
  try {
    const data = await api(prefix+"/packets"); $("packet").replaceChildren();
    for (const p of data.items) { const o = element("option", `${p.case_count} ca · ${p.id.slice(0,12)}`); o.value = p.id; $("packet").append(o); }
    $("workspace").hidden = false; $("login").hidden = true; $("logout").hidden = false;
    if (data.items.length) await refresh(); else notice("Chưa có bộ đánh giá.");
  } catch (e) { notice(e.message); token = ""; }
};
$("logout").onclick = () => { ++epoch; token = ""; items = []; dirty = false; $("workspace").hidden = true; $("login").hidden = false; $("logout").hidden = true; for (const id of ["cases", "detail", "quality", "packet"]) $(id).replaceChildren(); notice(""); };
$("filter").onchange = renderQueue;
$("refresh").onclick = () => refresh().catch(e => notice(e.message));
$("packet").onchange = () => { ++epoch; dirty = false; $("detail").replaceChildren(); refresh().catch(e => notice(e.message)); };
window.addEventListener("beforeunload", e => { if (dirty) { e.preventDefault(); e.returnValue = ""; } });
