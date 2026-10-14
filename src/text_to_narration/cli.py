"""Command-line interface; heavy inference dependencies load only when needed."""

import argparse
import json
import math
import sys

from .common import NarrationError


def positive_float(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("Must be a finite positive number")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description="Auditable local Kokoro narration")
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare", help="Create transcript and audited source map")
    prep.add_argument("source")
    prep.add_argument("--output", required=True)
    prep.add_argument("--format", choices=["text", "markdown"])
    prep.add_argument("--pronunciations")
    stops = prep.add_mutually_exclusive_group()
    stops.add_argument("--no-stop", action="store_true")
    stops.add_argument(
        "--stop-heading", action="append", help="Replace default stop headings; repeatable"
    )
    download = commands.add_parser(
        "download-models", help="Download and verify official model files"
    )
    download.add_argument("--models", default="models")
    render = commands.add_parser("render", help="Synthesize locally and validate the result")
    render.add_argument("--output", required=True)
    render.add_argument("--models", required=True)
    render.add_argument("--voice", default="af_heart")
    render.add_argument("--speed", type=positive_float, default=0.98)
    render.add_argument("--threads", type=int, default=4)
    render.add_argument("--max-seconds", type=positive_float)
    validate = commands.add_parser("validate", help="Recheck existing source mapping and audio")
    validate.add_argument("--output", required=True)
    validate.add_argument("--max-seconds", type=positive_float)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            from .prepare import DEFAULT_STOPS, prepare

            result = prepare(
                args.source,
                args.output,
                args.format,
                args.pronunciations,
                [] if args.no_stop else args.stop_heading or DEFAULT_STOPS,
            )
            print(
                f"Prepared {len(result['segments'])} segments. Review transcript.txt before render."
            )
        elif args.command == "download-models":
            from .models import download_models

            download_models(args.models)
        else:
            from .audio import render, validate

            result = (
                render(
                    args.output, args.models, args.voice, args.speed, args.threads, args.max_seconds
                )
                if args.command == "render"
                else validate(args.output, args.max_seconds)
            )
            print(json.dumps(result, indent=2))
            return 2 if result["status"] != "passed" else 0
    except (NarrationError, OSError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
