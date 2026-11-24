"""Offline inspector for private atlas snapshots; no external assets or requests."""
import json
import secrets
from pathlib import Path


def render(data, output):
    nonce = secrets.token_hex(16)
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c").replace("&", "\\u0026")
    template = Path(__file__).with_name("web").joinpath("atlas.html").read_text(encoding="utf-8")
    script = Path(__file__).with_name("web").joinpath("atlas.js").read_text(encoding="utf-8")
    Path(output).write_text(template.replace("__NONCE__", nonce).replace("__DATA__", payload)
                           .replace("__SCRIPT__", script), encoding="utf-8")
