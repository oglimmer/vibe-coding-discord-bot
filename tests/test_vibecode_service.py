"""Unit tests for the vibecode service (no cluster access needed)."""

import unittest
from unittest.mock import patch

from config import Config
from services.vibecode_service import (
    VibeCodeError,
    VibeCodeService,
    build_enhanced_prompt,
    parse_result_line,
    sanitize_slug,
)


class TestSanitizeSlug(unittest.TestCase):
    def test_lowercases_and_replaces_special_chars(self):
        self.assertEqual(
            sanitize_slug("Add a /weather command!"), "add-a-weather-command"
        )

    def test_truncates_and_strips_trailing_dash(self):
        slug = sanitize_slug("a" * 29 + "!b")
        self.assertLessEqual(len(slug), 30)
        self.assertFalse(slug.endswith("-"))

    def test_empty_input_falls_back(self):
        self.assertEqual(sanitize_slug("!!!"), "feature")


class TestPromptEnhancement(unittest.TestCase):
    def test_contains_feature_and_username(self):
        prompt = build_enhanced_prompt("add a dice roll command", "TestUser")
        self.assertIn("add a dice roll command", prompt)
        self.assertIn("TestUser", prompt)

    def test_contains_quality_gates_and_conventions(self):
        prompt = build_enhanced_prompt("something", "u")
        self.assertIn("python -m unittest discover tests", prompt)
        self.assertIn("ruff check .", prompt)
        self.assertIn("commands/<name>_command.py", prompt)
        self.assertIn("main.py", prompt)


class TestParseResultLine(unittest.TestCase):
    def test_parses_success_line(self):
        logs = (
            "cloning...\n"
            'VIBECODE_RESULT:{"status":"success","pr_url":"https://x/pr/1","branch":"b"}\n'
        )
        result = parse_result_line(logs)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["pr_url"], "https://x/pr/1")

    def test_last_result_line_wins(self):
        logs = (
            'VIBECODE_RESULT:{"status":"failed","reason":"first"}\n'
            'VIBECODE_RESULT:{"status":"success","pr_url":"u"}\n'
        )
        self.assertEqual(parse_result_line(logs)["status"], "success")

    def test_returns_none_without_marker(self):
        self.assertIsNone(parse_result_line("no result here\n"))

    def test_ignores_invalid_json(self):
        self.assertIsNone(parse_result_line("VIBECODE_RESULT:not-json\n"))


class TestRateLimiting(unittest.TestCase):
    def setUp(self):
        self.service = VibeCodeService()

    @patch.object(Config, "VIBECODE_GITHUB_TOKEN", "t")
    @patch.object(Config, "DEEPSEEK_API_KEY", "k")
    def test_allows_first_run(self):
        self.service.ensure_can_start(user_id=1)  # must not raise

    @patch.object(Config, "VIBECODE_GITHUB_TOKEN", None)
    @patch.object(Config, "DEEPSEEK_API_KEY", "k")
    def test_rejects_when_unconfigured(self):
        with self.assertRaises(VibeCodeError):
            self.service.ensure_can_start(user_id=1)

    @patch.object(Config, "VIBECODE_GITHUB_TOKEN", "t")
    @patch.object(Config, "DEEPSEEK_API_KEY", "k")
    @patch.object(Config, "VIBECODE_MAX_CONCURRENT_JOBS", 1)
    def test_rejects_when_concurrency_limit_reached(self):
        self.service._active_jobs.add("vibecode-running")
        with self.assertRaises(VibeCodeError):
            self.service.ensure_can_start(user_id=1)

    @patch.object(Config, "VIBECODE_GITHUB_TOKEN", "t")
    @patch.object(Config, "DEEPSEEK_API_KEY", "k")
    @patch.object(Config, "VIBECODE_COOLDOWN_SECONDS", 900)
    def test_rejects_during_cooldown(self):
        import time

        self.service._last_run_per_user[1] = time.monotonic()
        with self.assertRaises(VibeCodeError):
            self.service.ensure_can_start(user_id=1)
        # another user is unaffected
        self.service.ensure_can_start(user_id=2)

    def test_cooldown_remaining_zero_for_unknown_user(self):
        self.assertEqual(self.service.cooldown_remaining(42), 0)


class TestJobManifest(unittest.TestCase):
    def setUp(self):
        self.service = VibeCodeService()
        self.manifest = self.service.build_job_manifest(
            job_name="vibecode-123-ab",
            branch="vibecode/123-ab-my-feature",
            prompt="enhanced prompt",
            pr_title="feat: my feature",
            feature="my feature",
        )

    def test_basic_shape(self):
        self.assertEqual(self.manifest["kind"], "Job")
        self.assertEqual(self.manifest["metadata"]["name"], "vibecode-123-ab")
        spec = self.manifest["spec"]
        self.assertEqual(spec["backoffLimit"], 0)
        self.assertEqual(
            spec["activeDeadlineSeconds"], Config.VIBECODE_JOB_TIMEOUT_SECONDS
        )

    def test_container_env(self):
        container = self.manifest["spec"]["template"]["spec"]["containers"][0]
        env = {e["name"]: e for e in container["env"]}
        self.assertEqual(env["VIBECODE_BRANCH"]["value"], "vibecode/123-ab-my-feature")
        self.assertEqual(env["VIBECODE_PROMPT"]["value"], "enhanced prompt")
        self.assertEqual(env["VIBECODE_FEATURE"]["value"], "my feature")
        # secrets must come from secretKeyRef, never inline values
        self.assertIn("valueFrom", env["DEEPSEEK_API_KEY"])
        self.assertIn("valueFrom", env["GITHUB_TOKEN"])
        self.assertNotIn("value", env["GITHUB_TOKEN"])

    def test_pod_runs_as_non_root(self):
        sec = self.manifest["spec"]["template"]["spec"]["securityContext"]
        self.assertTrue(sec["runAsNonRoot"])

    @patch.object(Config, "VIBECODE_IMAGE_PULL_SECRET", "pullkey")
    def test_image_pull_secret_included_when_configured(self):
        manifest = self.service.build_job_manifest("j", "b", "p", "t", "f")
        self.assertEqual(
            manifest["spec"]["template"]["spec"]["imagePullSecrets"],
            [{"name": "pullkey"}],
        )

    def test_image_pull_secret_omitted_by_default(self):
        with patch.object(Config, "VIBECODE_IMAGE_PULL_SECRET", None):
            manifest = self.service.build_job_manifest("j", "b", "p", "t", "f")
            self.assertNotIn("imagePullSecrets", manifest["spec"]["template"]["spec"])


class TestBuildResult(unittest.TestCase):
    def setUp(self):
        self.service = VibeCodeService()

    def test_success(self):
        logs = (
            'VIBECODE_RESULT:{"status":"success","pr_url":"https://x/1","branch":"b"}'
        )
        result = self.service._build_result("succeeded", logs)
        self.assertTrue(result.succeeded)
        self.assertEqual(result.pr_url, "https://x/1")

    def test_job_succeeded_but_no_result_line_is_failure(self):
        result = self.service._build_result("succeeded", "no marker")
        self.assertFalse(result.succeeded)

    def test_failure_reason_from_worker(self):
        logs = 'VIBECODE_RESULT:{"status":"failed","reason":"git push failed"}'
        result = self.service._build_result("failed", logs)
        self.assertFalse(result.succeeded)
        self.assertEqual(result.reason, "git push failed")

    def test_failure_without_result_line_gets_default_reason(self):
        result = self.service._build_result("failed", "")
        self.assertFalse(result.succeeded)
        self.assertTrue(result.reason)


if __name__ == "__main__":
    unittest.main()
