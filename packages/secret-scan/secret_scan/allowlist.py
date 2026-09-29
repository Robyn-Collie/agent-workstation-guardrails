"""The allowlist: known-safe files or rule/file pairs, one per line.

    # comment
    docs/examples/*.md              skip every rule in matching files
    generic-secret:tests/*.py       skip one rule in matching files

Patterns use fnmatch against the repo-relative path with forward slashes, so `*`
also matches across directories. A line of code can also opt out with an inline
`secret-scan: allow` comment, which keeps the exception next to the code it excuses.
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Optional

INLINE_PRAGMA = "secret-scan: allow"
DEFAULT_FILE = ".secret-scan-allowlist"


@dataclass(frozen=True)
class Entry:
    pattern: str
    rule_id: Optional[str] = None


class Allowlist:
    def __init__(self, entries: list[Entry]) -> None:
        self.entries = entries

    @classmethod
    def parse(cls, text: str) -> "Allowlist":
        entries = []
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            rule_id, sep, pattern = line.partition(":")
            entries.append(Entry(pattern, rule_id) if sep else Entry(line))
        return cls(entries)

    @classmethod
    def load(cls, path: Path) -> "Allowlist":
        return cls.parse(path.read_text(encoding="utf-8")) if path.is_file() else cls([])

    def skips_file(self, path: str) -> bool:
        return any(e.rule_id is None and fnmatchcase(path, e.pattern) for e in self.entries)

    def allows(self, rule_id: str, path: str) -> bool:
        return any(e.rule_id in (None, rule_id) and fnmatchcase(path, e.pattern) for e in self.entries)
