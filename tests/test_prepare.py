import json

import pytest

from text_to_narration.audio import check_source, chunks, plan
from text_to_narration.cli import main
from text_to_narration.common import NarrationError
from text_to_narration.prepare import extract, prepare, substitute


def test_markdown_order_and_stop():
    text = "# Title\n\nA **bold** [label](https://example.com).\nwrapped line.\n\n## Part\n\n- One\n- Two\n\n## Further Reading\n\nExclude me\n\n## References\nOther"
    records, coverage = extract(text)
    assert [r["text"] for r in records] == [
        "Title",
        "A bold label. wrapped line.",
        "Part",
        "One",
        "Two",
    ]
    assert coverage[-1]["status"] == "excluded_after_stop"


def test_reference_first():
    records, _ = extract("Start\n\n## REFERENCES\n\nNo\n\n## Further Reading\nNo")
    assert len(records) == 1


def test_no_stop():
    records, _ = extract("# Title\n\n## References\n\nYes", stop_headings=[])
    assert len(records) == 3


def test_text_paragraphs():
    records, _ = extract("One line\nand another.\n\nNext.\n\nReferences\n\nNo.", "text")
    assert [r["text"] for r in records] == ["One line and another.", "Next."]


@pytest.mark.parametrize(
    "source",
    [
        "```python\nx=1\n```",
        "Hello `x`.",
        "![alt](x.png)",
        "<div>Hi</div>",
        "A | B\n--|--\n1|2",
        "$x^2$",
        "[ref]: https://example.com\n\nHi",
        "    code",
    ],
)
def test_unsupported_is_never_silently_dropped(source):
    with pytest.raises(NarrationError):
        extract(source)


def test_setext_headings_and_blockquote():
    records, _ = extract("Title\n=====\n\n> A quote\n> continued.\n\nReferences\n----------\nNo")
    assert [r["text"] for r in records] == ["Title", "A quote continued."]


def test_replacements_are_single_pass():
    assert substitute("AI and AIR", {"AI": "A I", "A": "letter"}) == "A I and AIR"


def test_prepare_and_tamper(tmp_path):
    source = tmp_path / "article.md"
    source.write_text("# Hello\n\nWorld.", encoding="utf-8")
    out = tmp_path / "out"
    prepare(source, out)
    assert len(check_source(out)["segments"]) == 2
    with pytest.raises(NarrationError):
        prepare(source, out)
    (out / "transcript.txt").write_text("Bad", encoding="utf-8")
    with pytest.raises(NarrationError):
        check_source(out)


def test_manifest_tamper(tmp_path):
    source = tmp_path / "a.txt"
    source.write_text("Hello world.", encoding="utf-8")
    out = tmp_path / "out"
    prepare(source, out)
    path = out / "narration-manifest.json"
    manifest = json.loads(path.read_text())
    manifest["segments"][0]["text"] = "Changed"
    path.write_text(json.dumps(manifest))
    with pytest.raises(NarrationError):
        check_source(out)


def test_long_chunking_no_loss():
    text = " ".join(["word"] * 2000)
    result = chunks(text)
    assert " ".join(result) == text
    assert max(map(len, result)) <= 480
    assert chunks("x" * 600) == ["x" * 600]  # actual phoneme limit checked at inference


def test_pauses():
    manifest = {
        "segments": [
            {"text": "Title", "kind": "title"},
            {"text": "Text", "kind": "paragraph"},
            {"text": "Heading", "kind": "heading"},
            {"text": "End", "kind": "paragraph"},
        ]
    }
    assert [x["pause_after_samples"] / 24000 for x in plan(manifest)] == [1.25, 1.25, 1.25, 0.55]


def test_cli_validation():
    with pytest.raises(SystemExit):
        main(["render", "--output", "x", "--models", "m", "--speed", "nan"])
    with pytest.raises(SystemExit):
        main(["render", "--output", "x", "--models", "m", "--max-seconds", "-1"])


@pytest.mark.parametrize("separator", ["\r\n", "\r", "\u2028", "\u2029", "\n"])
def test_line_separator_normalization(separator):
    records, _ = extract(separator.join(["First.", "", "Second."]), "text")
    assert [r["text"] for r in records] == ["First.", "Second."]


def test_spaced_thematic_break():
    records, _ = extract("First.\n\n- - -\n\nSecond.")
    assert [r["text"] for r in records] == ["First.", "Second."]


def test_trailing_blank_lines_are_audited():
    _, coverage = extract("A\n\n", "text")
    assert len(coverage) == 2
    assert coverage[-1]["status"] == "blank"
