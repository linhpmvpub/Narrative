"""Private content-addressed RSS bodies, before text decoding or normalization.

These are HTTP-decoded entity bytes, not compressed wire bytes. A matching hash
proves byte integrity only, never publisher authenticity or claim correctness.
"""

import hashlib
import os
import re
import tempfile
from pathlib import Path

LIMIT = 3_000_000


def read_capture(root, sha):
    if not isinstance(sha, str) or not re.fullmatch(r"[a-f0-9]{64}", sha):
        raise ValueError("Invalid capture hash")
    path = Path(root) / (sha + ".rss")
    with path.open("rb") as stream:
        body = stream.read(LIMIT + 1)
    if len(body) > LIMIT or hashlib.sha256(body).hexdigest() != sha:
        raise ValueError("Capture integrity mismatch")
    return body


def archive_capture(root, body):
    if len(body) > LIMIT:
        raise ValueError("Capture exceeds size limit")
    sha = hashlib.sha256(body).hexdigest()
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    target = root / (sha + ".rss")
    # Publish a complete fsynced file without overwriting an existing capture.
    # A failed DB transaction may leave an orphan; it must never leave a revision
    # referring to a partial file. Existing corruption is reported, not repaired.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=root, suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError:
            pass
        read_capture(root, sha)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return sha
