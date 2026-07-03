"""
Vibecode service: lets the bot extend itself.

Spawns a Kubernetes Job that clones this repository, runs an agentic coding
AI (aider + DeepSeek) against a user-supplied feature request, verifies the
result with the test suite and ruff, then pushes a branch and opens a PR.
"""

import asyncio
import json
import logging
import re
import secrets
import time
from dataclasses import dataclass, field

from kubernetes import client as k8s_client
from kubernetes import config as k8s_config
from kubernetes.config.config_exception import ConfigException

from config import Config

logger = logging.getLogger(__name__)

RESULT_MARKER = "VIBECODE_RESULT:"
IN_CLUSTER_NAMESPACE_FILE = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
POLL_INTERVAL_SECONDS = 20
LOG_TAIL_LINES = 400

PROMPT_TEMPLATE = """You are an autonomous coding agent working on the source code of \
"vibe-coding-discord-bot", a German-language Discord bot built with discord.py 2.x \
and MariaDB.

Implement the following feature, requested by Discord user "{username}":

--- FEATURE REQUEST ---
{feature}
--- END FEATURE REQUEST ---

Follow these repository conventions strictly:
1. Slash commands are discord.py Cogs in commands/<name>_command.py exposing
   `async def setup(bot, db_manager)`; new commands must be registered in
   main.py's setup_hook.
2. Configuration comes from environment variables declared in config.py (with
   sane defaults) and documented in .env.example.
3. Database access goes through the DatabaseManager class in database.py;
   schema changes must be idempotent (CREATE TABLE IF NOT EXISTS or guarded
   ALTER TABLE, following the existing create_tables pattern).
4. User-facing Discord messages use embeds and match the tone of the existing
   commands (German where the surrounding feature is German).
5. Handle errors with try/except and logger.error like the existing commands.

Quality gates - the work is not done until all of these pass:
- Add unit tests for the new code in tests/ (unittest style, mock Discord
  objects and the database like the existing tests do).
- `python -m unittest discover tests` passes.
- `ruff check .` and `ruff format --check .` are clean.

Keep the change minimal and focused on the requested feature. Do not refactor
unrelated code."""


class VibeCodeError(Exception):
    """User-facing error raised when a vibecode job cannot be started."""


@dataclass
class VibeCodeResult:
    status: str  # success | failed | timeout | error
    pr_url: str | None = None
    branch: str | None = None
    reason: str | None = None
    log_tail: str = field(default="", repr=False)

    @property
    def succeeded(self) -> bool:
        return self.status == "success"


def sanitize_slug(text: str, max_length: int = 30) -> str:
    """Turn arbitrary text into a git-branch/k8s-safe lowercase slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_length].strip("-") or "feature"


def build_enhanced_prompt(feature: str, username: str) -> str:
    """Wrap the raw user request with repo conventions and quality gates."""
    return PROMPT_TEMPLATE.format(feature=feature.strip(), username=username)


def parse_result_line(log_text: str) -> dict | None:
    """Extract the last VIBECODE_RESULT json line from worker logs."""
    result = None
    for line in log_text.splitlines():
        line = line.strip()
        if RESULT_MARKER in line:
            payload = line.split(RESULT_MARKER, 1)[1].strip()
            try:
                result = json.loads(payload)
            except json.JSONDecodeError:
                logger.warning(f"Unparseable vibecode result line: {line!r}")
    return result


class VibeCodeService:
    """Creates and tracks Kubernetes Jobs running the vibecode worker."""

    def __init__(self):
        self._last_run_per_user: dict[int, float] = {}
        self._active_jobs: set[str] = set()
        self._kube_loaded = False

    # --- rate limiting -------------------------------------------------

    def cooldown_remaining(self, user_id: int) -> int:
        """Seconds until the user may start the next job (0 = allowed)."""
        last = self._last_run_per_user.get(user_id)
        if last is None:
            return 0
        elapsed = time.monotonic() - last
        return max(0, int(Config.VIBECODE_COOLDOWN_SECONDS - elapsed))

    @property
    def active_job_count(self) -> int:
        return len(self._active_jobs)

    def ensure_can_start(self, user_id: int) -> None:
        """Raise VibeCodeError if rate limits or config forbid a new job."""
        if not Config.DEEPSEEK_API_KEY or not Config.VIBECODE_GITHUB_TOKEN:
            raise VibeCodeError(
                "Vibecode ist nicht vollständig konfiguriert "
                "(DEEPSEEK_API_KEY / VIBECODE_GITHUB_TOKEN fehlt)."
            )
        if self.active_job_count >= Config.VIBECODE_MAX_CONCURRENT_JOBS:
            raise VibeCodeError(
                "Es läuft bereits ein Vibecode-Auftrag. "
                "Bitte warte, bis er fertig ist."
            )
        remaining = self.cooldown_remaining(user_id)
        if remaining > 0:
            raise VibeCodeError(
                f"Cooldown aktiv - bitte warte noch {remaining // 60}m "
                f"{remaining % 60}s."
            )

    # --- kubernetes plumbing -------------------------------------------

    def _ensure_kube_config(self) -> None:
        if self._kube_loaded:
            return
        try:
            k8s_config.load_incluster_config()
            logger.info("Loaded in-cluster Kubernetes config")
        except ConfigException:
            k8s_config.load_kube_config()
            logger.info("Loaded local kubeconfig")
        self._kube_loaded = True

    def _namespace(self) -> str:
        if Config.VIBECODE_NAMESPACE:
            return Config.VIBECODE_NAMESPACE
        try:
            with open(IN_CLUSTER_NAMESPACE_FILE) as f:
                return f.read().strip()
        except OSError:
            return "default"

    def build_job_manifest(
        self, job_name: str, branch: str, prompt: str, pr_title: str, feature: str
    ) -> dict:
        secret = Config.VIBECODE_SECRET_NAME
        pod_spec = {
            "restartPolicy": "Never",
            "securityContext": {
                "runAsNonRoot": True,
                "runAsUser": 1000,
                "runAsGroup": 1000,
                "fsGroup": 1000,
            },
            "containers": [
                {
                    "name": "vibecode-worker",
                    "image": Config.VIBECODE_WORKER_IMAGE,
                    "imagePullPolicy": "Always",
                    "env": [
                        {"name": "VIBECODE_REPO", "value": Config.VIBECODE_REPO},
                        {
                            "name": "VIBECODE_BASE_BRANCH",
                            "value": Config.VIBECODE_BASE_BRANCH,
                        },
                        {"name": "VIBECODE_BRANCH", "value": branch},
                        {"name": "VIBECODE_PROMPT", "value": prompt},
                        {"name": "VIBECODE_FEATURE", "value": feature},
                        {"name": "VIBECODE_PR_TITLE", "value": pr_title},
                        {"name": "AIDER_MODEL", "value": Config.VIBECODE_MODEL},
                        {
                            "name": "DEEPSEEK_API_KEY",
                            "valueFrom": {
                                "secretKeyRef": {
                                    "name": secret,
                                    "key": "DEEPSEEK_API_KEY",
                                }
                            },
                        },
                        {
                            "name": "GITHUB_TOKEN",
                            "valueFrom": {
                                "secretKeyRef": {
                                    "name": secret,
                                    "key": "VIBECODE_GITHUB_TOKEN",
                                }
                            },
                        },
                    ],
                    "resources": {
                        "requests": {"cpu": "100m", "memory": "512Mi"},
                        "limits": {"cpu": "2000m", "memory": "2Gi"},
                    },
                }
            ],
        }
        if Config.VIBECODE_IMAGE_PULL_SECRET:
            pod_spec["imagePullSecrets"] = [{"name": Config.VIBECODE_IMAGE_PULL_SECRET}]
        return {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": job_name,
                "labels": {"app": "vibecode-worker"},
            },
            "spec": {
                "backoffLimit": 0,
                "activeDeadlineSeconds": Config.VIBECODE_JOB_TIMEOUT_SECONDS,
                "ttlSecondsAfterFinished": 3600,
                "template": {
                    "metadata": {"labels": {"app": "vibecode-worker"}},
                    "spec": pod_spec,
                },
            },
        }

    # --- job lifecycle ---------------------------------------------------

    async def start_job(self, user_id: int, username: str, feature: str) -> str:
        """Create the worker Job. Returns the job name. Raises VibeCodeError."""
        self.ensure_can_start(user_id)

        suffix = f"{int(time.time())}-{secrets.token_hex(2)}"
        job_name = f"vibecode-{suffix}"
        branch = f"vibecode/{suffix}-{sanitize_slug(feature)}"
        pr_title = f"feat: {feature.strip()[:60]}"
        prompt = build_enhanced_prompt(feature, username)
        manifest = self.build_job_manifest(
            job_name, branch, prompt, pr_title, feature.strip()
        )

        def _create():
            self._ensure_kube_config()
            batch = k8s_client.BatchV1Api()
            batch.create_namespaced_job(namespace=self._namespace(), body=manifest)

        try:
            await asyncio.to_thread(_create)
        except Exception as e:
            logger.error(f"Failed to create vibecode job: {e}")
            raise VibeCodeError("Der Worker-Job konnte nicht gestartet werden.") from e

        self._active_jobs.add(job_name)
        self._last_run_per_user[user_id] = time.monotonic()
        logger.info(
            f"Started vibecode job {job_name} (branch {branch}) "
            f"for {username} ({user_id})"
        )
        return job_name

    async def wait_for_job(self, job_name: str) -> VibeCodeResult:
        """Poll the Job until it finishes, then read logs and parse result."""
        deadline = time.monotonic() + Config.VIBECODE_JOB_TIMEOUT_SECONDS + 300
        try:
            while time.monotonic() < deadline:
                status = await asyncio.to_thread(self._read_job_status, job_name)
                if status is not None:
                    log_tail = await asyncio.to_thread(self._read_pod_logs, job_name)
                    return self._build_result(status, log_tail)
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
            return VibeCodeResult(
                status="timeout",
                reason="Der Job hat das Zeitlimit überschritten.",
            )
        except Exception as e:
            logger.error(f"Error while watching vibecode job {job_name}: {e}")
            return VibeCodeResult(
                status="error",
                reason="Fehler beim Überwachen des Jobs.",
            )
        finally:
            self._active_jobs.discard(job_name)

    def _read_job_status(self, job_name: str) -> str | None:
        """Return 'succeeded'/'failed' once the job finished, else None."""
        self._ensure_kube_config()
        batch = k8s_client.BatchV1Api()
        job = batch.read_namespaced_job(name=job_name, namespace=self._namespace())
        if job.status.succeeded:
            return "succeeded"
        if job.status.failed:
            return "failed"
        return None

    def _read_pod_logs(self, job_name: str) -> str:
        self._ensure_kube_config()
        core = k8s_client.CoreV1Api()
        namespace = self._namespace()
        try:
            pods = core.list_namespaced_pod(
                namespace=namespace, label_selector=f"job-name={job_name}"
            )
            if not pods.items:
                return ""
            return core.read_namespaced_pod_log(
                name=pods.items[0].metadata.name,
                namespace=namespace,
                tail_lines=LOG_TAIL_LINES,
            )
        except Exception as e:
            logger.warning(f"Could not read logs for job {job_name}: {e}")
            return ""

    def _build_result(self, job_status: str, log_tail: str) -> VibeCodeResult:
        parsed = parse_result_line(log_tail) or {}
        if job_status == "succeeded" and parsed.get("status") == "success":
            return VibeCodeResult(
                status="success",
                pr_url=parsed.get("pr_url"),
                branch=parsed.get("branch"),
                log_tail=log_tail,
            )
        return VibeCodeResult(
            status="failed",
            reason=parsed.get("reason", "Der Coding-Agent ist gescheitert."),
            branch=parsed.get("branch"),
            log_tail=log_tail,
        )
