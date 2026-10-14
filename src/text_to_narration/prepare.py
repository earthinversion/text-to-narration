"""Conservative Markdown extraction with an audit record for every source line."""

import re
from pathlib import Path

from markdown_it import MarkdownIt

from .common import read_json, require, sha256, write_json

DEFAULT_STOPS = ("further reading", "references")


def load_pronunciations(path=None):
    config = read_json(path) if path else {}
    require(isinstance(config, dict), "Pronunciations must be a JSON object")
    require(set(config) <= {"replacements", "phoneme_overrides"}, "Unknown pronunciation option")
    for name in ("replacements", "phoneme_overrides"):
        value = config.setdefault(name, {})
        require(isinstance(value, dict), f"{name} must be an object")
        require(
            all(
                isinstance(k, str) and k and isinstance(v, str) and v.strip()
                for k, v in value.items()
            ),
            f"{name} needs nonempty string pairs",
        )
    return config


def substitute(text, replacements):
    # One pass: replacement output is never accidentally replaced again.
    if not replacements:
        return text
    pattern = (
        r"(?<!\w)(?:"
        + "|".join(re.escape(k) for k in sorted(replacements, key=len, reverse=True))
        + r")(?!\w)"
    )
    return re.sub(pattern, lambda m: replacements[m.group()], text)


def inline_text(token):
    pieces = []
    for child in token.children or []:
        require(
            child.type not in {"image", "code_inline", "html_inline"},
            f"Unsupported {child.type}: write an explicit spoken version first",
        )
        if child.type == "text":
            pieces.append(child.content)
        elif child.type in {"softbreak", "hardbreak"}:
            pieces.append(" ")
        elif child.type not in {
            "link_open",
            "link_close",
            "em_open",
            "em_close",
            "strong_open",
            "strong_close",
            "s_open",
            "s_close",
        }:
            require(False, f"Unsupported inline construct: {child.type}")
    text = "".join(pieces)
    require(
        not re.search(r"\$|\\[a-zA-Z]+\{|https?://|\|", text),
        "Raw URL, math, or table notation needs an explicit spoken version",
    )
    return " ".join(text.split())


def extract(source, fmt="markdown", stop_headings=DEFAULT_STOPS):
    lines = source.splitlines()
    source = "\n".join(lines)
    stops = {s.strip().casefold() for s in stop_headings}
    records = []
    stop_line = len(lines)
    if fmt == "text":
        # Plain text has no implied headings; only standalone stop-label paragraphs match.
        for match in re.finditer(r"\S[^\n]*(?:\n(?!\s*\n)[^\n]+)*", source):
            text = " ".join(match.group().split())
            start = source[: match.start()].count("\n")
            end = start + match.group().count("\n") + 1
            if text.casefold() in stops:
                stop_line = start
                break
            records.append(
                {"kind": "paragraph", "text": text, "source_lines": list(range(start + 1, end + 1))}
            )
    else:
        tokens = MarkdownIt("commonmark").parse(source)
        for i, token in enumerate(tokens):
            if token.type == "heading_open":
                label = inline_text(tokens[i + 1])
                if label.casefold().rstrip(".:") in stops:
                    stop_line = token.map[0]
                    break
            require(
                token.type not in {"fence", "code_block", "html_block"},
                f"Unsupported {token.type} near line {(token.map or [0])[0] + 1}; prepare spoken prose",
            )
            if token.type == "inline":
                text = inline_text(token)
                require(bool(text), "Empty spoken block: review the source")
                previous = tokens[i - 1]
                kind = "heading" if previous.type == "heading_open" else "paragraph"
                if kind == "heading" and previous.tag == "h1" and not records:
                    kind = "title"
                records.append(
                    {
                        "kind": kind,
                        "text": text,
                        "source_lines": list(range(token.map[0] + 1, token.map[1] + 1)),
                    }
                )
    require(bool(records), "No narratable content before the stop heading")
    used = {line for r in records for line in r["source_lines"]}
    coverage = []
    for i, line in enumerate(lines, 1):
        status = (
            "excluded_after_stop"
            if i > stop_line
            else "spoken"
            if i in used
            else "blank"
            if not line.strip()
            else "markup"
        )
        if status == "markup":
            require(
                bool(re.fullmatch(r"\s*(?:(?:[ \t]*[-*_]){3,}|=+|-+)\s*", line)),
                f"Unmapped source content at line {i}; prepare explicit spoken prose",
            )
        coverage.append({"line": i, "status": status, "source": line})
    return records, coverage


def prepare(source, output, fmt=None, pronunciations=None, stop_headings=DEFAULT_STOPS):
    source, output = Path(source), Path(output)
    require(source.is_file(), f"Input file not found: {source}")
    require(
        not output.exists() or not any(output.iterdir()),
        "Output directory is not empty; choose a new directory to preserve prior work",
    )
    data = source.read_bytes()
    text = data.decode("utf-8-sig")
    fmt = fmt or ("markdown" if source.suffix.lower() in {".md", ".markdown"} else "text")
    config = load_pronunciations(pronunciations)
    segments, coverage = extract(text, fmt, stop_headings)
    for i, segment in enumerate(segments):
        segment.update(id=i, original_text=segment["text"])
        segment["text"] = substitute(segment["text"], config["replacements"])
    output.mkdir(parents=True, exist_ok=True)
    (output / "source.txt").write_bytes(data)
    transcript = "\n\n".join(s["text"] for s in segments) + "\n"
    (output / "transcript.txt").write_text(transcript, encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "status": "prepared",
        "source_filename": source.name,
        "source_sha256": sha256(source),
        "source_snapshot": "source.txt",
        "format": fmt,
        "stop_headings": list(stop_headings),
        "segments": segments,
        "pronunciations": config,
        "transcript_sha256": sha256(output / "transcript.txt"),
    }
    write_json(output / "narration-manifest.json", manifest)
    write_json(output / "source-coverage.json", coverage)
    return manifest
