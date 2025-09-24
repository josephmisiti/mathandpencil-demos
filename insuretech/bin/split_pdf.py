#!/usr/bin/env python3
"""Extract a range of pages from a PDF into a new PDF file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-s",
        "--start",
        type=int,
        required=True,
        help="First page to include (1-indexed).",
    )
    parser.add_argument(
        "-e",
        "--end",
        type=int,
        required=True,
        help="Last page to include (1-indexed, inclusive).",
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        required=True,
        help="Path to the source PDF file.",
    )
    return parser.parse_args(argv)


def load_pdf_backend():
    """Import a PDF backend, preferring pypdf but falling back to PyPDF2."""

    try:
        from pypdf import PdfReader, PdfWriter  # type: ignore

        return PdfReader, PdfWriter
    except ImportError:
        try:
            from PyPDF2 import PdfReader, PdfWriter  # type: ignore

            return PdfReader, PdfWriter
        except ImportError as exc:  # pragma: no cover - runtime guard
            raise SystemExit(
                "Install 'pypdf' or 'PyPDF2' to use this script."
            ) from exc


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])

    input_path: Path = args.input
    start_page: int = args.start
    end_page: int = args.end

    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 1

    if input_path.suffix.lower() != ".pdf":
        print("Input file must be a PDF", file=sys.stderr)
        return 1

    if start_page < 1 or end_page < 1:
        print("Page numbers must be positive", file=sys.stderr)
        return 1

    if end_page < start_page:
        print("End page cannot be before start page", file=sys.stderr)
        return 1

    PdfReader, PdfWriter = load_pdf_backend()

    reader = PdfReader(str(input_path))
    total_pages = len(reader.pages)

    if start_page > total_pages:
        print(
            f"Start page {start_page} is beyond the end of the document ({total_pages} pages)",
            file=sys.stderr,
        )
        return 1

    if end_page > total_pages:
        print(
            f"End page {end_page} trimmed to {total_pages} (total pages)",
            file=sys.stderr,
        )
        end_page = total_pages

    writer = PdfWriter()

    for page_number in range(start_page - 1, end_page):
        writer.add_page(reader.pages[page_number])

    output_path = input_path.with_name(f"{input_path.stem}_output.pdf")

    with output_path.open("wb") as output_file:
        writer.write(output_file)

    print(f"Wrote {output_path} with pages {start_page}-{end_page}.")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
