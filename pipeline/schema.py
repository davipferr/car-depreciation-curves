"""Fail fast, and clearly, when a source changes the shape of its answers.

FIPE's endpoints are undocumented: they back its own consultation page and can
rename a field without notice. Without a check, a rename surfaces as a bare
``KeyError: 'Valor'`` deep inside a loader. ``require_keys`` runs right after
a response is parsed and names the source, the missing fields and the closest
fields that do exist.
"""

from __future__ import annotations

import difflib
from collections.abc import Iterable


class SchemaError(Exception):
    """A raw response no longer has the fields the pipeline expects."""


def require_keys(records: list | dict, expected: Iterable[str], source: str, *, min_rows: int = 1) -> list | dict:
    """Return ``records`` (a JSON object, or a list of them) if every record has every ``expected`` key.

    A list must also have at least ``min_rows`` records.
    """
    expected = list(expected)
    rows = [records] if isinstance(records, dict) else records
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise SchemaError(f"{source}: expected a JSON object or a list of objects, got {type(records).__name__}")
    if len(rows) < min_rows:
        raise SchemaError(f"{source}: expected at least {min_rows} record(s), got {len(rows)}")
    for i, row in enumerate(rows):
        missing = [k for k in expected if k not in row]
        if missing:
            hints = []
            for key in missing:
                close = difflib.get_close_matches(key, list(row), n=1, cutoff=0.6)
                hints.append(f"  - {key!r}" + (f" (did you mean {close[0]!r}?)" if close else ""))
            where = "" if isinstance(records, dict) else f" (record {i})"
            raise SchemaError(
                f"{source}{where}: {len(missing)} expected field(s) missing — the API format probably changed.\n"
                + "\n".join(hints)
                + f"\nFields found: {', '.join(map(repr, row))}"
            )
    return records
