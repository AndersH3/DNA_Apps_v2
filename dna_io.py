# AI disclosure: substantially generated or refactored with OpenAI Codex, 2026-10-13.
# See the repository-root AI_DISCLOSURE.md for provenance, scope, and review limits.
"""Shared UTF-8 input and non-overwriting output for the command-line tools."""

from collections.abc import Iterator, Mapping
from pathlib import Path

import deal


@deal.has("read")
def read_lines(path: Path) -> Iterator[tuple[int, str]]:
    """Yield one-based line numbers; accept a UTF-8 BOM and universal newlines.

    OS/encoding errors propagate unchanged. No exhaustive raises contract is
    claimed: filesystem backends can raise many distinct exception subclasses.
    """
    with path.open(encoding="utf-8-sig") as stream:
        yield from enumerate(stream, start=1)


@deal.has("read", "write")
def write_outputs(outputs: Mapping[Path, str]) -> None:
    """Create new UTF-8 files, refusing to overwrite any existing destination.

    Preflight avoids ordinary partial batches. Exclusive creation also protects
    against another process creating a destination between the check and open.
    On failure, remove only files this call created. This is best-effort cleanup,
    not a crash-safe transaction across several files.
    """
    for path in outputs:
        if path.exists():
            raise FileExistsError(f"output already exists: {path}")
    created: list[Path] = []
    try:
        for path, content in outputs.items():
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                created.append(path)
                stream.write(content)
    except (OSError, UnicodeError):
        for path in created:
            try:
                path.unlink()
            except OSError:
                # Preserve the original write error; a cleanup failure must not
                # conceal the reason the batch failed.
                pass
        raise
