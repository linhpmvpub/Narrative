"""Reviewed event frames join source bodies to atlas factors without keyword rules."""
import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from engine.evaluation.article_relevance import reviewed_body, utc
from engine.impact_atlas import MECHANISMS, Scenario, read_snapshot, scenario
from engine.ingestion.contracts import digest


class EventFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=100)
    version: int = Field(ge=1)
    mechanism_id: str
    factor_id: str
    direction: Literal["UP", "DOWN", "UNKNOWN"]
    phase: Literal["PROPOSED", "COMMITTED", "OPERATING"]
    scope: str = Field(min_length=1, max_length=2000)
    source_quote: str = Field(min_length=1, max_length=8000)
    selection_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    available_at: AwareDatetime
    reviewed_at: AwareDatetime
    reviewer_id: str = Field(min_length=1)
    reviewer_kind: Literal["HUMAN", "AI_OPERATOR"]


def assess(data, frame, selection, *, article_root=None, at=None):
    at = at or datetime.now(UTC)
    if (at.tzinfo is None or at > datetime.now(UTC) or frame.mechanism_id not in MECHANISMS
            or digest(selection) != frame.selection_sha256
            or not utc(data["as_of"]) <= at
            or not frame.available_at <= frame.reviewed_at <= at):
        raise ValueError("Event identity, mechanism or chronology invalid")
    packet, body = reviewed_body(selection, at, article_root=article_root)
    if (frame.source_quote not in body or utc(packet["retrieved_at"]) > frame.available_at
            or utc(selection["body_review"]["reviewed_at"]) > frame.reviewed_at):
        raise ValueError("Event quote or source availability invalid")
    result = scenario(data, Scenario(mechanism_id=frame.mechanism_id, factor_id=frame.factor_id,
        direction="UP" if frame.direction == "UNKNOWN" else frame.direction,
        phase=frame.phase, scope=frame.scope))
    if frame.direction == "UNKNOWN":
        result["conditional_channel_direction"] = "UNKNOWN"
    result.update(mode="REVIEWED_EVENT_CONTEXT_NOT_ACCEPTED_IMPACT", event=frame.model_dump(mode="json"),
        atlas_sha256=digest(data), source_packet_sha256=selection["packet_sha256"],
        source_url=selection["revision"]["payload"]["url"],
        source_check="CAPTURE_INTEGRITY_NOT_CURRENT_PUBLISHER_STATE",
        interpretation="Reviewer-declared event/factor attribution; not independently verified causality",
        blockers=["Event-to-exposure scope and mechanism applicability require review",
                  "Exposure magnitude, transmission and timing not established",
                  "No independent event-group calibration or current-source feed approval"])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["atlas", "frame", "selection", "articles", "output"]:
        parser.add_argument("--"+name, type=Path, required=True)
    args = parser.parse_args()
    data = read_snapshot(args.atlas)
    frame = EventFrame.model_validate_json(args.frame.read_bytes())
    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    result = assess(data, frame, selection, article_root=args.articles)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"paths": len(result["paths"]), "delivery": "disabled"}))


if __name__ == "__main__":
    main()
