#!/usr/bin/env python3
"""Extract signed marker calls from seven-column, tab-separated YSEQ records."""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Sequence
from pathlib import Path
from uuid import uuid4

import deal

from dna_io import read_lines, write_outputs

HEADER = ("sampleid", "ordered", "marker+", "chr", "start", "end", "allele")


@deal.has()
@deal.raises(ValueError)
@deal.post(
    lambda result: result is None or (len(result) > 1 and result[-1] in "+-" and "," not in result)
)
def parse_yseq_line(line: str) -> str | None:
    """Return a signed marker or None for headers, comments, blanks, and no-calls.

    Data rows require seven tab-separated, nonempty fields, a numeric sample
    identifier, and nonnegative ordered coordinates. The last character of the
    allele field supplies the sign; the marker field supplies the name. Rows
    whose allele has no final sign represent unclassified/no-call observations
    and are skipped. Malformed structure raises ValueError instead of silently
    losing records. A final newline is optional.
    """
    text = line.strip()
    if not text or text.startswith("#"):
        return None
    fields = [field.strip() for field in line.rstrip("\r\n").split("\t")]
    if tuple(field.lower() for field in fields) == HEADER:
        return None
    if len(fields) != 7 or not all(fields):
        raise ValueError("expected seven nonempty tab-separated YSEQ fields")
    sample, _ordered, marker, _chromosome, start, end, allele = fields
    if not all(value.isascii() and value.isdecimal() for value in (sample, start, end)):
        raise ValueError("sample ID, start, and end must be nonnegative integers")
    if int(start) > int(end):
        raise ValueError("start coordinate must not exceed end coordinate")
    if any(char.isspace() for char in marker) or "," in marker:
        raise ValueError("marker must not contain whitespace or commas")
    if allele[-1] not in "+-":
        return None
    return marker + allele[-1]


@deal.has("read")
@deal.post(lambda result: all(len(marker) > 1 and marker[-1] in "+-" for marker in result))
def extract_markers(lines: Iterable[str]) -> list[str]:
    """Extract in source order, preserving duplicates and attaching line numbers."""
    markers: list[str] = []
    for number, line in enumerate(lines, start=1):
        try:
            marker = parse_yseq_line(line)
        except ValueError as error:
            raise ValueError(f"line {number}: {error}") from error
        if marker is not None:
            markers.append(marker)
    return markers


def main(argv: Sequence[str] | None = None) -> int:
    """Extract one input file to an explicit or uniquely named sibling file."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="YSEQ tab-separated input")
    parser.add_argument(
        "-o", "--output", type=Path, help="new output file (default: unique sibling of input)"
    )
    args = parser.parse_args(argv)
    try:
        output = (
            args.output
            if args.output is not None
            else args.file.with_name(f"{uuid4().hex}-{args.file.name}")
        )
        # Add the directory to the output path, not to the generated filename.
        # This works with absolute input paths and names containing spaces.
        markers = extract_markers(line for _, line in read_lines(args.file))
        write_outputs({output: ",".join(markers)})
    except (OSError, UnicodeError, ValueError) as error:
        parser.exit(1, f"{parser.prog}: {args.file}: {error}\n")
    print(f"Wrote {len(markers)} marker calls to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
