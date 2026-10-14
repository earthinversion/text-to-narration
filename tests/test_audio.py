"""Optional FFmpeg integration tests without model downloads."""

import shutil

import pytest

from text_to_narration.audio import RATE, plan, validate
from text_to_narration.common import NarrationError, read_json, sha256, write_json
from text_to_narration.prepare import prepare

np = pytest.importorskip("numpy")
sf = pytest.importorskip("soundfile")

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg unavailable")


@pytest.fixture
def synthetic_run(tmp_path):
    import subprocess

    source = tmp_path / "sample.txt"
    source.write_text("A small original sample.", encoding="utf-8")
    out = tmp_path / "output"
    manifest = prepare(source, out)
    (out / "chunks").mkdir()
    item = plan(manifest)[0]
    audio = (0.2 * np.sin(2 * np.pi * 220 * np.arange(RATE * 2) / RATE)).astype("float32")
    path = out / "chunks/00000.wav"
    sf.write(path, audio, RATE, subtype="PCM_24")
    audio, _ = sf.read(path, dtype="float32")
    sf.write(
        out / "narration-master.wav",
        np.r_[audio, np.zeros(item["pause_after_samples"])],
        RATE,
        subtype="PCM_24",
    )
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(out / "narration-master.wav"),
            "-c:a",
            "libmp3lame",
            "-b:a",
            "64k",
            str(out / "narration.mp3"),
        ],
        check=True,
    )
    write_json(
        out / "narration-timeline.json",
        [
            {
                **item,
                "file": "chunks/00000.wav",
                "start_sample": 0,
                "end_sample": len(audio),
                "sha256": sha256(path),
            }
        ],
    )
    manifest.update(
        status="generated",
        master_sha256=sha256(out / "narration-master.wav"),
        mp3_sha256=sha256(out / "narration.mp3"),
    )
    write_json(out / "narration-manifest.json", manifest)
    return out


def test_full_decode_and_pcm(synthetic_run):
    result = validate(synthetic_run)
    assert result["status"] == "passed"
    assert result["decoded_duration_seconds"] == pytest.approx(2.55, abs=0.1)


def test_strict_duration_retains_audio(synthetic_run):
    before = sha256(synthetic_run / "narration.mp3")
    with pytest.raises(NarrationError, match="Duration limit exceeded"):
        validate(synthetic_run, max_seconds=1)
    assert read_json(synthetic_run / "audio-validation.json")["status"] == "duration_exceeded"
    assert sha256(synthetic_run / "narration.mp3") == before


def test_chunk_tamper_fails(synthetic_run):
    (synthetic_run / "chunks/00000.wav").write_bytes(b"bad")
    with pytest.raises(NarrationError, match="Chunk hash differs"):
        validate(synthetic_run)


def test_existing_decode_file_preserved(synthetic_run):
    existing = synthetic_run / "decoded-check.wav"
    existing.write_bytes(b"user-owned content")
    validate(synthetic_run)
    assert existing.read_bytes() == b"user-owned content"
    assert not list(synthetic_run.glob("decoded-check-*.wav"))


def test_failed_recheck_invalidates_old_pass(synthetic_run):
    assert validate(synthetic_run)["status"] == "passed"
    (synthetic_run / "chunks/00000.wav").write_bytes(b"bad")
    with pytest.raises(NarrationError, match="Chunk hash differs"):
        validate(synthetic_run)
    assert read_json(synthetic_run / "audio-validation.json")["status"] == "failed"


def test_duration_boundary_is_strict(synthetic_run):
    result = validate(synthetic_run)
    with pytest.raises(NarrationError, match="Duration limit exceeded"):
        validate(synthetic_run, result["decoded_duration_seconds"])
