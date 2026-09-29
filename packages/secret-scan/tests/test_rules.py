import pytest
from fakes import FAKE_SECRETS, RANDOMISH

from secret_scan.entropy import shannon_entropy
from secret_scan.rules import GENERIC_MIN_ENTROPY, RULES
from secret_scan.scanner import scan_text


def test_every_rule_has_a_fixture():
    assert {rule.id for rule in RULES} == set(FAKE_SECRETS)


@pytest.mark.parametrize("rule_id", sorted(FAKE_SECRETS))
def test_each_fixture_is_caught_by_its_own_rule(rule_id):
    findings = scan_text("app/config.py", f"value = {FAKE_SECRETS[rule_id]}\n")
    assert [f.rule_id for f in findings] == [rule_id]


def test_anthropic_key_is_not_also_reported_as_openai():
    findings = scan_text("x", FAKE_SECRETS["anthropic-api-key"])
    assert [f.rule_id for f in findings] == ["anthropic-api-key"]


@pytest.mark.parametrize(
    "line",
    [
        'password = "correcthorsebattery"',  # words: low entropy
        'api_key = "${API_KEY}"',  # environment placeholder
        'token: "<your-token-here>"',  # documentation placeholder
        'secret = "short"',  # too short to matter
        "api_key = os.environ['API_KEY']",  # read at run time, the right pattern
        "AKIA is the prefix for AWS access key IDs",  # prefix alone
        'secret-scan = "secret_scan.cli:main"',  # pyproject entry point: no digits
    ],
)
def test_ordinary_code_is_not_flagged(line):
    assert scan_text("app.py", line) == []


def test_entropy_separates_words_from_random_strings():
    assert shannon_entropy("correcthorsebattery") < GENERIC_MIN_ENTROPY
    assert shannon_entropy(RANDOMISH) > GENERIC_MIN_ENTROPY
    assert shannon_entropy("") == 0.0
    assert shannon_entropy("aaaa") == 0.0
