# secret-scan

A zero-dependency secret scanner (Python standard library only) meant to run as a pre-commit and
pre-push hook. It reports the file, line and rule for each possible secret, and never prints the
secret itself.

```sh
python3 -m secret_scan --staged     # what's about to be committed (reads the git index)
python3 -m secret_scan --tracked    # every file git tracks
python3 -m secret_scan src/ config/ # files or directories
```

Run from `packages/secret-scan`, or add it to `PYTHONPATH`. Exit codes: `0` clean, `1` possible secret
found, `2` usage or git error.

**Rules:** vendor token formats (AWS, GitHub, Anthropic, OpenAI, Slack, Stripe, Google), private key
blocks, and a generic rule for high-entropy values assigned to names like `api_key` or `password`.
See `secret_scan/rules.py` for each pattern and its public source.

**Exceptions:** add `secret-scan: allow` in a comment on the line, or list paths in
`.secret-scan-allowlist` at the repo root (`docs/*.md` skips a file; `generic-secret:tests/*` skips one
rule).

**Tests:** `pytest packages/secret-scan` (tested on Python 3.9, 3.10, 3.11 and 3.13).
