"""Obviously fake secrets, assembled at run time.

Each value is split so no complete token-shaped string is ever written to the repo:
the scanner's own "no false positives on this repo" test stays honest, and hosted
secret scanning never mistakes a fixture for a leak. Every value contains FAKE.
"""

RANDOMISH = "Zq8FAKEw3Rt7Yu1Io5Pa9Sd2"

FAKE_SECRETS = {
    "aws-access-key-id": "AKIA" + "FAKE0000TEST0000",
    "github-token": "ghp_" + "FAKE" * 9,
    "anthropic-api-key": "sk-" + "ant-" + "api03-" + "FAKE" * 8,
    "openai-api-key": "sk-" + "proj-" + "FAKE" * 10,
    "slack-token": "xox" + "b-" + "0000000000-FAKEFAKEFAKE",
    "stripe-secret-key": "sk_" + "live_" + "FAKE" * 6,
    "google-api-key": "AIza" + "FAKE" * 8 + "abc",
    "private-key": "-----BEGIN " + "RSA PRIVATE KEY-----",
    "generic-secret": 'api_key = "' + RANDOMISH + '"',
}
