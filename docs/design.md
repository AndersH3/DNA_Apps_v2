# Design, contracts, and compatibility

## Module boundaries

| Module | Responsibility | Main reusable functions |
| --- | --- | --- |
| `merge.py` | Genotype parsing and coordinate-based merging | `parse`, `resolve_genotype`, `merge_rows`, `header` |
| `merge_ydata.py` | Normalize, classify, and deduplicate marker calls | `process`, `conflicting_markers` |
| `extract.py` | Parse YSEQ rows and extract signed marker names | `parse_yseq_line`, `extract_markers` |
| `dna_io.py` | UTF-8 input and exclusive output creation | `read_lines`, `write_outputs` |

Each executable provides `main(argv=None)` and a standard `__main__` guard.
Importing a module performs no file operations and does not print or exit.
The three installed commands call the same functions as the scripts.

`Row` is an immutable named tuple defined once, rather than a new class for every
line. Genotype merging uses one dictionary keyed by `(chromosome, position)`;
this replaces three parallel arrays whose entries had to be kept synchronized.
Input files are iterated by line, retaining only one genotype record per unique
locus. For N input lines and U unique loci, merge work is O(N + U log U), with
O(U) retained state. Final rows and serialized output also occupy O(U) memory.
Y-marker input is read one file at a time and normalized into a set; it still
requires enough memory for the largest individual file and all unique calls.
Extraction retains the output markers before writing.

## Deal annotations

Contracts follow Deal's [value contracts](https://deal.readthedocs.io/basic/values.html),
[exception contracts](https://deal.readthedocs.io/basic/exceptions.html), and
[side-effect markers](https://deal.readthedocs.io/basic/side-effects.html).

- `parse` and `parse_yseq_line` declare no I/O (`deal.has()`), expected
  `ValueError` failures, and output shape/value guarantees. They also use normal
  validation so bad external data is rejected with contracts disabled.
- `resolve_genotype` has a precondition requiring nonempty call strings, declares
  purity, and connects the result to its inputs with `deal.ensure`. In particular,
  an existing conflict cannot disappear.
- `header` and `conflicting_markers` are pure and have output guarantees.
- `merge_rows`, `process`, and `extract_markers` have postconditions for their
  results. Their `read` marker permits lazy file-backed input iterators. They do
  not claim complete exception lists: an iterator may fail while being consumed.
- `read_lines` declares `read`; `write_outputs` declares `read` and `write`.
  Filesystem exceptions propagate unchanged. No exhaustive `deal.raises` list
  is claimed at this boundary, since OS backends can raise different subclasses.
  Deal 4.24's exception checks match exact exception classes, not all subclasses
  of a listed base class.

Contracts rely on the documented type hints; they are not comprehensive runtime
type checks for arbitrary Python objects. For example, `process` expects an
iterable of strings, and `conflicting_markers` expects the positive and negative
partitions supplied by `process`.

The command-line orchestration intentionally has no purity claim: argument
parsing, streams, clocks, random UUIDs, file access, and process exit are effects.
There are no mutable domain classes needing a `deal.inv` annotation. Immutable
records, explicit validation, and function-level contracts express the relevant
invariants without introducing a class solely to attach a decorator.

Runtime postconditions do additional traversals and, for marker normalization,
sorting. They have a performance cost for large inputs. Input validation and the
actual merge rules remain active even when Deal checking is disabled. See
[Deal runtime configuration](https://deal.readthedocs.io/basic/runtime.html).

## Preserved behavior

- Genotypes merge by coordinates, with literal string equality, `--` for missing,
  and `XX` for irreversible conflict; missing/conflicted output loci are omitted.
- The last rsid observed at a locus wins independently of genotype resolution.
- Chromosome order is 1–22, X, Y, MT, then ascending position within each chromosome.
- `parse` returns an object with `rsid`, `chromosome`, `position`, `genotype`, and
  `comment` attributes. `process` returns `[all, positive, negative]` lists.
- Y-marker whitespace is removed, and unknown/unsigned entries remain in the
  combined output. Contradictory signs are retained, now also reported.
- YSEQ extraction preserves source order and duplicates and uses the allele's
  final sign. It does not filter by chromosome.

## Intentional changes from the legacy scripts

1. Python 3.10+ replaces the obsolete Python 3.7 shebang; Deal is now required.
2. Genotype fields require real separators. Unsupported chromosomes, invalid
   positions, and malformed rows produce useful errors instead of regex failures.
3. Blank lines are accepted, imports are safe, and no-input calls show usage.
4. Output no longer claims that 23andMe generated, quality-reviewed, or aligned
   the data to build 37. These properties were never established by the program.
5. Y-marker invocation works via absolute/relative script paths and installed
   commands. Argument handling no longer scans the script's filename.
6. All Y outputs and counts are globally deduplicated and sorted. Previously the
   combined file was deduplicated while signed files and counts could repeat calls
   appearing in several inputs. `process` no longer prints unsigned entries.
7. YSEQ parsing accepts final lines without a newline and validates malformed
   records instead of silently skipping them. A valid row with an unsigned allele
   is still skipped. Comments and empty rows are explicitly supported.
8. UUID-based defaults replace collision-prone short random numbers. Explicit
   output names are available, all written files are closed reliably, and existing
   destinations are protected. Extraction defaults to the input directory.
9. Comment `Row` fields are empty strings and position zero rather than mixed
   numeric sentinels. Genotype output has exactly four columns without a trailing
   empty tab-separated column. UTF-8 with BOM input is supported.
10. `header(date)` now returns a real header instead of doing nothing. It has no
    clock dependency; only the CLI chooses the current UTC time.

## Output safety limits

Exclusive creation (`open(..., "x")`) prevents overwriting an existing file even
if it appears after preflight. The batch writer records only files it created and
attempts to remove those on ordinary I/O or encoding failure. Missing parent
directories are reported; they are not created implicitly. This is designed for
ordinary local processing, not concurrent untrusted modification of output
directories. It does not guarantee recovery from power loss or abrupt termination.

## Verification strategy

The conflict truth table covers every pair of representative call strings. A
separate set-of-evidence model is the oracle for generated sequences: no evidence,
multiple distinct calls, or an explicit conflict yields no output; exactly one
nonmissing, nonconflicting call survives. Reversal of input must preserve the
selected genotype (but intentionally need not preserve the rsid).

Marker tests check idempotence, order independence, deduplication, and partition
consistency. CLI tests exercise all scripts as subprocesses, including invalid
paths, empty input, output collisions, UTF-8 errors, and optimized Python. Runtime
contract violations are tested directly. Ruff checks style/imports; Deal's linter
checks the annotated source. None of these checks establishes the biological
validity of input data, genome-build compatibility, or a mathematical proof of
all executions.
