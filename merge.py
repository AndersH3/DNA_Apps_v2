#!/usr/bin/env python3
# AI disclosure: substantially generated or refactored with OpenAI Codex, 2026-10-13.
# See the repository-root AI_DISCLOSURE.md for provenance, scope, and review limits.
"""Merge whitespace-delimited genotype files by chromosome and position.

The computational helpers are independent of the CLI and safe to import. Inputs
must already use the same genome assembly and strand orientation: this program
combines calls, but does not perform coordinate conversion or strand alignment.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

import deal

from dna_io import read_lines, write_outputs

# This ordering is biological/display ordering, not lexicographic ordering (in
# which chromosome 10 would precede chromosome 2). Keep MT after the sex chromosomes.
CHROMOSOMES = tuple(map(str, range(1, 23))) + ("X", "Y", "MT")
CHROMOSOME_ORDER = {name: index for index, name in enumerate(CHROMOSOMES)}
MISSING = "--"
CONFLICT = "XX"


class Row(NamedTuple):
    """One parsed call; comment rows use empty fields and position zero.

    ``comment`` preserves the original parser's public interface. Data rows have
    a supported chromosome, a positive position, and a nonempty genotype.
    """

    rsid: str
    chromosome: str
    position: int
    genotype: str
    comment: bool = False


@deal.has()
@deal.raises(ValueError)
@deal.post(
    lambda result: (
        result.comment
        or (
            result.chromosome in CHROMOSOMES
            and result.position > 0
            and bool(result.rsid)
            and bool(result.genotype)
        )
    )
)
def parse(row: str) -> Row:
    """Parse four whitespace-separated fields or recognize a comment/header.

    Blank lines and lines beginning with ``#`` are ignored. A header may use
    RESULT or GENOTYPE as its last column. Invalid data raises ValueError even
    when Deal checking is disabled; contracts supplement ordinary validation.
    """
    text = row.strip()
    fields = text.split()
    if (
        not text
        or text.startswith("#")
        or (
            len(fields) == 4
            and [field.lower() for field in fields[:3]] == ["rsid", "chromosome", "position"]
            and fields[3].lower() in {"result", "genotype"}
        )
    ):
        return Row("", "", 0, "", True)
    # Requiring actual field boundaries fixes the old greedy regex, which could
    # divide a single token into several purported columns.
    if len(fields) != 4:
        raise ValueError("expected four fields: rsid chromosome position genotype")
    rsid, chromosome, position_text, genotype = fields
    if chromosome not in CHROMOSOME_ORDER:
        raise ValueError(f"unsupported chromosome {chromosome!r}; expected 1–22, X, Y, or MT")
    try:
        position = int(position_text)
    except ValueError as error:
        raise ValueError(f"invalid position {position_text!r}") from error
    if position <= 0:
        raise ValueError("position must be a positive integer")
    return Row(rsid, chromosome, position, genotype)


@deal.pre(lambda current, incoming: bool(current) and bool(incoming))
@deal.pure
@deal.ensure(lambda current, incoming, result: result in {current, incoming, CONFLICT})
@deal.ensure(lambda current, incoming, result: current != CONFLICT or result == CONFLICT)
def resolve_genotype(current: str, incoming: str) -> str:
    """Combine two calls using the legacy conservative conflict policy.

    A missing call contributes no evidence. Two distinct nonmissing strings
    create an irreversible conflict. Comparison is literal: AG and GA conflict;
    no biological equivalence or strand orientation is inferred here.
    """
    if current == MISSING:
        return incoming
    if incoming == MISSING or incoming == current:
        return current
    return CONFLICT


@deal.has("read")
@deal.post(
    lambda result: all(
        not row.comment and row.genotype not in {MISSING, CONFLICT} for row in result
    )
)
def merge_rows(rows: Iterable[Row]) -> list[Row]:
    """Return sorted, callable loci, retaining the last identifier at each locus.

    Only one record per coordinate is retained, so memory grows with unique
    loci rather than input lines. Conflicted loci remain in the working table
    until the end: deleting them early would let later calls revive them.
    """
    loci: dict[tuple[str, int], Row] = {}
    for row in rows:
        if row.comment:
            continue
        if (
            row.chromosome not in CHROMOSOME_ORDER
            or row.position <= 0
            or not row.rsid
            or not row.genotype
        ):
            raise ValueError("invalid data Row")
        key = (row.chromosome, row.position)
        previous = loci.get(key)
        genotype = (
            row.genotype if previous is None else resolve_genotype(previous.genotype, row.genotype)
        )
        # The last rsid wins, matching the original tool even if it accompanies
        # a missing call. Genotype selection is a separate operation.
        loci[key] = row._replace(genotype=genotype)
    ordered = sorted(loci, key=lambda key: (CHROMOSOME_ORDER[key[0]], key[1]))
    return [loci[key] for key in ordered if loci[key].genotype not in {MISSING, CONFLICT}]


@deal.pure
@deal.post(lambda result: result.startswith("#") and result.endswith("\n"))
def header(date: str) -> str:
    """Build an honest provenance header without asserting an unverified build."""
    # Prefix every line so even a multiline supplied date cannot create a data row.
    safe_date = " ".join(date.splitlines())
    return (
        f"# Merged by DNA_Apps_v2 at: {safe_date}\n"
        "# Inputs must share a genome assembly and strand orientation.\n"
        "# Assembly, strand orientation, and call accuracy have not been verified.\n"
        "# Conflicting (XX) and missing (--) calls are omitted.\n"
        "# rsid\tchromosome\tposition\tgenotype\n"
    )


def read_rows(paths: Sequence[Path]) -> Iterable[Row]:
    """Stream parsed input, adding the filename and line to validation errors."""
    for path in paths:
        for number, line in read_lines(path):
            try:
                yield parse(line)
            except ValueError as error:
                raise ValueError(f"{path}:{number}: {error}") from error


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI; filenames are separate arguments, including paths with spaces."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path, help="four-column genotype files")
    parser.add_argument("-o", "--output", type=Path, help="new output file (default: stdout)")
    args = parser.parse_args(argv)
    try:
        rows = merge_rows(read_rows(args.files))
        output = header(datetime.now(timezone.utc).isoformat())
        output += "".join(f"{r.rsid}\t{r.chromosome}\t{r.position}\t{r.genotype}\n" for r in rows)
        # Finish parsing before emitting output, so invalid input never produces
        # a deceptively valid partial result. Shell redirection itself can still
        # truncate an existing file; --output uses exclusive creation instead.
        if args.output is None:
            print(output, end="")
        else:
            write_outputs({args.output: output})
    except (OSError, UnicodeError, ValueError) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
