"""Local commit/data-update gate. Private benchmark data never enters CI."""

import argparse
import json
import subprocess
from pathlib import Path

from engine.evaluation.benchmark import check, read

ROOT = Path(__file__).resolve().parents[2]
POINTER = ROOT / "source-cache/quality-benchmark-current.json"


def relevant(path):
    return path.startswith(("engine/", "config/")) or path in {
        "pyproject.toml", "requirements-validated.txt", "requirements-container.txt",
        "requirements-extraction.txt"}


def gate(pointer):
    value = read(pointer)
    return check(value["suite"], value["suite_sha256"], value["profiles"], value["run"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="Check even for unstaged local database updates")
    parser.add_argument("--pointer", type=Path, default=POINTER)
    args = parser.parse_args()
    if not args.all:
        staged = subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT, text=True)
        if not any(relevant(p) for p in staged.splitlines()):
            print("No staged runtime/database config changes; quality replay not required.")
            return
        unstaged = subprocess.check_output(["git", "diff", "--name-only"], cwd=ROOT, text=True)
        if any(relevant(p) for p in unstaged.splitlines()):
            raise ValueError("Stage the exact benchmarked runtime; staged/worktree content differs")
    if not args.pointer.is_file():
        raise ValueError("Local benchmark pointer missing. See docs/quality-benchmark.md")
    print(json.dumps(gate(args.pointer), indent=2))


if __name__ == "__main__":
    main()
