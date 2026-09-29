"""Detection rules.

Token prefixes come from each vendor's public documentation:
- AWS access key IDs start with AKIA (long-term) or ASIA (temporary):
  https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_identifiers.html
- GitHub tokens start with ghp_, gho_, ghu_, ghs_, ghr_ or github_pat_:
  https://github.blog/engineering/platform-security/behind-githubs-new-authentication-token-formats/
- Slack tokens start with xox followed by a type letter:
  https://api.slack.com/authentication/token-types
- Stripe live secret and restricted keys start with sk_live_ and rk_live_:
  https://docs.stripe.com/keys
- Google API keys start with AIza: https://cloud.google.com/docs/authentication/api-keys
Lengths are kept loose on purpose: a missed secret costs more than a false alarm.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional

from secret_scan.entropy import shannon_entropy

#: Generic assignments must look at least this random (bits per character).
GENERIC_MIN_ENTROPY = 3.5

#: Values that are obviously placeholders, not secrets.
PLACEHOLDER = re.compile(r"\$\{|\{\{|<[^>]*>|example|changeme|placeholder|your[_-]|xxxx", re.IGNORECASE)


@dataclass(frozen=True)
class Rule:
    id: str
    description: str
    pattern: re.Pattern[str]
    #: Optional extra test on the matched secret (group 1 if present, else group 0).
    accept: Optional[Callable[[str], bool]] = None


def _generic_accept(value: str) -> bool:
    # Generated credentials mix letters and digits. Requiring both drops names like
    # "secret_scan.cli:main" (a real false positive from this repo's pyproject.toml).
    has_letter_and_digit = any(c.isalpha() for c in value) and any(c.isdigit() for c in value)
    return has_letter_and_digit and not PLACEHOLDER.search(value) and shannon_entropy(value) >= GENERIC_MIN_ENTROPY


RULES: tuple[Rule, ...] = (
    Rule("aws-access-key-id", "AWS access key ID", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    Rule("github-token", "GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})\b")),
    Rule("anthropic-api-key", "Anthropic API key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    Rule("openai-api-key", "OpenAI API key", re.compile(r"\bsk-(?!ant-)(?:proj-)?[A-Za-z0-9_-]{32,}")),
    Rule("slack-token", "Slack token", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}")),
    Rule("stripe-secret-key", "Stripe live secret key", re.compile(r"\b[rs]k_live_[A-Za-z0-9]{20,}\b")),
    Rule("google-api-key", "Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    Rule("private-key", "Private key block", re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----")),
    Rule(
        "generic-secret",
        "High-entropy value assigned to a key, secret, token or password",
        re.compile(
            r"(?i)\b[\w.-]*(?:api[_-]?key|secret|token|passw(?:or)?d|access[_-]?key)[\w.-]*"
            r"[\"']?\s*[:=]\s*[\"']([^\"'\s]{16,})[\"']"
        ),
        accept=_generic_accept,
    ),
)
