"""Local research cards from reviewed full articles; no feed promotion or delivery."""

import argparse
import html
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from engine.company_profiles import available_bundles
from engine.evaluation.article_relevance import reviewed_body
from engine.ingestion.contracts import digest
from engine.news_articles import VisibleText, root_dir
from engine.news_capture import read_capture
from engine.profile_routing import binding_decisions
from engine.source_sentences import source_units

BLOCK_TAGS = {"p", "div", "section", "article", "h1", "h2", "h3", "h4", "li",
              "ul", "ol", "table", "tr", "td", "th", "br", "blockquote", "footer", "nav"}
BOILERPLATE = re.compile(
    r"^(about\s+.{1,90}|forward[-\s]looking statements?|cautionary statement|"
    r"safe harbor(?: statement)?|contacts?|investor contacts?)\s*:?$", re.I)
QUALIFICATION = re.compile(
    r"^(?:product density is identified|the definition of|\d+\s*(?:gb|tb|kb|mb)/s is calculated|"
    r"based on (?:internal|.*performance labs) (?:test|estimate)|"
    r"actual (?:results|performance|capacity) may vary)", re.I)


class Blocks(VisibleText):
    """Preserve V1 source offsets while recovering inline HTML paragraph boundaries."""
    def __init__(self):
        super().__init__()
        self.group = 0
        self.groups: list[int] = []

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        if tag in BLOCK_TAGS:
            self.group += 1

    def handle_endtag(self, tag):
        super().handle_endtag(tag)
        if tag in BLOCK_TAGS:
            self.group += 1

    def handle_data(self, data):
        before = len(self.parts)
        super().handle_data(data)
        if len(self.parts) > before:
            self.groups.append(self.group)


def substantive_blocks(selection, at, *, article_root=None):
    packet, _ = reviewed_body(selection, at, article_root=article_root)
    parser = Blocks()
    parser.feed(read_capture((Path(article_root) if article_root is not None else root_dir()) / "bodies", packet["body_sha256"], ".html").decode("utf-8-sig"))
    review = selection["body_review"]
    blocks: list[dict] = []
    offset = 0
    previous = None
    for value, group in zip(parser.parts, parser.groups, strict=True):
        start, end = offset, offset + len(value)
        offset = end + 1  # V1 joins normalized text nodes with a newline.
        if start < review["start"] or end > review["end"]:
            continue
        if any(start < b and end > a for a, b in review.get("related_link_ranges", [])):
            previous = None
            continue
        if group != previous:
            blocks.append({"text": "", "source_spans": []})
        block = blocks[-1]
        block["text"] += (" " if block["text"] else "") + value
        block["source_spans"].append({"start": start, "end": end, "text": value})
        previous = group
    substantive: list[dict] = []
    suppressed: list[dict] = []
    boilerplate = False
    for block in blocks:
        if BOILERPLATE.fullmatch(block["text"].strip()):
            boilerplate = True
        # Preserve full article in archive; suppress appendices from matching only.
        if boilerplate or re.match(r"^This (?:press )?release contains forward-looking", block["text"], re.I):
            boilerplate = True
            suppressed.append(block)
        else:
            (suppressed if QUALIFICATION.match(block["text"]) else substantive).append(block)
    return substantive, suppressed


def decisions(bundle, narrative, title, blocks, at):
    for field, block in [("title", {"text": title, "source_spans": []}),
                         *[("body", b) for b in blocks]]:
        # Apply same-sentence scope to all legacy bindings as well as scoped rules.
        for unit in source_units(block["text"]):
            for result in binding_decisions(bundle, narrative, {**unit, "context_title": title}, at):
                yield {"binding_id": result["binding"].id, "scope": result["binding"].scope,
                    "excerpt": unit["summary"].strip(), "field": field,
                    "source_spans": block["source_spans"],
                    "matches": [{**m, "field": field, "start": m["start"] + unit["source_offset"],
                                 "end": m["end"] + unit["source_offset"]} for m in result["matches"]],
                    "paragraph": block["text"],
                    "path": [edge.model_dump(mode="json") for edge in result["path"]],
                    "max_news_age_days": result["binding"].max_news_age_days}


def build(selections, at=None, *, profile_root=None, article_root=None):
    at = at or datetime.now(UTC)
    if at.tzinfo is None or at > datetime.now(UTC) or not 1 <= len(selections) <= 100:
        raise ValueError("Bounded selections and aware nonfuture time required")
    registry = available_bundles(at, root=profile_root)
    if not registry["enabled"] or registry.get("withheld") or registry.get("truncated"):
        raise ValueError("Complete validated research registry required")
    cards, audit, seen = [], [], set()
    for selection in selections:
        article = selection["revision"]["payload"]
        if article["url"] in seen:
            continue
        seen.add(article["url"])
        blocks, suppressed = substantive_blocks(selection, at, article_root=article_root)
        audit.append({"url": article["url"], "substantive_blocks": len(blocks),
                      "suppressed_blocks": len(suppressed), "archive_preserved": True})
        for bundle in registry["items"]:
            for narrative in bundle.narratives:
                hits = list(decisions(bundle, narrative, article["title"], blocks, at))
                if not hits:
                    continue
                best = next((h for h in hits if h["field"] == "body"), hits[0])
                age = (at - datetime.fromisoformat(article["published_at"])).total_seconds() / 86400
                fresh = any(age <= h["max_news_age_days"] for h in hits)
                named = bool(re.search(r"(?<!\w)" + re.escape(bundle.ticker) + r"(?!\w)",
                                       article["title"], re.I))
                company_name = re.sub(r"\s+(?:inc|corp|corporation|incorporated|ltd)\.?$", "",
                                      bundle.legal_name.strip(), flags=re.I)
                named = named or (len(company_name) >= 4 and bool(re.search(
                    r"(?<!\w)" + re.escape(company_name) + r"(?!\w)", article["title"], re.I)))
                cards.append({"id": digest([article["url"], bundle.id, bundle.version, narrative.id]),
                    "ticker": bundle.ticker, "headline": article["title"], "url": article["url"],
                    "published_at": article["published_at"], "profile_version": bundle.version,
                    "narrative": narrative.title, "narrative_id": narrative.id, "profile_id": bundle.id,
                    "summary": best["excerpt"], "summary_basis": "SOURCE_EXCERPT_NOT_GENERATED_CLAIM",
                    "why_relevant": best["scope"], "path": best["path"],
                    "nodes": {n.id: n.label for n in bundle.nodes},
                    "profile_sources": {s.id: str(s.url) for s in bundle.sources},
                    "evidence": {"packet_sha256": selection["packet_sha256"],
                                 "matches": hits, "source_url": article["url"]},
                    "freshness": "WITHIN_RULE_WINDOW" if fresh else "ARCHIVE_CONTEXT",
                    "coverage": "COMPANY_MENTION_NOT_VERIFIED_IMPACT" if named else "INDUSTRY_CONTEXT",
                    "unknowns": list(dict.fromkeys([*narrative.unknowns,
                        "Company-specific exposure, financial magnitude and direction remain unverified."])),
                    "stance": "RELATED_INFORMATION", "impact": "UNKNOWN", "delivery": "disabled",
                    "mode": "LOCAL_RESEARCH_PREVIEW_NOT_ACCEPTED_FEED"})
    cards.sort(key=lambda c: (c["freshness"] == "WITHIN_RULE_WINDOW",
                              c["coverage"] == "COMPANY_MENTION_NOT_VERIFIED_IMPACT",
                              c["published_at"]), reverse=True)
    return {"items": cards, "audit": audit, "at": at.isoformat(),
            "delivery": "disabled", "mode": "LOCAL_RESEARCH_PREVIEW_NOT_ACCEPTED_FEED"}


def render(result):
    def esc(value):
        return html.escape(str(value), quote=True)
    cards = []
    for card in result["items"]:
        path = " → ".join(dict.fromkeys(card["nodes"][node]
            for edge in card["path"] for node in [edge["from_id"], edge["to_id"]]))
        proof = ''.join(f'<p><b>{esc(edge["type"])}:</b> {esc(edge["scope"])}</p>'
            + ''.join(f'<blockquote>{esc(e["quote"])}</blockquote><a href="'
                f'{esc(card["profile_sources"][e["source_id"]])}" target="_blank" '
                'rel="noreferrer noopener">Nguồn hồ sơ</a>' for e in edge['evidence'])
            for edge in card['path'])
        cards.append(f'<article data-ticker="{esc(card["ticker"])}" '
            f'data-archive="{str(card["freshness"] == "ARCHIVE_CONTEXT").lower()}">'
            f'<small>{esc(card["ticker"])} · '
            f'{"Tin trong cửa sổ thời gian" if card["freshness"] == "WITHIN_RULE_WINDOW" else "Ngữ cảnh lịch sử"}'
            f' · {"Có đề cập công ty" if card["coverage"] == "COMPANY_MENTION_NOT_VERIFIED_IMPACT" else "Ngữ cảnh ngành"}</small>'
            f'<h2>{esc(card["headline"])}</h2><h3>{esc(card["narrative"])}</h3>'
            f'<blockquote>{esc(card["summary"])}</blockquote><p><b>Vì sao liên quan:</b> '
            f'{esc(card["why_relevant"])}</p><p class="path">{esc(path)}</p>'
            f'<p><b>Chưa xác minh:</b> {esc("; ".join(card["unknowns"]))}</p>'
            f'<details><summary>Bằng chứng đường liên quan</summary>{proof}</details>'
            f'<a href="{esc(card["url"])}" rel="noreferrer noopener" target="_blank">Đọc nguồn</a>'
            f'<p><small>{esc(card["published_at"])} · Hồ sơ v{card["profile_version"]}</small></p></article>')
    return ('<!doctype html><html lang="vi"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Tin liên quan đến narrative</title><style>body{font:16px system-ui;max-width:1000px;'
        'margin:auto;padding:20px;background:#f3f5f7;color:#142338}article{background:white;padding:24px;'
        'margin:20px 0;border-radius:12px}h2{font-size:22px}.path{padding:12px;background:#edf5ff}'
        'blockquote{margin:12px 0;border-left:3px solid #4780b3;padding-left:12px}small{color:#526273}'
        'input,select{padding:10px;max-width:90%;margin:6px}article[hidden]{display:none}'
        'blockquote,.path{overflow-wrap:anywhere}summary{cursor:pointer}</style>'
        '<h1>Tin liên quan đến narrative</h1><p>Bản nghiên cứu cục bộ · Thông báo tắt. '
        'Thẻ nêu ngữ cảnh có thể liên quan, chưa xác minh tác động tài chính. '
        'ARCHIVE_CONTEXT là tin lịch sử, không phải tin mới.</p>'
        '<label>Công ty <select id="ticker"><option value="">Tất cả</option>'
        + ''.join(f'<option>{esc(t)}</option>' for t in sorted({c['ticker'] for c in result['items']}))
        + '</select></label><label>Tìm tin / narrative <input id="search" type="search"></label>'
        '<label><input id="archive" type="checkbox" checked>Hiện ngữ cảnh lịch sử</label>'
        '<p id="count" aria-live="polite"></p>' + ''.join(cards)
        + '<script>const cards=[...document.querySelectorAll("article")];'
        'const ticker=document.getElementById("ticker"), search=document.getElementById("search"),'
        'archive=document.getElementById("archive");function filter(){let n=0;for(const c of cards){'
        'c.hidden=!!((ticker.value&&c.dataset.ticker!==ticker.value)||'
        '(!archive.checked&&c.dataset.archive==="true")||'
        '!c.textContent.toLowerCase().includes(search.value.toLowerCase()));if(!c.hidden)n++;}'
        'document.getElementById("count").textContent=n+" thẻ tin phù hợp";}'
        '[ticker,search,archive].forEach(x=>x.addEventListener("input",filter));filter();</script></html>')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selections", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(json.loads(args.selections.read_text(encoding="utf-8")))
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "cards.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output / "index.html").write_text(render(result), encoding="utf-8")
    print(json.dumps({"cards": len(result["items"]), "delivery": "disabled"}))


if __name__ == "__main__":
    main()
