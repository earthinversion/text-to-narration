"""Shared IO and explicit validation (also active under python -O)."""

import hashlib
import json
from pathlib import Path


class NarrationError(ValueError):
    """Actionable invalid-input or quality-control failure."""


def require(condition, message):
    if not condition:
        raise NarrationError(message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
