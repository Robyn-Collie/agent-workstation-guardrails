"""Scan text for secrets and report where they are, without echoing them."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from secret_scan.allowlist import INLINE_PRAGMA, Allowlist
from secret_scan.rules import RULES, Rule

#: Files larger than this are skipped; secrets live in source and config, not in blobs.
MAX_BYTES = 1_000_000


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule_id: str
    redacted: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.rule_id}: {self.redacted}"


def redact(secret: str) -> str:
    """Show just enough to find it: the first 4 characters and the length."""
    return f"{secret[:4]}... ({len(secret)} chars)"


def scan_text(
    path: str,
    text: str,
    allowlist: Optional[Allowlist] = None,
    rules: Iterable[Rule] = RULES,
) -> list[Finding]:
    allowlist = allowlist or Allowlist([])
    if allowlist.skips_file(path):
        return []
    active = [r for r in rules if not allowlist.allows(r.id, path)]
    findings = []
    for number, line in enumerate(text.splitlines(), start=1):
        if INLINE_PRAGMA in line:
            continue
        for rule in active:
            for match in rule.pattern.finditer(line):
                secret = match.group(1) if rule.pattern.groups else match.group(0)
                if rule.accept is None or rule.accept(secret):
                    findings.append(Finding(path, number, rule.id, redact(secret)))
    return findings


def decode(data: bytes) -> Optional[str]:
    """Text content, or None for binary or oversized files."""
    if len(data) > MAX_BYTES or b"\0" in data[:8192]:
        return None
    return data.decode("utf-8", errors="replace")
