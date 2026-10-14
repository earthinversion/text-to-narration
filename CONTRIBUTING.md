# Contributing

Small fixes, clear examples, and tests are welcome.

## Set up

Use Python 3.12 and a virtual environment. From the repository directory:

```bash
python -m pip install -e '.[dev]'
pytest
```

Install `.[tts]`, FFmpeg, and the model files only if you need to test rendering. See the README for the full local narration workflow.

## Before opening a pull request

1. Describe the problem and include a small, non-sensitive example.
2. Add or update tests for the changed behavior.
3. Run the test suite and the README preparation example in a fresh output directory.
4. Update command examples and documentation if an option or output changes.
5. State which checks you ran. Distinguish mocked tests from real-model rendering and human listening.

Preserve the source snapshot, explicit exclusions, pronunciation trace, and source-line audit. Do not silently drop unsupported Markdown or shorten a narration to meet a time limit. New syntax should have an explicit spoken rendering and coverage tests.

Avoid overwriting an existing run. Add regression tests for malformed input, missing dependencies, changed output records, and partial failures when applicable.

## Audio changes

For changes to synthesis, chunking, pauses, or encoding, render a short generic article using real model files. Listen to the beginning, segment transitions, technical words, and the ending. Record the model, voice, speed, platform, and any known limitations in your pull request. Do not claim that automated structural or audio checks establish semantic correctness.

## Keep contributions public-safe

Do not commit model weights, generated audio, private articles, credentials, local paths containing personal information, or logs containing source text you cannot share. Use short original examples. Do not add copied third-party code without preserving its license and required notices.

By submitting a contribution, you agree that your original contribution may be distributed under this project's MIT license. Third-party components retain their own terms.
