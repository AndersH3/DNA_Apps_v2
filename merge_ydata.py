#!/usr/bin/env python3
"""Merge comma-separated Y-marker calls into unique, sorted output files."""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Sequence
from pathlib import Path
from uuid import uuid4

import deal

from dna_io import read_lines, write_outputs


@deal.has("read")
@deal.post(lambda result: len(result) == 3 and all(items == sorted(set(items)) for items in result))
@deal.post(lambda result: result[1] == [item for item in result[0] if item.endswith("+")])
@deal.post(lambda result: result[2] == [item for item in result[0] if item.endswith("-")])
def process(input_data: Iterable[str]) -> list[list[str]]:
    """Return [all, positive, negative] marker lists without printing or mutation.

    Whitespace anywhere in an entry is removed for compatibility with the old
    script. Empty entries are discarded. Unsigned entries are retained in the
    combined list and counted as unclassified in the CLI report. Opposite calls
    (M1+ and M1-) are both retained; this tool does not resolve their conflict.
    """
    # Deduplicate once across all files, so every output and report uses the same
    # definition of a count: unique normalized marker-call strings.
    markers = sorted({normalized for item in input_data if (normalized := "".join(item.split()))})
    return [
        markers,
        [m for m in markers if m.endswith("+")],
        [m for m in markers if m.endswith("-")],
    ]


@deal.pure
@deal.post(lambda result: result == sorted(set(result)))
def conflicting_markers(positive: Sequence[str], negative: Sequence[str]) -> list[str]:
    """List marker names present with both signs, without discarding either call."""
    return sorted({item[:-1] for item in positive} & {item[:-1] for item in negative})


def main(argv: Sequence[str] | None = None) -> int:
    """Write all, positive, negative, and report files under a shared prefix."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path, help="comma-separated marker-call files")
    parser.add_argument(
        "--output-prefix",
        type=Path,
        help="output path prefix (default: unique ID in current directory)",
    )
    args = parser.parse_args(argv)
    prefix = args.output_prefix if args.output_prefix is not None else Path(uuid4().hex)
    try:
        # Read each file as a complete comma-separated list. Newlines are
        # whitespace, not extra delimiters, matching the historical format.
        entries = (
            entry
            for path in args.files
            for entry in "".join(line for _, line in read_lines(path)).split(",")
        )
        all_markers, positive, negative = process(entries)
        conflicts = conflicting_markers(positive, negative)
        report = (
            f"snps: {len(all_markers)}   snps(positive): {len(positive)}   snps(negative): {len(negative)}\n"
            f"unclassified: {len(all_markers) - len(positive) - len(negative)}\n"
            f"conflicting markers: {len(conflicts)}\n"
            f"conflicts: {','.join(conflicts)}\n"
        )
        write_outputs(
            {
                Path(f"{prefix}.out.txt"): ",".join(all_markers),
                Path(f"{prefix}.positive.out.txt"): ",".join(positive),
                Path(f"{prefix}.negative.out.txt"): ",".join(negative),
                Path(f"{prefix}.report.out.txt"): report,
            }
        )
    except (OSError, UnicodeError, ValueError) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")
    print(f"Wrote {prefix}.out.txt and positive, negative, and report files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
