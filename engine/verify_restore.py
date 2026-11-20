"""Read-only full-row comparison of two explicitly supplied validation databases."""

import argparse
import hashlib
import json
import os
from pathlib import Path

from sqlalchemy import MetaData, select

from engine.db import database


def snapshot(url):
    engine = database(url)
    try:
        with engine.connect() as conn:
            schema = MetaData()
            schema.reflect(conn)
            result = {}
            for name, table in sorted(schema.tables.items()):
                rows = sorted(
                    json.dumps(dict(row), sort_keys=True, default=str)
                    for row in conn.execute(select(table)).mappings()
                )
                result[name] = {
                    "rows": len(rows),
                    "sha256": hashlib.sha256(json.dumps(rows).encode()).hexdigest(),
                }
            return result
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source, target = os.environ["RESTORE_SOURCE_URL"], os.environ["RESTORE_TARGET_URL"]
    if source == target:
        raise ValueError("Source and restored databases must differ")
    before, after = snapshot(source), snapshot(target)
    result = {
        "match": before == after,
        "source": before,
        "restored": after,
        "note": "Disposable database drill; URLs and row contents omitted",
    }
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"match": result["match"], "tables": len(before)}))
    if not result["match"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
