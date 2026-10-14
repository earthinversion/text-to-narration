"""Explicit, checksum-verified downloads; synthesis never downloads models."""

from pathlib import Path
from urllib.request import urlopen

from .common import require, sha256

BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/"
DIGESTS = {
    "kokoro-v1.0.onnx": "7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5",
    "voices-v1.0.bin": "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d",
}


def verify_models(directory):
    for name, digest in DIGESTS.items():
        path = Path(directory) / name
        require(path.is_file(), f"Missing {path}; run download-models first")
        require(
            sha256(path) == digest, f"Checksum mismatch: {name}; stop and verify official release"
        )
    return dict(DIGESTS)


def download_models(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, digest in DIGESTS.items():
        target = directory / name
        if not target.exists():
            partial = directory / (name + ".download")
            try:
                with urlopen(BASE + name, timeout=120) as response, partial.open("wb") as handle:
                    while block := response.read(1024 * 1024):
                        handle.write(block)
                require(sha256(partial) == digest, f"Downloaded checksum mismatch: {name}")
                partial.replace(target)
            finally:
                partial.unlink(missing_ok=True)
        require(sha256(target) == digest, f"Existing checksum mismatch: {name}")
        print(f"Verified {name}", flush=True)
