"""JSON/JSONL evaluation workspace; never acquires sources or enables delivery."""

import argparse
import json
from pathlib import Path

from engine.evaluation.historical import Case, Label, Prediction, Split, evaluate, freeze
from engine.settings import Settings


def read_rows(path, model):
    return [
        model.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def save(path, value):
    # Refuse to replace frozen manifests, labels or prior evaluation artifacts.
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create a new empty collection workspace")
    init.add_argument("directory", type=Path)
    lock = commands.add_parser("freeze")
    lock.add_argument("--cases", type=Path, required=True)
    lock.add_argument("--split", type=Path, required=True)
    lock.add_argument("--output", type=Path, required=True)
    labels = commands.add_parser("label-template")
    labels.add_argument("--cases", type=Path, required=True)
    labels.add_argument("--output", type=Path, required=True)
    run = commands.add_parser("evaluate")
    for name in ("cases", "labels", "predictions", "manifest", "output"):
        run.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    Settings.from_env()  # Preserve disabled notification/LLM guards for every entry point.
    try:
        if args.command == "init":
            args.directory.mkdir(parents=True, exist_ok=False)
            for model in (Case, Label, Prediction, Split):
                save(
                    args.directory / (model.__name__.lower() + ".schema.json"),
                    model.model_json_schema(),
                )
            (args.directory / "cases.jsonl").write_text("", encoding="utf-8")
            save(
                args.directory / "status.json",
                {
                    "historical_events": 0,
                    "status": "PENDING approved sources and human labels",
                    "delivery": "disabled",
                },
            )
            print("Created empty workspace; no historical data or labels invented")
            return
        cases = read_rows(args.cases, Case)
        if args.command == "freeze":
            result = freeze(
                cases, Split.model_validate_json(args.split.read_text(encoding="utf-8"))
            )
        elif args.command == "label-template":
            # Nulls are intentional: unfinished gold labels must fail validation.
            with args.output.open("x", encoding="utf-8") as stream:
                for case in cases:
                    row = dict.fromkeys(Label.model_fields)
                    row.update(case_id=case.id, evidence_urls=[str(e.url) for e in case.evidence])
                    stream.write(json.dumps(row) + "\n")
            print("Created incomplete human-review template; no labels inferred")
            return
        else:
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            predictions = json.loads(args.predictions.read_text(encoding="utf-8"))
            if predictions["dataset_sha256"] != manifest["dataset_sha256"]:
                raise ValueError("Predictions belong to a different frozen corpus")
            result = evaluate(
                cases,
                read_rows(args.labels, Label),
                [Prediction.model_validate(p) for p in predictions["items"]],
                manifest,
            )
        save(args.output, result)
        print(json.dumps({"artifact": str(args.output), "delivery": "disabled"}))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, f"Evaluation refused: {exc}\n")


if __name__ == "__main__":
    main()
