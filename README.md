# DNA_Apps_v2

Three small Python command-line tools for combining genotype files and extracting
or merging signed Y-marker calls. All processing is local; the tools do not send
input data to a service.

- **`merge.py`** merges four-column genotype records by chromosome and position.
- **`merge_ydata.py`** combines comma-separated marker calls such as `M1+,M2-`.
- **`extract.py`** converts seven-column YSEQ records into that marker-call format.

The code includes type hints, detailed docstrings and algorithm comments, and
[Deal](https://deal.readthedocs.io/) contracts. See
[design and contracts](docs/design.md) for function boundaries, assumptions,
compatibility changes, and verification limits.

## AI disclosure

**This version contains substantial AI-generated and AI-refactored code, tests,
comments, documentation, and configuration produced with OpenAI Codex on
13 October 2026.** The AI contribution went beyond proofreading or completion
suggestions: Codex implemented the refactoring, selected implementation details,
wrote the tests and Deal contracts, ran checks, and committed and pushed the
changes at the repository owner's request.

The tests were also AI-authored. Passing them does not constitute independent
human review, formal verification, or biological validation. No independent
human code audit is documented for this refactoring.

See the **[full AI disclosure](AI_DISCLOSURE.md)** for the exact contribution
scope, development process, data used, verification evidence, limitations, and
human/AI responsibilities. The programs themselves do not call an AI service.

## Install

Python **3.10 or newer** is required. From the repository directory:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
```

The runtime dependency is `deal>=4.24,<5`. The historical Python 3.7 invocation
is no longer supported. You can run the scripts directly from this directory,
or use the installed `dna-merge`, `dna-merge-ydata`, and `dna-extract` commands.
Each command supports `--help`.

## Merge genotype files

```sh
python merge.py "input one.txt" input-two.txt --output merged.txt
# Equivalent after installation:
dna-merge "input one.txt" input-two.txt --output merged.txt
```

Use a separate argument for each filename, not a comma-separated filename list.
The optional `--output`/`-o` path must not already exist. Without it, the result is
written to standard output:

```sh
python merge.py first.txt second.txt > merged.txt
```

Shell redirection can overwrite an existing file before Python starts. Prefer
`--output` when you want the tool's overwrite protection.

Inputs have exactly four whitespace-separated fields:

```text
# rsid chromosome position genotype
rs1 1 100 AA
rs2 2 200 --
rs3 X 300 AG
```

Blank lines, `#` comments, and an unprefixed `RSID CHROMOSOME POSITION RESULT`
(or `GENOTYPE`) header are accepted. Chromosomes are exactly `1`–`22`, `X`, `Y`,
and `MT`; positions must be positive integers. Other chromosome aliases, CSV,
VCF, and raw vendor-specific layouts must be converted before use. Genotypes
are compared as literal strings; no alphabet, ploidy, or biological validity
is inferred from the string.

The merge rules preserve the original algorithm:

| Existing call | Incoming call | Combined call |
| --- | --- | --- |
| `--` (missing) | any call | incoming call |
| any call | `--` | existing call |
| same nonmissing strings | same string | that string |
| different nonmissing strings | different string | `XX` (conflict) |
| `XX` | any call | `XX` |

Conflicting and missing loci are omitted from output. A later call cannot revive
a conflict. The **last input identifier** wins at each coordinate, even when its
call is missing. `AG` and `GA` are different strings under this policy.

Output is tab-separated and sorted by chromosome (`1`–`22`, `X`, `Y`, `MT`) and
then numeric position. The header identifies DNA_Apps_v2 and a UTC generation
time. It does not claim that a vendor produced or validated the merged data.

**Inputs must already use the same genome assembly and strand orientation.**
This tool does not check or convert either, reconcile variant representations,
or validate call accuracy. Combining mismatched inputs can therefore produce
misleading matches or conflicts. Outputs are data-processing results, not
clinical interpretations.

## Merge Y-marker calls

```sh
python merge_ydata.py first.txt second.txt extra.txt --output-prefix combined
```

Input is a comma-separated marker-call list, for example:

```text
M1+,M2-,M3+
```

This is the historical FTDNA-style **marker-call list**, not an arbitrary raw
FTDNA download. Whitespace inside each comma-delimited entry is removed. A
newline alone is not a separator: `M1+` and `M2-` on separate lines still need a
comma between them. Empty entries are ignored. Entries without a trailing sign
are retained as unclassified; marker names themselves are not validated against
a reference database.

The command creates four files:

| File | Contents |
| --- | --- |
| `combined.out.txt` | All unique calls, sorted |
| `combined.positive.out.txt` | Unique calls ending in `+`, sorted |
| `combined.negative.out.txt` | Unique calls ending in `-`, sorted |
| `combined.report.out.txt` | Unique-call counts, unclassified count, conflicting marker names |

Both `M1+` and `M1-` are retained if present, and `M1` is reported as conflicting.
The report counts **call strings**, so those two entries count as two calls and
one conflicting marker. No sign takes precedence. Adding the same input twice
does not change the lists or counts.

If `--output-prefix` is omitted, a UUID prefix is generated in the current
directory. Supply a prefix for predictable filenames. Parent directories must
already exist. Existing output files are never overwritten.

## Extract YSEQ calls

```sh
python extract.py "directory/input.txt" --output y-calls.txt
```

Input uses seven **tab-separated** fields:

```text
SampleID Ordered Marker+ Chr Start End Allele
123      date    M1      Y   100   100 A+
124      date    M2      Y   200   200 G-
```

The example above is spaced for readability; actual separators must be tabs.
Sample ID, start, and end must be nonnegative integers, and start must not exceed
end. Each field must be nonempty. Marker names cannot contain commas or
whitespace. The tool copies the marker name and the final `+` or `-` from the
allele column; it does not filter records by chromosome. The ordered/date and
chromosome fields are otherwise treated as opaque values.

Headers, blank lines, and `#` comments are ignored. Structurally valid rows whose
allele does not end in a sign are skipped as no-call/unclassified observations.
Malformed rows fail with a line number. Source order and duplicates are
preserved; run `merge_ydata.py` afterward to deduplicate if desired. A missing
final newline, Windows line endings, and a UTF-8 BOM are supported.

Without `--output`, extraction creates a uniquely named sibling of the input,
such as `UUID-input.txt`. Explicit output paths must not already exist.

## Errors and empty input

- Command-line usage errors exit with status **2**.
- File, decoding, or data-validation errors exit with status **1** and a message
  on standard error. Expected input errors do not produce Python tracebacks.
- Success exits with status **0**.
- Files use UTF-8; an input BOM is accepted.
- Empty genotype input produces a header only; empty extraction produces an
  empty file; empty Y-marker input produces three empty lists and a zero report.
- All input is processed before output creation. Multi-file Y outputs are
  preflighted and newly created files are cleaned up on write failure where
  possible. This is not a crash-safe, atomic transaction across all four files.

## Development and verification

```sh
python -m pip install -e '.[dev]'
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m deal lint merge.py merge_ydata.py extract.py dna_io.py
```

Tests use synthetic records only. They cover the conflict truth table,
Hypothesis-generated merge properties, parsing, malformed input, file errors,
output protection, clean imports, and command-line execution. The [GitHub Actions template](docs/python-checks.yml) runs the same checks on
Python 3.10 and 3.14. To enable it, copy it to `.github/workflows/tests.yml`
using a GitHub connection permitted to create workflow files. The template in
`docs/` does not run automatically.

Deal contracts supplement normal input validation. Python optimization (`-O`)
can disable contract checks; explicit input validation remains active. Passing
these tests and the Deal linter is **not formal verification** or confirmation
of biological correctness. The build does not run a theorem prover.
