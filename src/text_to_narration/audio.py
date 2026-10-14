"""Deterministic chunk planning, local synthesis, and independent audio validation."""

import importlib.metadata
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .common import read_json, require, sha256, write_json
from .models import verify_models
from .prepare import extract, substitute

RATE = 24000


def chunks(text, limit=480):
    """Split at sentence/word boundaries, retaining exact normalized word sequence."""
    words = text.split()
    result, current = [], []
    for word in words:
        if current and len(" ".join(current + [word])) > limit:
            result.append(" ".join(current))
            current = []
        current.append(word)
        if len(" ".join(current)) >= limit * 0.65 and re.search(r"[.!?]$", word):
            result.append(" ".join(current))
            current = []
    if current:
        result.append(" ".join(current))
    require(" ".join(result) == " ".join(words), "Text chunking changed content")
    return result


def check_source(output):
    output = Path(output)
    manifest = read_json(output / "narration-manifest.json")
    require(manifest.get("schema_version") == 1, "Unsupported manifest schema")
    require(sha256(output / "source.txt") == manifest["source_sha256"], "Source snapshot changed")
    records, coverage = extract(
        (output / "source.txt").read_text(encoding="utf-8-sig"),
        manifest["format"],
        manifest["stop_headings"],
    )
    for i, segment in enumerate(records):
        segment.update(id=i, original_text=segment["text"])
        segment["text"] = substitute(segment["text"], manifest["pronunciations"]["replacements"])
    require(records == manifest["segments"], "Segments differ from source; prepare again")
    require(coverage == read_json(output / "source-coverage.json"), "Source coverage changed")
    transcript = "\n\n".join(s["text"] for s in records) + "\n"
    require(
        (output / "transcript.txt").read_text(encoding="utf-8") == transcript,
        "Transcript differs from source segments",
    )
    require(
        sha256(output / "transcript.txt") == manifest["transcript_sha256"],
        "Transcript hash differs",
    )
    return manifest


def dependencies():
    os.environ["ORT_DISABLE_TELEMETRY"] = "1"
    try:
        import numpy as np
        import soundfile as sf
    except ImportError as exc:
        raise RuntimeError("Install audio dependencies: pip install -e '.[tts]'") from exc
    require(shutil.which("ffmpeg") is not None, "FFmpeg is required on PATH (with libmp3lame)")
    return np, sf


def plan(manifest):
    result = []
    for i, segment in enumerate(manifest["segments"]):
        parts = chunks(segment["text"])
        for j, part in enumerate(parts):
            last = j == len(parts) - 1
            next_heading = i + 1 < len(manifest["segments"]) and manifest["segments"][i + 1][
                "kind"
            ] in {"heading", "title"}
            pause = (
                1.25
                if last and (segment["kind"] in {"heading", "title"} or next_heading)
                else (0.55 if last else 0.20)
            )
            result.append(
                {
                    "index": len(result),
                    "segment": i,
                    "text": part,
                    "pause_after_samples": round(pause * RATE),
                }
            )
    return result


def render(output, models, voice="af_heart", speed=0.98, threads=4, max_seconds=None):
    output, models = Path(output), Path(models)
    manifest = check_source(output)
    require(
        manifest["status"] == "prepared", "This run already started; use a fresh output directory"
    )
    require(0.5 <= speed <= 2.0, "Kokoro speed must be between 0.5 and 2.0")
    require(threads > 0, "Threads must be positive")
    model_hashes = verify_models(models)
    np, sf = dependencies()
    import onnxruntime as ort

    ort.disable_telemetry_events()
    from kokoro_onnx import Kokoro

    options = ort.SessionOptions()
    options.intra_op_num_threads, options.inter_op_num_threads = threads, 1
    session = ort.InferenceSession(
        str(models / "kokoro-v1.0.onnx"), sess_options=options, providers=["CPUExecutionProvider"]
    )
    engine = Kokoro.from_session(session, str(models / "voices-v1.0.bin"))
    require(voice in engine.voices, f"Unknown voice: {voice}")
    manifest.update(
        status="rendering",
        voice=voice,
        speed=speed,
        threads=threads,
        language="en-us",
        model_sha256=model_hashes,
        max_seconds=max_seconds,
        versions={
            name: importlib.metadata.version(name)
            for name in ["kokoro-onnx", "onnxruntime", "numpy", "soundfile", "phonemizer"]
        },
    )
    write_json(output / "narration-manifest.json", manifest)
    (output / "chunks").mkdir(exist_ok=False)
    timeline = []
    cursor = 0
    # Stream the master to disk rather than keeping an article-sized waveform in memory.
    with sf.SoundFile(
        output / "narration-master.wav", "w", samplerate=RATE, channels=1, subtype="PCM_24"
    ) as master:
        for item in plan(manifest):
            phonemes = engine.tokenizer.phonemize(item["text"], "en-us")
            original_phonemes = phonemes
            for old, new in manifest["pronunciations"]["phoneme_overrides"].items():
                phonemes = phonemes.replace(old, new)
            batches = engine._split_phonemes(phonemes)
            require(bool(batches) and max(map(len, batches)) <= 510, "Invalid phoneme batch length")
            require(
                "".join(phonemes.split()) == "".join("".join(b.split()) for b in batches),
                "Phoneme splitting omitted content",
            )
            samples, rate = engine.create(
                phonemes,
                voice=voice,
                speed=speed,
                lang="en-us",
                is_phonemes=True,
                trim=True,
                sentence_pause=0.28,
                clause_pause=0.12,
            )
            require(
                rate == RATE and samples.ndim == 1 and len(samples) > 0,
                "Unexpected model audio format or empty output",
            )
            require(
                np.isfinite(samples).all() and 0.001 < np.max(np.abs(samples)) < 1,
                "Model produced silent, non-finite, or clipped audio",
            )
            filename = f"chunks/{item['index']:05d}.wav"
            sf.write(output / filename, samples, RATE, subtype="PCM_24")
            # Read quantized chunk so the master and validation compare identical PCM.
            samples, _ = sf.read(output / filename, dtype="float32")
            master.write(samples)
            master.write(np.zeros(item["pause_after_samples"], dtype="float32"))
            timeline.append(
                {
                    **item,
                    "file": filename,
                    "start_sample": cursor,
                    "end_sample": cursor + len(samples),
                    "phonemes": phonemes,
                    "original_phonemes": original_phonemes,
                    "phoneme_lengths": list(map(len, batches)),
                    "sha256": sha256(output / filename),
                }
            )
            cursor += len(samples) + item["pause_after_samples"]
            write_json(output / "narration-timeline.json", timeline)
            print(f"Chunk {len(timeline)} complete; {cursor / RATE:.1f} seconds", flush=True)
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-n",
            "-i",
            str(output / "narration-master.wav"),
            "-af",
            "loudnorm=I=-18:TP=-2:LRA=7",
            "-ar",
            str(RATE),
            "-ac",
            "1",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "64k",
            str(output / "narration.mp3"),
        ],
        check=True,
    )
    manifest.update(
        status="generated",
        master_sha256=sha256(output / "narration-master.wav"),
        mp3_sha256=sha256(output / "narration.mp3"),
    )
    write_json(output / "narration-manifest.json", manifest)
    return validate(output, max_seconds)


def validate(output, max_seconds=None):
    output = Path(output)
    report = output / "audio-validation.json"
    # Never leave an older passing report looking current after a failed recheck.
    write_json(report, {"status": "validating"})
    try:
        return _validate(output, max_seconds)
    except Exception as exc:
        if read_json(report).get("status") != "duration_exceeded":
            write_json(report, {"status": "failed", "error": str(exc)})
        raise


def _validate(output, max_seconds=None):
    output = Path(output)
    np, sf = dependencies()
    manifest = check_source(output)
    require(manifest["status"] == "generated", "Run did not finish generating audio")
    timeline = read_json(output / "narration-timeline.json")
    expected = plan(manifest)
    require(len(timeline) == len(expected), "Missing or extra audio chunks")
    require(
        sha256(output / "narration-master.wav") == manifest["master_sha256"], "Master hash differs"
    )
    require(sha256(output / "narration.mp3") == manifest["mp3_sha256"], "MP3 hash differs")
    outliers, cursor = [], 0
    with sf.SoundFile(output / "narration-master.wav") as master:
        require(master.samplerate == RATE and master.channels == 1, "Invalid master format")
        for actual, wanted in zip(timeline, expected):
            require(
                all(actual[k] == v for k, v in wanted.items()), "Chunk order/text/pause differs"
            )
            require(actual["file"] == f"chunks/{actual['index']:05d}.wav", "Unexpected chunk path")
            path = output / actual["file"]
            require(sha256(path) == actual["sha256"], "Chunk hash differs")
            audio, rate = sf.read(path, dtype="float32")
            require(
                rate == RATE and audio.ndim == 1 and len(audio) > 0 and np.isfinite(audio).all(),
                "Invalid chunk audio",
            )
            require(
                0.001 < np.max(np.abs(audio)) < 1 and np.sqrt(np.mean(audio**2)) > 0.0001,
                "Silent or clipped chunk",
            )
            require(
                actual["start_sample"] == cursor and actual["end_sample"] == cursor + len(audio),
                "Timeline sample boundaries differ",
            )
            require(
                np.array_equal(master.read(len(audio), dtype="float32"), audio),
                "Master/chunk mismatch",
            )
            silence = master.read(actual["pause_after_samples"], dtype="float32")
            require(
                len(silence) == actual["pause_after_samples"] and not np.any(silence),
                "Pause differs",
            )
            cursor += len(audio) + len(silence)
            wpm = len(actual["text"].split()) / (len(audio) / RATE) * 60
            if not 60 < wpm < 280:
                outliers.append({"chunk": actual["index"], "words_per_minute": wpm})
        require(master.frames == cursor, "Trailing or missing master audio")
    # Decode to a temporary WAV on disk to avoid article-sized pipe buffers.
    fd, name = tempfile.mkstemp(prefix="decoded-check-", suffix=".wav", dir=output)
    os.close(fd)
    decoded_path = Path(name)
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-xerror",
                "-y",
                "-i",
                str(output / "narration.mp3"),
                "-ar",
                str(RATE),
                "-ac",
                "1",
                "-c:a",
                "pcm_f32le",
                str(decoded_path),
            ],
            check=True,
        )
        frames, peak, quiet, longest = 0, 0.0, 0, 0
        with sf.SoundFile(decoded_path) as decoded:
            for block in decoded.blocks(blocksize=RATE * 10, dtype="float32"):
                require(np.isfinite(block).all(), "Decoded MP3 contains non-finite values")
                frames += len(block)
                peak = max(peak, float(np.max(np.abs(block))))
                flags = np.abs(block) < 10 ** (-45 / 20)
                edges = np.flatnonzero(np.diff(np.r_[False, flags, False].astype(int)))
                for start, end in zip(edges[::2], edges[1::2]):
                    length = end - start + (quiet if start == 0 else 0)
                    longest = max(longest, int(length))
                quiet = length if len(edges) and edges[-1] == len(block) else 0
        require(frames > 0 and abs(frames - cursor) <= RATE * 0.1, "MP3/master duration mismatch")
        require(0.001 < peak < 1, "Decoded MP3 is silent or clipped")
    finally:
        decoded_path.unlink(missing_ok=True)
    limit = max_seconds if max_seconds is not None else manifest.get("max_seconds")
    duration_ok = limit is None or frames / RATE < limit
    result = {
        "status": "duration_exceeded"
        if not duration_ok
        else "needs_review"
        if outliers or longest / RATE >= 3
        else "passed",
        "decoded_duration_seconds": frames / RATE,
        "max_seconds": limit,
        "source_sha256": manifest["source_sha256"],
        "mp3_sha256": manifest["mp3_sha256"],
        "master_sha256": manifest["master_sha256"],
        "chunks": len(timeline),
        "source_mapping_verified": True,
        "chunk_order_and_pcm_pauses_verified": True,
        "full_mp3_decode_verified": True,
        "peak": peak,
        "longest_quiet_seconds": longest / RATE,
        "speaking_rate_outliers": outliers,
        "listening_review": "not performed",
        "speech_recognition_review": "not performed",
    }
    write_json(output / "audio-validation.json", result)
    require(
        duration_ok,
        "Duration limit exceeded. Full audio was retained. Review/revise the source explicitly; no truncation or automatic speeding was performed.",
    )
    return result
