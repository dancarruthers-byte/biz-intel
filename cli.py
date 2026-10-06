"""Command-line usage: python cli.py "Company Name" [--focus "..."] [-o report.md]"""

import argparse
import sys

from biz_intel import ReportError, generate_report, to_markdown


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a business intelligence report for a company.")
    parser.add_argument("company", help="Company name (optionally with ticker or website to disambiguate)")
    parser.add_argument("--focus", help="Optional area to emphasise, e.g. 'AI strategy' or 'EU expansion'")
    parser.add_argument("-o", "--output", help="Write the Markdown report to this file instead of stdout")
    args = parser.parse_args()

    def progress(event: dict) -> None:
        if event["type"] == "status":
            print(f"  … {event['message']}", file=sys.stderr)

    print(f"Researching {args.company}...", file=sys.stderr)
    try:
        report = generate_report(args.company, args.focus, on_event=progress)
    except ReportError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    text = to_markdown(report)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Saved to {args.output}", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
