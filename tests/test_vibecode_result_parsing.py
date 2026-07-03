"""Tests for parse_result_line — the worker-result extraction that decides
whether the bot reports a /vibecode run as success or failure."""

import unittest

from services.vibecode_service import parse_result_line

SUCCESS = (
    'VIBECODE_RESULT:{"status":"success",'
    '"pr_url":"https://github.com/o/r/pull/27","branch":"vibecode/x"}'
)


class TestParseResultLine(unittest.TestCase):
    def test_clean_multiline_log(self):
        log = f"=== pushing ===\nsome output\n{SUCCESS}\n"
        result = parse_result_line(log)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["pr_url"], "https://github.com/o/r/pull/27")

    def test_bytes_blob_with_literal_newlines(self):
        # Reproduces the real failure: the whole log arrives as one blob with
        # escaped newlines and trailing repr junk (b'...\n'), so splitlines()
        # can't isolate the marker line and the JSON has a trailing "\n'".
        blob = "b'=== running ===\\nRan 119 tests\\n" + SUCCESS + "\\n'"
        result = parse_result_line(blob)
        self.assertIsNotNone(result, "success blob must still parse")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["branch"], "vibecode/x")

    def test_trailing_junk_after_json(self):
        result = parse_result_line(SUCCESS + "   \ntrailing noise")
        self.assertEqual(result["status"], "success")

    def test_last_marker_wins(self):
        failed = 'VIBECODE_RESULT:{"status":"failed","reason":"x"}'
        result = parse_result_line(f"{failed}\n{SUCCESS}")
        self.assertEqual(result["status"], "success")

    def test_no_marker_returns_none(self):
        self.assertIsNone(parse_result_line("nothing to see here"))

    def test_failed_result_parsed(self):
        log = 'VIBECODE_RESULT:{"status":"failed","reason":"boom"}'
        result = parse_result_line(log)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["reason"], "boom")


if __name__ == "__main__":
    unittest.main()
