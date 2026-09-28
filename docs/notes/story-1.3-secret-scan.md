# Story 1.3: `secret-scan` (Python, zero dependencies)

Notes for explaining this story in a review or interview.

## Why zero dependencies

The scanner runs on every commit and push, on every developer's machine, before code leaves it. Each
dependency is code that also runs there and could itself be compromised or break an install. The
standard library has everything needed: `re`, `math`, `fnmatch`, `subprocess`, `argparse`.

## How detection works

1. **Known formats.** Most vendors now put a fixed prefix on their credentials (`ghp_` for GitHub,
   `AKIA` for AWS key IDs, `sk-ant-` for Anthropic). A prefix plus the right character set is a
   high-confidence match. Sources are linked in `secret_scan/rules.py`.
2. **Entropy for everything else.** Shannon entropy measures how unpredictable the characters are, in
   bits per character. English words score about 3. Random strings score 4 to 5 or more. The generic
   rule only fires when a value is assigned to a name like `api_key`, `token` or `password`, is at least
   16 characters, mixes letters and digits, isn't an obvious placeholder (`${API_KEY}`, `<your-token>`),
   **and** scores at least 3.5.
3. **Never echo the secret.** A finding prints `AKIA... (20 chars)`. Hook output lands in terminals, CI
   logs and screen shares; printing the secret there would leak it a second time.

## The false positive this repo caught

The first run of `test_no_false_positives_on_this_repo` failed on this package's own `pyproject.toml`:
`secret-scan = "secret_scan.cli:main"`. The name contains "secret", and the value is long and varied
enough to pass the entropy threshold. The fix was the letters-and-digits requirement, and the line is
now a regression test. Tuning a scanner is always this trade: every rule you loosen catches more and
annoys more.

## Fake fixtures, assembled at run time

`tests/fakes.py` builds every fake secret by joining pieces (`"AKIA" + "FAKE0000TEST0000"`), and every
value contains `FAKE`. No complete token-shaped string exists anywhere in the repo, so:

- the scanner can scan this repo with no allowlist entries and report nothing, which is the acceptance
  test, and
- GitHub's own secret scanning never mistakes a fixture for a leak.

## `--staged` reads the index

`git show :path` returns the staged version of a file, which is what the commit will contain. The
working tree can differ: stage a secret, then remove it from the file without re-staging, and the
commit would still contain it. `test_staged_scans_the_index_not_the_working_tree` proves this case.

## Numbers

- 32 tests, about 0.15 s on Python 3.9, 3.10, 3.11 and 3.13 (run with `uv run --python <v>`).
- Timed runs of the scanner over this repo, cold and as a hook, are Story 1.5.

## Honest limits

- Regexes miss formats they don't know, and entropy can't tell a random test ID from a real key.
- No git history scan yet. That's part of the pre-public gate (#18).
- Tested with fake fixtures only. No claim is made about catch rates on real-world leaks.
