"""Regression tests for the credential detector and the scan work list.

The detector's whole design rests on one promise: same input, same answer,
forever. These tests are that promise written down. Run them after ANY change
to scan/detect.py or scan/worklist.py:

    python -m unittest discover tests

unittest ships with Python, so this adds no dependency to requirements.txt.

No real credential appears in this file. Keys are built from the test's own
fixed bytes, and "AKIA" + 16 letters is only the *shape* of an AWS key.
"""

from __future__ import annotations

import base64
import unittest

from scan.detect import ALLOWLIST, RULES_VERSION, scan_text
from scan.worklist import select_repos

FAKE_AWS = "AKIA" + "QWERTYUIOPASDFGH"
FAKE_AWS_2 = "AKIA" + "ZXCVBNMLKJHGFDSA"


def fake_pem(seed: int, kind: str = "RSA ", width: int = 64, newline: str = "\n") -> str:
    """A syntactically key-shaped block from deterministic bytes. Not a key."""
    body = base64.b64encode(bytes((seed * 31 + i) % 256 for i in range(600))).decode()
    lines = [body[i:i + width] for i in range(0, len(body), width)]
    return newline.join(
        [f"-----BEGIN {kind}PRIVATE KEY-----", *lines, f"-----END {kind}PRIVATE KEY-----"]
    )


class LineRules(unittest.TestCase):
    """The six fixtures Nicholas verified scan_text() against in session 14."""

    def test_clean_file_has_no_findings(self):
        self.assertEqual(scan_text("import os\nprint('hello')\n", "a.py"), [])

    def test_single_key(self):
        found = scan_text(f'key = "{FAKE_AWS}"\n', "a.py")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["rule"], "aws_access_key_id")
        self.assertEqual(found[0]["line"], 1)

    def test_allowlisted_placeholder_is_skipped(self):
        example = sorted(ALLOWLIST)[0]
        self.assertEqual(scan_text(f"key = '{example}'\n", "README.md"), [])

    def test_real_key_on_same_line_as_placeholder_still_counts(self):
        example = sorted(ALLOWLIST)[0]
        found = scan_text(f"{example} {FAKE_AWS}\n", "a.py")
        self.assertEqual(len(found), 1)

    def test_two_rules_on_one_line(self):
        line = f"{FAKE_AWS} ghp_{'a' * 36}\n"
        rules = sorted(f["rule"] for f in scan_text(line, "a.py"))
        self.assertEqual(rules, ["aws_access_key_id", "github_token"])

    def test_one_rule_twice_on_one_line(self):
        found = scan_text(f"{FAKE_AWS},{FAKE_AWS_2}\n", "a.py")
        self.assertEqual(len(found), 2)
        self.assertNotEqual(found[0]["match_sha256"], found[1]["match_sha256"])

    def test_fingerprint_ignores_line_number(self):
        """A key that moves down the file is the same finding, not a new one."""
        a = scan_text(f"{FAKE_AWS}\n", "a.py")[0]
        b = scan_text(f"import os\n\n\n{FAKE_AWS}\n", "a.py")[0]
        self.assertEqual(a["match_sha256"], b["match_sha256"])
        self.assertNotEqual(a["line"], b["line"])

    def test_secret_is_never_stored(self):
        found = scan_text(f"{FAKE_AWS}\n", "a.py")[0]
        self.assertNotIn(FAKE_AWS, repr(found))


class PrivateKeys(unittest.TestCase):
    """Rules version 2: the session-16 fix."""

    def test_rules_version_was_bumped(self):
        self.assertGreaterEqual(RULES_VERSION, 2)

    def test_whole_key_is_found_once_at_its_begin_line(self):
        text = "config:\n" + fake_pem(1) + "\n"
        found = scan_text(text, "id_rsa")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["rule"], "private_key_block")
        self.assertEqual(found[0]["line"], 2)

    def test_different_keys_get_different_fingerprints(self):
        """THE v1 bug: every RSA key hashed to the same BEGIN line."""
        a = scan_text(fake_pem(1), "a")[0]["match_sha256"]
        b = scan_text(fake_pem(2), "b")[0]["match_sha256"]
        self.assertNotEqual(a, b)

    def test_same_key_formatted_differently_is_the_same_finding(self):
        """Line endings, wrapping and JSON escaping must not change identity."""
        base = scan_text(fake_pem(1), "a")[0]["match_sha256"]
        crlf = scan_text(fake_pem(1, newline="\r\n"), "a")[0]["match_sha256"]
        rewrapped = scan_text(fake_pem(1, width=76), "a")[0]["match_sha256"]
        json_escaped = scan_text(
            '{"private_key": "' + fake_pem(1, newline="\\n") + '\\n"}', "sa.json"
        )[0]["match_sha256"]
        self.assertEqual({base, crlf, rewrapped, json_escaped}, {base})

    def test_key_type_is_part_of_identity(self):
        rsa = scan_text(fake_pem(1, kind="RSA "), "a")[0]["match_sha256"]
        ec = scan_text(fake_pem(1, kind="EC "), "a")[0]["match_sha256"]
        self.assertNotEqual(rsa, ec)

    def test_two_keys_in_one_file(self):
        found = scan_text(fake_pem(1) + "\n\n" + fake_pem(2), "keys.pem")
        self.assertEqual(len(found), 2)

    def test_header_alone_is_not_a_finding(self):
        self.assertEqual(scan_text("-----BEGIN RSA PRIVATE KEY-----\n", "README.md"), [])

    def test_documentation_placeholder_is_not_a_finding(self):
        doc = "-----BEGIN PRIVATE KEY-----\n...your key here...\n-----END PRIVATE KEY-----"
        self.assertEqual(scan_text(doc, "README.md"), [])

    def test_mismatched_begin_and_end_types_do_not_pair(self):
        text = fake_pem(1, kind="RSA ").replace("END RSA ", "END EC ")
        self.assertEqual(scan_text(text, "a"), [])


class WorkList(unittest.TestCase):
    """select_repos(): decision A from session 15."""

    LIVENESS = [
        {"repository_url": "A", "reachable": True, "head_sha": "a1"},
        {"repository_url": "A", "reachable": True, "head_sha": "a1"},   # shared repo
        {"repository_url": "B", "reachable": True, "head_sha": "b2"},
        {"repository_url": "C", "reachable": False, "head_sha": None},
        {"repository_url": "D", "reachable": True, "head_sha": "d1"},
    ]
    HISTORY = [
        {"repository_url": "A", "commit_sha": "a1", "status": "timeout"},
        {"repository_url": "B", "commit_sha": "b1", "status": "scanned"},
        {"repository_url": "D", "commit_sha": "d1", "status": "scanned"},
    ]

    def test_first_run_scans_every_live_repo_once(self):
        self.assertEqual(select_repos(self.LIVENESS, []), ["A", "B", "D"])

    def test_rules(self):
        # A: failed last time -> retried, once.  B: new commit -> scanned.
        # C: unreachable -> skipped.             D: unchanged -> skipped.
        self.assertEqual(select_repos(self.LIVENESS, self.HISTORY), ["A", "B"])


if __name__ == "__main__":
    unittest.main()
