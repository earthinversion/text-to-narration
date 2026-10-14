import hashlib
import io

import pytest

from text_to_narration import models
from text_to_narration.common import NarrationError


def test_download_checksum_and_reuse(tmp_path, monkeypatch):
    payload = b"public test model placeholder"
    monkeypatch.setattr(models, "DIGESTS", {"model.bin": hashlib.sha256(payload).hexdigest()})
    calls = []

    def fetch(url, timeout):
        calls.append(url)
        return io.BytesIO(payload)

    monkeypatch.setattr(models, "urlopen", fetch)
    models.download_models(tmp_path)
    models.download_models(tmp_path)
    assert len(calls) == 1
    assert models.verify_models(tmp_path)


def test_download_checksum_failure_cleans_partial(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "DIGESTS", {"model.bin": "0" * 64})
    monkeypatch.setattr(models, "urlopen", lambda *a, **k: io.BytesIO(b"wrong"))
    with pytest.raises(NarrationError):
        models.download_models(tmp_path)
    assert list(tmp_path.iterdir()) == []
