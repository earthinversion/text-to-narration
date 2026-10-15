# Text to Narration

Convert plain text or simple Markdown into local AI narration with Kokoro. Prepare a reviewable transcript, generate WAV and MP3 audio, and keep a record of how the source became spoken text.

**Author: [Utpal Kumar](https://github.com/earthinversion)**

This project turns a previously task-specific narration workflow into a reusable command-line tool. It includes a generic example article, configurable pronunciation replacements, and checks that can be run without downloading a speech model.

## Description

- Prepare text before generating audio, so you can inspect what will be spoken.
- Keep a source snapshot, source-line audit, and record of pronunciation substitutions.
- Generate narration locally with `kokoro-onnx` and an ONNX model.
- Export a 24-bit WAV master and a compact mono MP3.
- Check prepared-text coverage and audio properties; optionally enforce a duration limit.

Kokoro is an AI text-to-speech model. No hosted paid API or API key is needed. Installing dependencies and downloading the model require network access; narration runs locally after setup. This is not an AI-free workflow.

## Installation

Python 3.12 is recommended. Clone the repository first:

```bash
git clone https://github.com/earthinversion/text-to-narration.git
cd text-to-narration
```

Create and activate an environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

On Windows PowerShell, activate the environment with `.venv\Scripts\Activate.ps1` instead.

The core installation uses `markdown-it-py` and supports preparation and text checks. Install the optional speech dependencies to render audio:

```bash
python -m pip install -e '.[tts]'
```

This installs `kokoro-onnx==0.6.1`, NumPy, SoundFile, and ONNX Runtime. The exact versions used for the Linux CPU smoke test are recorded in `requirements-tested.txt`; optionally install them with `python -m pip install -r requirements-tested.txt`. These are observed versions, not a cross-platform lockfile. Install [FFmpeg](https://ffmpeg.org/download.html), using your platform's package manager or an official download route. Make FFmpeg available on `PATH`:

```bash
ffmpeg -version
```

## Run

### 1. Prepare the article

```bash
text-to-narration prepare examples/article.md \
  --output output \
  --pronunciations examples/pronunciations.json
```

Review the generated transcript and source-line audit before rendering. Use a new output directory for a new run; the tool refuses to overwrite existing output artifacts.

### 2. Download the model and voices

```bash
text-to-narration download-models --models models
```

The downloader uses the model files linked by the [official kokoro-onnx repository](https://github.com/thewh1teagle/kokoro-onnx):

- [kokoro-v1.0.onnx](https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx)
- [voices-v1.0.bin](https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin)

The downloader verifies these SHA-256 digests before using either file:

```text
7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5  kokoro-v1.0.onnx
bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d  voices-v1.0.bin
```

Keep these files in `models/`. Model files are downloaded separately and are not included in this repository.

### 3. Render the narration

```bash
text-to-narration render --output output --models models \
  --voice af_heart --speed 0.98 --threads 4
```

The MP3 export uses 64 kbps, mono, 24 kHz, with FFmpeg's `loudnorm` targets of -18 LUFS integrated loudness, -2 dBTP true peak, and 7 LU loudness range. These are processing targets, not a claim that every final file exactly achieves them.

### 4. Validate and listen

```bash
text-to-narration validate --output output
```

Read the validation report and listen to the finished recording. Check names, abbreviations, numbers, transitions, and the ending against the source before sharing it.

## Examples

### Narrate a plain-text file

```bash
text-to-narration prepare article.txt --format text --output output-text
text-to-narration render --output output-text --models models
text-to-narration validate --output output-text
```

### Include the full document

```bash
text-to-narration prepare examples/article.md --no-stop --output output-full
```

### Choose a stopping heading

```bash
text-to-narration prepare article.md --output output-custom \
  --stop-heading References --stop-heading Appendix
```

By default, preparation stops at `References` or `Further Reading`, matched case-insensitively as a Markdown heading (ignoring a trailing period or colon) or a standalone plain-text paragraph label. `--stop-heading` replaces the default stopping headings; repeat it to specify more than one. Stopping excludes the matching heading and everything after it. Check the audit to confirm the boundary is right for your document. Use `--no-stop` when no section should be excluded.

### Require a recording of strictly under ten minutes

```bash
text-to-narration render --output output --models models --max-seconds 600
text-to-narration validate --output output --max-seconds 600
```

There is **no default duration cap**. A limit is a validation requirement, not permission to summarize, cut the ending, or silently omit text. If the recording is too long, deliberately revise the source with the author’s approval and prepare a new run.

### Change pronunciations

Edit a copy of `examples/pronunciations.json` and pass its path to `prepare`:

```json
{
  "replacements": {
    "LLM": "L L M"
  },
  "phoneme_overrides": {}
}
```

Keep `AI` unchanged: the pinned Kokoro tokenizer already produces both letter names (“ay eye”). Do not replace it with `A I`: the tokenizer treats the separated `A` as a weak article (“uh”), which can make the result sound like just “I”. Punctuation spellings such as `A.I.` are also context-sensitive and are not recommended as a workaround.

Use explicit spoken replacements for other technical terms and abbreviations. The original source is retained and substitutions are recorded, so review the resulting transcript for unintended changes. Numbers and citations are not automatically rewritten or removed. Plain-text mode does not invent a title.

## Supported input

Use UTF-8 plain text or simple Markdown. Markdown support includes headings, paragraphs, lists, blockquotes, inline links, and emphasis. Links are rendered as their visible text; formatting is not spoken literally.

Reference-style link definitions, code, tables, images, HTML, and mathematical notation require deliberate spoken descriptions. Unsupported constructs fail clearly rather than being silently dropped. Rewrite those passages into ordinary prose before preparing the narration. Plain-text mode treats the input as text; it does not interpret or explain technical notation for you.

PDF, Word, and web-page extraction are outside the scope of this tool. Convert and review those sources yourself first.

## Outputs and checks

Preparation produces:

- `source.txt`: original source snapshot
- `transcript.txt`: prepared spoken text
- `source-coverage.json`: per-line accounting and exclusions
- `narration-manifest.json`: segment records and pronunciation changes

Rendering adds:

- `chunks/00000.wav`, etc.: synthesized audio segments
- `narration-timeline.json`: segment timing
- `narration-master.wav`: 24-bit WAV master
- `narration.mp3`: delivery copy
- `audio-validation.json`: audio checks

The audit accounts for source lines and records exclusions. Coverage checks compare prepared text and segment records. Audio checks inspect the generated files and requested duration constraint. They do **not** prove that the model pronounced every word correctly, preserved the meaning, or produced natural narration. There is no automatic listening or semantic verification. Human review remains necessary.

Output files may contain the complete input text. Keep private articles, generated audio, model downloads, and local output directories out of version control. Only narrate and distribute material you have permission to use.

## Troubleshooting

- Missing model or checksum mismatch: use `download-models` and the exact official files above. Do not disable hash checks or silently substitute a quantized model.
- Missing speech packages: activate your environment, then install `.[tts]`. Python 3.12 is the tested inference environment; platform wheel availability varies.
- FFmpeg or `libmp3lame` not found: install a build with MP3 encoding support and check `ffmpeg -encoders`.
- Unsupported Markdown: write a faithful spoken version of code, equations, tables, or images and review that source. The parser is intentionally conservative rather than a general document converter.
- A failed/interrupted render: the partial run remains available for inspection. Prepare into a fresh directory and retry. Automatic resume is not currently supported.
- `duration_exceeded`: the complete recording is retained. Nothing is sped up or truncated. Revise the source explicitly, then prepare and render a new run.
- `needs_review`: investigate speaking-rate anomalies or unexpectedly long quiet passages and listen before delivery. Exit code 2 marks review-needed output; exit code 1 marks an error; 0 marks automated checks passing.

The default voice/language is American English (`af_heart`, `en-us`). Other languages are not configured by this CLI. Explicit voice/speed overrides change the sound (supported speed range: 0.5–2.0); no setting changes automatically to satisfy a time limit.

Paragraphs are synthesized separately. The tool adds 1.25 seconds after headings and before the next heading, 0.55 seconds after other paragraphs, and 0.20 seconds between chunks of a long paragraph. It never adds an introduction, outro, music, or AI announcement. Text is split near 480 characters and all phoneme batches must fit the model’s 510-character context without dropping content. Punctuation prosody also depends on the model.

SHA-256 hashes and dependency versions are recorded for auditing. Identical settings do not guarantee byte-identical audio on every platform. Pronunciation replacements are case-sensitive, whole-word/phrase, and applied once; advanced phoneme overrides are literal ordered replacements requiring careful listening review.

## Development

```bash
python -m pip install -e '.[dev]'
pytest
```

Core tests do not require downloading a model. A passing test suite does not establish speech quality or replace a real-model listening test. See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution and review guidance.

## License and acknowledgements

The project code is MIT-licensed; see [LICENSE](LICENSE). Kokoro and its dependencies retain their own licenses. In particular, upstream identifies `kokoro-onnx` as MIT and the Kokoro model as Apache 2.0. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for sources and redistribution considerations.
