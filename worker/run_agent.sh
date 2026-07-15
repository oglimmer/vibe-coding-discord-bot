#!/usr/bin/env bash
# Vibecode worker pipeline (Claude Code / DeepSeek):
#   clone repo -> Claude Code implements the feature (with tests) -> pre-PR
#   self-review gate -> pre-PR verify gate -> push -> open PR -> wait for the
#   ai-review GitHub Action -> fix any findings with Claude Code -> re-review
#   -> report result.
#
# Adapted from the coding-agent platform's worker-claude. Differences here:
#   * env vars keep this repo's VIBECODE_* naming and the VIBECODE_RESULT marker;
#   * only this (Python) repo is ever targeted, so dependency preparation is a
#     single venv instead of the polyglot stack detection;
#   * auto-merge defaults OFF — /vibecode is open to every Discord user and main
#     auto-deploys, so a human presses the merge button.
#
# Required env: GITHUB_TOKEN, DEEPSEEK_API_KEY, VIBECODE_REPO (owner/name),
#               VIBECODE_BRANCH, VIBECODE_PROMPT, VIBECODE_PR_TITLE
# Optional env:
#   VIBECODE_BASE_BRANCH  default: main
#   VIBECODE_FEATURE      raw feature text (for the PR body / self-review)
#   VIBECODE_VERIFY_CMD   build/lint/test gate run before the PR (default: this
#                         repo's CI equivalent). Empty disables it.
#   VIBECODE_AUTO_MERGE   "true" squash-merges an approved+green PR; anything
#                         else (default) leaves it open for a human
#   CLAUDE_MODEL          Claude Code primary model, default: deepseek-v4-pro. A
#                         deepseek-* id runs on the DeepSeek backend; a claude-*
#                         id runs on the real Anthropic API (ANTHROPIC_API_KEY).
#   CLAUDE_SMALL_MODEL    subagent/haiku-tier model; default tracks the backend
#   ANTHROPIC_API_KEY     required when CLAUDE_MODEL is a claude-* model
#   ANTHROPIC_BASE_URL    default: ${DEEPSEEK_BASE_URL}/anthropic on DeepSeek
#   CLAUDE_TIMEOUT        seconds per Claude round before it is killed (default: 1200)
#   GITHUB_BOT_LOGIN      reviewer login to treat as "self" (ignored when waiting)
#   REVIEW_MAX_ROUNDS     default: 2
#   REVIEW_TIMEOUT        seconds to wait per review round (default: 900)
#   REVIEW_POLL           seconds between polls (default: 20)
#   NO_CHECK_GRACE        polls before trusting a "no checks" reading (default: 3)
#   DEEPSEEK_BASE_URL     helper-call API base (default: https://api.deepseek.com)
#   REVIEW_JUDGE_MODEL    model for self-review + review-judging (default: deepseek-chat)
#   SELF_REVIEW_ROUNDS    pre-PR corrective rounds (default: 2)
#   VERIFY_MAX_ROUNDS     corrective rounds for the verify gate (default: 2)
#   VIBECODE_VERIFY_TIMEOUT seconds for the verify gate (default: 900)
set -uo pipefail

BASE_BRANCH="${VIBECODE_BASE_BRANCH:-main}"
BOT_LOGIN="${GITHUB_BOT_LOGIN:-vibecode-bot}"
REVIEW_MAX_ROUNDS="${REVIEW_MAX_ROUNDS:-2}"
REVIEW_TIMEOUT="${REVIEW_TIMEOUT:-900}"
REVIEW_POLL="${REVIEW_POLL:-20}"
# Polls to wait before trusting a "0 check runs" reading (repo has no checks vs.
# a just-pushed commit whose checks have not registered yet).
NO_CHECK_GRACE="${NO_CHECK_GRACE:-3}"
DEEPSEEK_BASE_URL="${DEEPSEEK_BASE_URL:-https://api.deepseek.com}"
# The ai-review action never emits a formal APPROVED/CHANGES_REQUESTED verdict —
# its real judgment is prose in a COMMENTED review. We classify that prose with a
# model before merging, using the same DeepSeek credentials as the coding model.
REVIEW_JUDGE_MODEL="${REVIEW_JUDGE_MODEL:-deepseek-chat}"
SELF_REVIEW_ROUNDS="${SELF_REVIEW_ROUNDS:-2}"
# Hard per-round bound: a model stuck in a loop must not ride out the whole Job
# deadline.
CLAUDE_TIMEOUT="${CLAUDE_TIMEOUT:-1200}"
# Authoritative pre-PR verification: this repo's real lint/test command — the same
# checks .github/workflows/ci.yml runs. Empty = rely on Claude Code's own checks
# plus the pre-commit hooks.
VERIFY_CMD="${VIBECODE_VERIFY_CMD-ruff check . && ruff format --check . && python -m unittest discover tests && python -m pytest tests/test_e2e_1337.py}"
# Whether to squash-merge the PR once approved and green. Defaults OFF: /vibecode
# is open to every Discord user and main auto-deploys via ArgoCD, so the final
# merge stays a human decision. Only an explicit "true" enables it.
AUTO_MERGE="${VIBECODE_AUTO_MERGE:-false}"
# Per-invocation cap for the verify gate (a hanging test script must degrade to a
# failed round, never a dead job).
VERIFY_TIMEOUT="${VIBECODE_VERIFY_TIMEOUT:-900}"
VERIFY_MAX_ROUNDS="${VERIFY_MAX_ROUNDS:-2}"
REPO_DIR=/work/repo
VENV=/work/venv
API="https://api.github.com/repos/${VIBECODE_REPO:-}"

# --- Claude Code backend (switchable per model) --------------------------------
# Claude Code speaks one Anthropic-compatible API; which provider it talks to is
# derived from the requested model, so a single worker image serves both:
#   * a DeepSeek model id (deepseek-*) runs against DeepSeek's Anthropic-compatible
#     endpoint, authenticated with DEEPSEEK_API_KEY (the default);
#   * a Claude model id (claude-*) runs against the real Anthropic API,
#     authenticated with ANTHROPIC_API_KEY.
# Claude Code drives EVERY tier (opus/sonnet/haiku aliases, subagents) on that one
# backend, so the small/haiku model must come from the same provider as the primary.
CLAUDE_MODEL="${CLAUDE_MODEL:-deepseek-v4-pro}"
case "$CLAUDE_MODEL" in
  claude*|anthropic/*) CLAUDE_BACKEND="anthropic" ;;
  *)                   CLAUDE_BACKEND="deepseek" ;;
esac

if [ "$CLAUDE_BACKEND" = "anthropic" ]; then
  # Real Anthropic API: standard API-key auth, default base URL. Clear any
  # DeepSeek-gateway overrides so a stray env var cannot divert the request.
  CLAUDE_SMALL_MODEL="${CLAUDE_SMALL_MODEL:-claude-haiku-4-5}"
  unset ANTHROPIC_BASE_URL ANTHROPIC_AUTH_TOKEN
  export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"
else
  # DeepSeek's Anthropic-compatible endpoint, authenticated with the DeepSeek key.
  CLAUDE_SMALL_MODEL="${CLAUDE_SMALL_MODEL:-deepseek-v4-flash}"
  export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-${DEEPSEEK_BASE_URL}/anthropic}"
  export ANTHROPIC_AUTH_TOKEN="${DEEPSEEK_API_KEY:-}"
fi
export ANTHROPIC_MODEL="$CLAUDE_MODEL"
export ANTHROPIC_DEFAULT_OPUS_MODEL="$CLAUDE_MODEL"
export ANTHROPIC_DEFAULT_SONNET_MODEL="$CLAUDE_MODEL"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="$CLAUDE_SMALL_MODEL"
export CLAUDE_CODE_SUBAGENT_MODEL="$CLAUDE_SMALL_MODEL"
export CLAUDE_CODE_EFFORT_LEVEL="${CLAUDE_CODE_EFFORT_LEVEL:-max}"
# Keep the ephemeral Job hermetic and non-interactive: no telemetry, no
# auto-update, no first-run onboarding.
export DISABLE_TELEMETRY=1
export DISABLE_AUTOUPDATER=1
export DISABLE_ERROR_REPORTING=1
export DISABLE_NON_ESSENTIAL_MODEL_CALLS=1
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1

emit_result() {
  # single-line JSON so the bot can grep it out of the pod logs
  echo "VIBECODE_RESULT:$1"
}

fail() {
  emit_result "$(jq -cn --arg r "$1" --arg b "${VIBECODE_BRANCH:-}" \
    '{status:"failed", reason:$r, branch:$b}')"
  exit 1
}

gh_api() {
  # gh_api METHOD URL [DATA] — echoes the response body. Returns non-zero on a
  # network error or an HTTP status >= 400, so callers can tell a real failure
  # from an empty-but-valid result (a rate-limited poll must NOT read as "no
  # checks"). Idempotent GETs are retried a couple of times on 429/5xx/network.
  local method="$1" url="$2" data="${3:-}"
  local attempt=0 resp curl_rc code body
  while :; do
    attempt=$((attempt + 1))
    if [ -n "$data" ]; then
      resp=$(curl -sS --max-time 60 -w $'\n%{http_code}' -X "$method" \
        -H "Authorization: Bearer ${GITHUB_TOKEN}" \
        -H "Accept: application/vnd.github+json" \
        "$url" -d "$data")
    else
      resp=$(curl -sS --max-time 60 -w $'\n%{http_code}' -X "$method" \
        -H "Authorization: Bearer ${GITHUB_TOKEN}" \
        -H "Accept: application/vnd.github+json" \
        "$url")
    fi
    curl_rc=$?
    code="${resp##*$'\n'}"
    body="${resp%$'\n'*}"
    if [ "$curl_rc" -ne 0 ]; then
      [ "$method" = GET ] && [ "$attempt" -lt 3 ] && { sleep 5; continue; }
      echo "WARN gh_api ${method} network error (curl rc=${curl_rc})" >&2
      printf '%s' "$body"; return 1
    fi
    if [ "${code:-0}" -ge 400 ] 2>/dev/null; then
      if [ "$method" = GET ] && [ "$attempt" -lt 3 ] \
         && { [ "$code" = 429 ] || [ "$code" -ge 500 ]; }; then
        sleep 5; continue
      fi
      echo "WARN gh_api ${method} -> HTTP ${code}" >&2
      printf '%s' "$body"; return 1
    fi
    printf '%s' "$body"; return 0
  done
}

# deepseek_call SYSTEM USER [MODEL] — one-shot chat completion against a helper
# model (self-review + review-judge); echoes the assistant content, empty output
# on any failure (callers fail open or fail safe as appropriate to their gate).
# Uses DeepSeek's OpenAI-format endpoint, NOT the /anthropic base Claude Code uses.
deepseek_call() {
  local sys="$1" user="$2" model="${3:-$REVIEW_JUDGE_MODEL}" payload resp
  payload=$(jq -cn --arg m "$model" --arg s "$sys" --arg u "$user" \
    '{model:$m, temperature:0, messages:[{role:"system",content:$s},{role:"user",content:$u}]}') || return 1
  resp=$(curl -sS --max-time 120 -X POST "${DEEPSEEK_BASE_URL}/chat/completions" \
    -H "Authorization: Bearer ${DEEPSEEK_API_KEY:-}" \
    -H "Content-Type: application/json" \
    -d "$payload") || return 1
  echo "$resp" | jq -r '.choices[0].message.content // ""'
}

# Pull the first {...} JSON object out of model prose (tolerates ```json fences).
extract_json() {
  tr '\n' ' ' | grep -o '{.*}' | head -1
}

for var in GITHUB_TOKEN VIBECODE_REPO VIBECODE_BRANCH VIBECODE_PROMPT \
           VIBECODE_PR_TITLE; do
  [ -n "${!var:-}" ] || fail "missing required env var: $var"
done
# DeepSeek is always needed for the helper judge calls (self-review / review-judge
# stay on DeepSeek regardless of the coding backend). An Anthropic-backed coding
# model additionally needs its own key.
[ -n "${DEEPSEEK_API_KEY:-}" ] || fail "missing required env var: DEEPSEEK_API_KEY"
if [ "$CLAUDE_BACKEND" = "anthropic" ]; then
  [ -n "${ANTHROPIC_API_KEY:-}" ] || fail "model ${CLAUDE_MODEL} routes to the Anthropic backend but ANTHROPIC_API_KEY is not set"
fi

# Provenance + effective config, printed into the log so a run can be analysed
# later (this block is persisted with the log even after the pod is gone).
echo "=== job metadata ==="
echo "worker_commit:  ${WORKER_GIT_COMMIT:-none}"
echo "worker_version: ${WORKER_VERSION:-dev}"
echo "worker_built:   ${WORKER_BUILD_TIME:-unknown}"
echo "engine:         claude-code"
echo "repo:           ${VIBECODE_REPO}  base=${BASE_BRANCH}"
echo "model:          ${CLAUDE_MODEL}  small=${CLAUDE_SMALL_MODEL}"
echo "backend:        ${CLAUDE_BACKEND}"
echo "claude_base:    ${ANTHROPIC_BASE_URL:-https://api.anthropic.com (default)}"
echo "helper_model:   judge=${REVIEW_JUDGE_MODEL}"
echo "review_rounds:  ${REVIEW_MAX_ROUNDS}  verify_rounds=${VERIFY_MAX_ROUNDS}  claude_timeout=${CLAUDE_TIMEOUT}s"
echo "verify_cmd:     ${VERIFY_CMD:-<none>}"
echo "auto_merge:     ${AUTO_MERGE}"
echo "deepseek_base:  ${DEEPSEEK_BASE_URL}"
echo "===================="

echo "=== vibecode worker: cloning ${VIBECODE_REPO} ==="
git clone "https://x-access-token:${GITHUB_TOKEN}@github.com/${VIBECODE_REPO}.git" \
  "$REPO_DIR" || fail "git clone failed"
cd "$REPO_DIR" || fail "repo dir missing"

git config user.name "$BOT_LOGIN"
git config user.email "${BOT_LOGIN}@users.noreply.github.com"
git checkout -b "$VIBECODE_BRANCH" "origin/${BASE_BRANCH}" || fail "branch creation failed"

# --- dependency preparation ----------------------------------------------------
# One venv for the repo's own deps, put on PATH so both Claude Code's own test
# runs and the verify gate below use it. ruff is pinned to the same rev as
# .pre-commit-config.yaml / ci.yml, so a lint pass here means a lint pass in CI.
echo "=== installing repository dependencies ==="
python -m venv "$VENV" || fail "venv creation failed"
export PATH="$VENV/bin:$PATH"
pip install --no-cache-dir --quiet --upgrade pip || fail "pip upgrade failed"
pip install --no-cache-dir --quiet -r requirements-dev.txt \
  || fail "dependency installation failed"
pip install --no-cache-dir --quiet ruff==0.8.4 || fail "ruff installation failed"

# Wrap a raw command into a bounded, CI-mode runner and echo the runner command.
# CI=1/CI=true keeps test tooling out of any watch/interactive mode; `timeout`
# kills a genuinely wedged process so a hang becomes "this round failed", not a
# dead job.
BOUNDED_SEQ=0
bounded_runner() {
  local raw="$1" secs="$2" f
  BOUNDED_SEQ=$((BOUNDED_SEQ + 1))
  f="/work/cmd-${BOUNDED_SEQ}.sh"
  printf '%s\n' "$raw" >"$f"
  printf 'env CI=1 CI=true FORCE_COLOR=0 timeout --signal=TERM --kill-after=10 %s bash %s' \
    "$secs" "$f"
}

# The verify command is the authoritative pre-PR gate, but if it is already RED on
# untouched main (broken config, red base) the agent can never make it green.
# Check it once and fail fast with a reason.
if [ -n "$VERIFY_CMD" ]; then
  echo "=== checking verify command on clean baseline: ${VERIFY_CMD} ==="
  if bash -c "$(bounded_runner "$VERIFY_CMD" "$VERIFY_TIMEOUT")" >/work/verify-baseline.log 2>&1; then
    echo "=== verify command green at baseline ==="
  else
    echo "=== verify command is RED at baseline ==="
    tail -20 /work/verify-baseline.log
    fail "the verify command fails on untouched ${BASE_BRANCH}; fix the repository's checks — not spending an agent run on it"
  fi
fi

# --- Claude Code engine --------------------------------------------------------
# Claude Code reads and edits the whole working tree itself, so it takes only a
# message file, not an explicit file set. Each round is bounded by CLAUDE_TIMEOUT.
#
# Claude Code edits the working tree but does not necessarily commit; after every
# round we stage and commit whatever changed so the downstream gates and PR see
# the work as ordinary branch commits (git diff against origin/BASE). If Claude
# committed on its own, the add/commit is a harmless no-op.
run_claude() {
  # run_claude MESSAGE_FILE
  local msg="$1"
  timeout --signal=TERM --kill-after=30 "$CLAUDE_TIMEOUT" \
    claude --print \
    --model "$CLAUDE_MODEL" \
    --dangerously-skip-permissions \
    --output-format text \
    "$(cat "$msg")"
  local rc=$?
  if [ "$rc" -eq 124 ]; then
    echo "=== claude round exceeded ${CLAUDE_TIMEOUT}s and was killed ==="
  fi
  if ! git diff --quiet || ! git diff --cached --quiet \
     || [ -n "$(git ls-files --others --exclude-standard)" ]; then
    git add -A
    git commit -m "agent: apply changes" --no-verify >/dev/null 2>&1 || true
  fi
  return $rc
}

# A corrective Claude round that is ALLOWED to time out: rc 124 (killed mid-round)
# is logged and swallowed so the surrounding gate can re-evaluate whatever got
# committed. A genuine crash (any other non-zero rc) still fails the job.
run_claude_round() {
  run_claude "$@"
  local rc=$?
  case "$rc" in
    0|124) return 0 ;;
    *) return "$rc" ;;
  esac
}

# Count of feature commits on the branch (i.e. work the model has committed).
commit_count() {
  git rev-list --count "origin/${BASE_BRANCH}..HEAD" 2>/dev/null || echo 0
}

echo "=== running claude code (model=${CLAUDE_MODEL}) ==="
{
  printf '%s' "$VIBECODE_PROMPT"
  if [ -n "$VERIFY_CMD" ]; then
    printf '\n\nBefore you are done, make sure this command passes: %s\n' "$VERIFY_CMD"
  fi
  printf '\nWork directly in the current repository checkout. Do not open a pull request or push — the surrounding tooling handles git.\n'
} > /work/prompt.txt

run_claude /work/prompt.txt
claude_rc=$?
if [ "$claude_rc" -eq 124 ]; then
  if [ "$(commit_count)" -gt 0 ]; then
    echo "=== claude timed out but committed $(commit_count) commit(s); continuing to the gates ==="
  else
    fail "claude timed out before producing any changes"
  fi
elif [ "$claude_rc" -ne 0 ]; then
  fail "claude run failed (rc=${claude_rc})"
fi

# A green suite only proves the *existing* tests still pass; it does not prove the
# new feature is exercised at all. Require the change to add or modify a test.
tests_changed() {
  [ -n "$(git diff --name-only "origin/${BASE_BRANCH}..HEAD" -- tests/)" ]
}

if ! tests_changed; then
  echo "=== no test detected; asking claude to add one ==="
  cat > /work/test-required.txt <<'EOF'
Your change does not add or modify any test under tests/. Add at least one test
that exercises the behaviour you just implemented and would FAIL if your change
were reverted. Write it unittest style (mocking Discord objects and the database
like the existing tests do) so `python -m unittest discover tests` picks it up.
Then make sure the whole suite still passes.
EOF
  run_claude_round /work/test-required.txt || fail "claude test-adding run failed"
  tests_changed || fail "the change ships no test (agent did not add one)"
fi

# Guard against a "no real work" run: reject a diff that touched ONLY .gitignore.
meaningful=$(git diff --name-only "origin/${BASE_BRANCH}..HEAD" | grep -vc '^\.gitignore$' || true)
if [ "${meaningful:-0}" -eq 0 ]; then
  fail "the coding agent made no meaningful commits"
fi

# --- pre-PR self-review --------------------------------------------------------
# Cheap gate that catches the worst failure mode BEFORE burning a PR + review
# round: the agent implementing something unrelated to the request. The judge
# model reads the actual diff; on "not implemented" we hand its critique back to
# Claude for a corrective round. Fails OPEN after SELF_REVIEW_ROUNDS.
self_review() {
  SELF_OK="no"
  SELF_CRITIQUE=""
  local diff sys user content json
  local exclude=(':(exclude)package-lock.json' ':(exclude)*.lock' ':(exclude)*.min.js')
  diff=$(
    printf 'FILES CHANGED:\n'
    git diff --stat "origin/${BASE_BRANCH}..HEAD" -- . "${exclude[@]}"
    printf '\nDIFF (generated/lockfiles omitted):\n'
    git diff "origin/${BASE_BRANCH}..HEAD" -- . "${exclude[@]}"
  )
  diff=$(printf '%s' "$diff" | head -c 60000)
  sys='You are a strict code reviewer. Given a feature request and the full diff of an automated agent'"'"'s change, judge whether the diff is ready to open as a pull request. Reply with ONLY a compact JSON object: {"implements":true|false,"critique":"<short: what is wrong and WHERE — name the two places that disagree>"}. Answer false if ANY of these hold: (a) the diff does not implement the requested behaviour in the right place, or changes unrelated code, or only partially implements it; (b) there is no meaningful automated test, OR the test does not exercise the real production code path it claims to (e.g. it re-implements the logic inline or asserts on a fixture instead of calling the actual function/command) — a test that would still pass if the production change were reverted does not count; (c) the change spans places whose contract is now inconsistent — for example a command'"'"'s setup() signature changed without updating every caller in main.py, a config value is read with a name config.py never defines, or a DB query uses a column the schema never creates. When unsure, answer false and say which two places to reconcile.'
  user=$(printf 'FEATURE REQUEST:\n%s\n\n%s\n' \
    "${VIBECODE_FEATURE:-$VIBECODE_PROMPT}" "$diff")
  content=$(deepseek_call "$sys" "$user") || return 0
  json=$(printf '%s' "$content" | extract_json)
  [ -n "$json" ] || return 0
  if [ "$(echo "$json" | jq -r '.implements // false' 2>/dev/null)" = "true" ]; then
    SELF_OK="yes"
  fi
  SELF_CRITIQUE=$(echo "$json" | jq -r '.critique // ""' 2>/dev/null)
}

self_round=0
while [ "$self_round" -lt "$SELF_REVIEW_ROUNDS" ]; do
  echo "=== pre-PR self-review (${REVIEW_JUDGE_MODEL}) ==="
  self_review
  if [ "$SELF_OK" = "yes" ]; then
    echo "=== self-review passed ==="
    break
  fi
  self_round=$((self_round + 1))
  echo "=== self-review: NOT implemented — ${SELF_CRITIQUE:-no critique} (corrective round ${self_round}/${SELF_REVIEW_ROUNDS}) ==="
  [ -n "$SELF_CRITIQUE" ] || break   # no critique to act on; fail open to the PR
  {
    echo "An independent review of your diff concluded the feature request is NOT"
    echo "correctly implemented yet. Its critique:"
    echo
    printf '%s\n' "$SELF_CRITIQUE"
    echo
    echo "Re-read the original request, revert/replace any unrelated changes, and"
    echo "implement the requested behaviour where it belongs — including a test."
  } > /work/self-review.txt
  run_claude_round /work/self-review.txt || fail "claude self-review fix run failed"
done

# --- pre-PR verification gate --------------------------------------------------
# The authoritative local gate. Runs the repo's real lint/test command (the same
# checks CI runs) plus its pre-commit hooks BEFORE the PR opens. A lint error or
# broken test caught here becomes a cheap local fix round; the alternative is a
# failed CI check that blocks merge and burns review rounds. If the code cannot be
# made green in VERIFY_MAX_ROUNDS rounds we FAIL the job and open no PR.

have_precommit() {
  [ -f .pre-commit-config.yaml ] && command -v pre-commit >/dev/null 2>&1
}

# Run every configured verification step; combined output -> /work/verify.log.
run_verify() {
  : > /work/verify.log
  local rc=0
  if have_precommit; then
    local changed=()
    mapfile -t changed < <(git diff --name-only "origin/${BASE_BRANCH}..HEAD")
    if [ "${#changed[@]}" -gt 0 ]; then
      echo "=== pre-commit run (changed files) ===" | tee -a /work/verify.log
      pre-commit run --files "${changed[@]}" >>/work/verify.log 2>&1 || rc=$?
    fi
  fi
  if [ -n "$VERIFY_CMD" ]; then
    echo "=== verify: ${VERIFY_CMD} (bounded ${VERIFY_TIMEOUT}s, CI mode) ===" | tee -a /work/verify.log
    bash -c "$(bounded_runner "$VERIFY_CMD" "$VERIFY_TIMEOUT")" >>/work/verify.log 2>&1 || rc=$?
  fi
  return $rc
}

# One verification attempt. Auto-fixing hooks (ruff --fix, ruff-format) commonly
# rewrite files and still exit non-zero on the same run; commit those and re-check
# once for free before spending a Claude round on them.
verify_once() {
  run_verify && return 0
  if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "=== verify auto-fixed files; committing and re-checking ==="
    git add -A
    git commit -m "chore: apply verify auto-fixes" --no-verify >/dev/null 2>&1 || true
    run_verify && return 0
  fi
  return 1
}

verify_gate() {
  if [ -z "$VERIFY_CMD" ] && ! have_precommit; then
    echo "=== no verify command or pre-commit config; skipping local gate ==="
    return 0
  fi
  echo "=== pre-PR verification gate (cmd='${VERIFY_CMD:-none}', precommit=$(have_precommit && echo yes || echo no)) ==="
  verify_once && { echo "=== local verification passed ==="; return 0; }
  local vround=0
  while [ "$vround" -lt "$VERIFY_MAX_ROUNDS" ]; do
    vround=$((vround + 1))
    echo "=== verification failing; handing to claude (round ${vround}/${VERIFY_MAX_ROUNDS}) ==="
    {
      echo "Your change FAILS the repository's local verification — the same lint/test"
      echo "checks CI runs. Fix every failure below. Keep the feature and its tests"
      echo "intact and do not introduce unrelated changes. Command output:"
      echo
      tail -c 12000 /work/verify.log
    } > /work/verify-findings.txt
    run_claude_round /work/verify-findings.txt || fail "claude verify-fix run failed"
    verify_once && { echo "=== local verification passed after fix round ${vround} ==="; return 0; }
  done
  echo "=== local verification still failing after ${VERIFY_MAX_ROUNDS} round(s) ==="
  tail -40 /work/verify.log
  return 1
}

if ! verify_gate; then
  # Don't discard a near-complete change. Push the branch (no PR — it can't pass
  # CI yet) so a human can finish it, and say so in the reason.
  reason="local verification (lint/test) still failing after ${VERIFY_MAX_ROUNDS} fix round(s); no PR opened"
  echo "=== ${reason}; pushing branch for manual completion ==="
  if git push origin "$VIBECODE_BRANCH" >/dev/null 2>&1; then
    reason="${reason}; branch ${VIBECODE_BRANCH} pushed for manual completion"
  else
    reason="${reason}; branch push also failed"
  fi
  emit_result "$(jq -cn --arg r "$reason" --arg b "$VIBECODE_BRANCH" \
    '{status:"failed", reason:$r, branch:$b, merged:false}')"
  exit 1
fi

echo "=== pushing branch ${VIBECODE_BRANCH} ==="
git push origin "$VIBECODE_BRANCH" || fail "git push failed"

echo "=== opening pull request ==="
PR_BODY="Automated change created by the /vibecode Discord command.

Feature request:

$(printf '%s' "${VIBECODE_FEATURE:-see commit history}" | head -c 2000)

Implemented by Claude Code (${CLAUDE_MODEL}, ${CLAUDE_BACKEND} backend). Lint and
the test suite were verified in the worker before this PR was opened; findings
from the AI review are addressed automatically."

PR_RESPONSE=$(gh_api POST "${API}/pulls" "$(jq -cn \
  --arg title "$VIBECODE_PR_TITLE" \
  --arg head "$VIBECODE_BRANCH" \
  --arg base "$BASE_BRANCH" \
  --arg body "$PR_BODY" \
  '{title:$title, head:$head, base:$base, body:$body}')")

PR_NUMBER=$(echo "$PR_RESPONSE" | jq -r '.number // empty')
PR_URL=$(echo "$PR_RESPONSE" | jq -r '.html_url // empty')
[ -n "$PR_NUMBER" ] || fail "PR creation failed: $(echo "$PR_RESPONSE" | jq -r '.message // "unknown error"')"
echo "=== opened PR #${PR_NUMBER}: ${PR_URL} ==="

# --- review -> fix loop --------------------------------------------------------
# The AI reviewer (oglimmer/review-action, see .github/workflows/ai-review.yml)
# keeps its whole verdict in ONE sticky PR conversation comment, edited in place on
# every push and tagged with a hidden marker. It posts a formal PR review object
# only when it has inline findings, and even then the review body is just the
# marker — so we key off the sticky comment.
REVIEW_SUMMARY_MARKER='<!-- openai-pr-review-action -->'

# The reviewer's summary, as plain prose (sticky conversation comment, markers stripped).
fetch_review_summary() {
  gh_api GET "${API}/issues/${PR_NUMBER}/comments?per_page=100" \
    | jq -r --arg m "$REVIEW_SUMMARY_MARKER" \
        '[.[] | select((.body // "") | contains($m))] | last
         | (.body // "(no summary)") | gsub("<!--[^>]*-->"; "") | gsub("^\\s+|\\s+$"; "")'
}

# review-action embeds a machine-readable verdict in its sticky summary comment:
#   <!-- review-verdict:<approve|request_changes> reviewed-sha:<sha> blocking:<n> -->
# It is the reviewer's OWN explicit verdict for a specific commit, so prefer it
# over re-classifying the prose. Echoes "approve" | "needs_changes", or "" when
# the marker is absent or was written for a different commit.
verdict_from_marker() {
  local head_sha="$1" line v sha
  line=$(gh_api GET "${API}/issues/${PR_NUMBER}/comments?per_page=100" \
    | jq -r --arg m "$REVIEW_SUMMARY_MARKER" \
        '[.[] | select((.body // "") | contains($m))] | last | .body // ""' \
    | grep -oE '<!-- review-verdict:[a-z_]+ reviewed-sha:[0-9a-f]* blocking:[0-9]+ -->' | tail -1)
  [ -n "$line" ] || return 0
  v=$(printf '%s' "$line"  | sed -n 's/.*review-verdict:\([a-z_]*\).*/\1/p')
  sha=$(printf '%s' "$line" | sed -n 's/.*reviewed-sha:\([0-9a-f]*\).*/\1/p')
  [ -n "$sha" ] && [ "$sha" != "$head_sha" ] && return 0   # stale marker; ignore
  case "$v" in
    approve)         echo "approve" ;;
    request_changes) echo "needs_changes" ;;
  esac
}

# Wait until the head commit's check runs are complete AND the reviewer has
# responded (its sticky summary comment is fresh) — or a check has already failed.
# Returns via globals:
#   REVIEW_STATE  "APPROVED" | "CHANGES_REQUESTED" | ""  (formal verdict, if any)
#   REVIEW_SEEN   "yes" | "no"                            (reviewer responded at all)
#   FAILED_CHECKS count of failing/blocking check runs
wait_for_review() {
  local head_sha="$1"
  local deadline=$(( $(date +%s) + REVIEW_TIMEOUT ))
  local iters=0
  while [ "$(date +%s)" -lt "$deadline" ]; do
    iters=$((iters + 1))
    local checks reviews comments total completed seen
    checks=$(gh_api GET "${API}/commits/${head_sha}/check-runs?per_page=100") \
      || { echo "=== check-runs fetch failed; retrying ==="; sleep "$REVIEW_POLL"; continue; }
    total=$(echo "$checks" | jq -r '.check_runs | length // 0')
    completed=$(echo "$checks" | jq -r '[.check_runs[]? | select(.status=="completed")] | length')
    FAILED_CHECKS=$(echo "$checks" | jq -r \
      '[.check_runs[]? | select(.conclusion=="failure" or .conclusion=="timed_out" or .conclusion=="cancelled" or .conclusion=="action_required")] | length')

    reviews=$(gh_api GET "${API}/pulls/${PR_NUMBER}/reviews?per_page=100") \
      || { echo "=== reviews fetch failed; retrying ==="; sleep "$REVIEW_POLL"; continue; }
    REVIEW_STATE=$(echo "$reviews" \
      | jq -r --arg bot "$BOT_LOGIN" --arg sha "$head_sha" \
        '[.[] | select(.user.login != $bot) | select(.commit_id == $sha)
              | select(.state=="APPROVED" or .state=="CHANGES_REQUESTED")] | last | .state // ""')

    comments=$(gh_api GET "${API}/issues/${PR_NUMBER}/comments?per_page=100") \
      || { echo "=== comments fetch failed; retrying ==="; sleep "$REVIEW_POLL"; continue; }
    seen=$(echo "$comments" \
      | jq -r --arg m "$REVIEW_SUMMARY_MARKER" --arg since "$REVIEW_SINCE" \
        '[.[] | select((.body // "") | contains($m))
              | select(($since == "") or (.updated_at > $since))] | length')
    REVIEW_SEEN="no"; [ "${seen:-0}" -gt 0 ] && REVIEW_SEEN="yes"

    local checks_done="no"
    if [ "$total" -gt 0 ] && [ "$completed" -eq "$total" ]; then
      checks_done="yes"
    elif [ "$total" -eq 0 ] && [ "$iters" -ge "$NO_CHECK_GRACE" ]; then
      checks_done="yes"
    fi

    if [ "$checks_done" = "yes" ] && { [ "$REVIEW_SEEN" = "yes" ] || [ "$FAILED_CHECKS" -gt 0 ]; }; then
      echo "=== review ready: verdict='${REVIEW_STATE:-none}' reviewed=${REVIEW_SEEN} failed_checks=${FAILED_CHECKS} ==="
      return 0
    fi
    echo "=== waiting for review (checks ${completed}/${total}, verdict='${REVIEW_STATE:-none}', reviewed=${REVIEW_SEEN}) ==="
    sleep "$REVIEW_POLL"
  done
  REVIEW_STATE=""
  REVIEW_SEEN="no"
  FAILED_CHECKS=0
  return 1
}

# Real detail for each failed check: its GitHub summary, its annotations, and a
# tail of the matching Actions job log — otherwise the model fixes CI blind.
failed_check_details() {
  local head_sha="$1" checks id name
  checks=$(gh_api GET "${API}/commits/${head_sha}/check-runs?per_page=100") || return 0
  while IFS=$'\t' read -r id name; do
    [ -n "$id" ] || continue
    echo "### CHECK: ${name}"
    echo "$checks" | jq -r --arg id "$id" \
      '.check_runs[]? | select((.id|tostring)==$id) | .output.summary // .output.title // "failed"'
    gh_api GET "${API}/check-runs/${id}/annotations?per_page=50" 2>/dev/null \
      | jq -r '.[]? | "  \(.path):\(.start_line // "?"): \(.annotation_level // "note"): \((.message // "")|gsub("\n";" "))"' 2>/dev/null
    local logtail
    logtail=$(curl -sSL --max-time 30 \
      -H "Authorization: Bearer ${GITHUB_TOKEN}" \
      -H "Accept: application/vnd.github+json" \
      "${API}/actions/jobs/${id}/logs" 2>/dev/null | tail -c 4000)
    if [ -n "$logtail" ]; then
      echo "  --- job log tail ---"
      printf '%s\n' "$logtail" | sed 's/^/  /'
    fi
  done < <(echo "$checks" | jq -r '.check_runs[]?
      | select(.conclusion=="failure" or .conclusion=="timed_out" or .conclusion=="cancelled")
      | "\(.id)\t\(.name)"')
}

collect_findings() {
  local head_sha="$1"
  {
    echo "The pull request has unresolved findings from CI and/or the reviewer."
    echo "Address every finding below (fix failing checks first), keep the change"
    echo "minimal, keep tests passing, and do not introduce unrelated modifications."
    echo
    echo "--- REVIEW SUMMARY ---"
    fetch_review_summary
    echo
    echo "--- INLINE COMMENTS ---"
    gh_api GET "${API}/pulls/${PR_NUMBER}/comments?per_page=100" \
      | jq -r '.[]? | "\(.path):\(.line // .original_line // "?"): \((.body // "") | gsub("<!--[^>]*-->"; "") | gsub("^\\s+|\\s+$"; ""))"'
    echo
    echo "--- FAILED CHECKS ---"
    failed_check_details "$head_sha" | head -c 20000
  } > /work/findings.txt
}

# The reviewer's latest body + inline comments as plain text (for the LLM judge).
gather_review_text() {
  echo "REVIEW BODY:"
  fetch_review_summary
  echo
  echo "INLINE COMMENTS:"
  gh_api GET "${API}/pulls/${PR_NUMBER}/comments?per_page=100" \
    | jq -r '.[]? | "- \(.path):\(.line // .original_line // "?"): \((.body // "") | gsub("<!--[^>]*-->"; "") | gsub("^\\s+|\\s+$"; ""))"'
}

# Classify whether a prose review approves the change. Sets JUDGE_VERDICT
# ("approve"|"needs_changes") and JUDGE_REASON. Fails SAFE to needs_changes.
judge_review() {
  JUDGE_VERDICT="needs_changes"
  JUDGE_REASON=""
  local sys user content lc
  sys='You decide whether an automated code review approves merging a pull request. The PR must actually implement the requested feature AND ship a test for it. Reply with ONLY a compact JSON object: {"verdict":"approve"|"needs_changes","reason":"<short>"}. Use "needs_changes" if the review indicates the feature is unmet, incomplete, or incorrect, that unrelated code was changed, that tests are missing, or if it requests any change. Use "approve" only when the review raises no blocking concerns (minor optional nits are fine). When in doubt, answer "needs_changes".'
  user=$(printf 'FEATURE REQUESTED:\n%s\n\nAUTOMATED REVIEW:\n%s\n' \
    "${VIBECODE_FEATURE:-(not provided)}" "$(gather_review_text)")

  content=$(deepseek_call "$sys" "$user") || { JUDGE_REASON="review-judge request failed"; return; }
  if [ -z "$content" ]; then
    JUDGE_REASON="review-judge returned no content"
    return
  fi
  lc=$(printf '%s' "$content" | tr '[:upper:]' '[:lower:]')
  if printf '%s' "$lc" | grep -q 'needs_changes'; then
    JUDGE_VERDICT="needs_changes"
  elif printf '%s' "$lc" | grep -qE '"verdict"[^}]*approve|^[[:space:]]*approve'; then
    JUDGE_VERDICT="approve"
  fi
  JUDGE_REASON=$(printf '%s' "$content" | jq -r '.reason // empty' 2>/dev/null)
  [ -n "$JUDGE_REASON" ] || JUDGE_REASON=$(printf '%s' "$content" | tr '\n' ' ' | cut -c1-200)
}

REVIEW_STATE=""
REVIEW_SEEN="no"
FAILED_CHECKS=0
JUDGE_VERDICT=""
JUDGE_REASON=""
MERGED=false
# Set true when the PR was approved+green but AUTO_MERGE is disabled, so it is a
# successful run that intentionally leaves the merge to a human.
APPROVED_NO_MERGE=false
# UTC timestamp of the most recent push; a sticky review comment is only "fresh"
# once its updated_at passes this. Set immediately before every push.
REVIEW_SINCE=""

# Evaluate the head commit up to REVIEW_MAX_ROUNDS+1 times but only spend a fix in
# the first REVIEW_MAX_ROUNDS iterations, so the LAST pushed fix still gets a
# wait+decide (and can merge) instead of being pushed and abandoned.
for attempt in $(seq 0 "$REVIEW_MAX_ROUNDS"); do
  HEAD_SHA=$(git rev-parse HEAD)
  if ! wait_for_review "$HEAD_SHA"; then
    fail "timed out waiting for the PR review"
  fi

  decision="fix"
  if [ "$FAILED_CHECKS" -eq 0 ]; then
    case "$REVIEW_STATE" in
      APPROVED) decision="merge" ;;
      CHANGES_REQUESTED) decision="fix" ;;
      *)
        marker_verdict=$(verdict_from_marker "$HEAD_SHA")
        if [ -n "$marker_verdict" ]; then
          JUDGE_VERDICT="$marker_verdict"
          JUDGE_REASON="from review-action verdict marker"
          echo "=== review verdict (marker): ${JUDGE_VERDICT} ==="
        else
          echo "=== no formal verdict; classifying review prose (${REVIEW_JUDGE_MODEL}) ==="
          judge_review
          echo "=== review judge: ${JUDGE_VERDICT} — ${JUDGE_REASON} ==="
        fi
        [ "$JUDGE_VERDICT" = "approve" ] && decision="merge"
        ;;
    esac
  fi

  if [ "$decision" = "merge" ]; then
    # Auto-merge disabled (the default here): the PR is approved and green, but
    # the final merge is left to a human. Stop and report success, PR open.
    if [ "$AUTO_MERGE" != "true" ]; then
      echo "=== approved (checks green, verdict='${REVIEW_STATE:-none}'); auto-merge disabled — leaving PR open ==="
      APPROVED_NO_MERGE=true
      break
    fi
    echo "=== approved for merge (checks green, verdict='${REVIEW_STATE:-none}'); merging ==="
    MERGE_RESPONSE=$(gh_api PUT "${API}/pulls/${PR_NUMBER}/merge" \
      "$(jq -cn --arg m "squash" '{merge_method:$m}')")
    if [ "$(echo "$MERGE_RESPONSE" | jq -r '.merged // false')" = "true" ]; then
      MERGED=true
      break
    fi
    fail "auto-merge failed: $(echo "$MERGE_RESPONSE" | jq -r '.message // "unknown error"')"
  fi

  # Not mergeable, and no fix budget left: the fix pushed last round was just
  # evaluated above and still fell short. Stop and leave the PR open.
  if [ "$attempt" -ge "$REVIEW_MAX_ROUNDS" ]; then
    break
  fi

  fix_round=$((attempt + 1))
  echo "=== findings to address (failed_checks=${FAILED_CHECKS}, verdict='${REVIEW_STATE:-none}'; round ${fix_round}/${REVIEW_MAX_ROUNDS}) ==="
  collect_findings "$HEAD_SHA"
  run_claude_round /work/findings.txt || fail "claude fix run failed"

  if [ "$(git rev-list --count "origin/${VIBECODE_BRANCH}..HEAD")" -eq 0 ]; then
    fail "agent produced no fix commits for the review findings"
  fi
  REVIEW_SINCE=$(date -u +%Y-%m-%dT%H:%M:%SZ)   # freshness baseline for this push
  git push origin "$VIBECODE_BRANCH" || fail "git push (fix) failed"
done

# Approved, but auto-merge is off (the default): a successful run that hands the
# final merge to a human. Reported as success with merged:false.
if [ "$APPROVED_NO_MERGE" = "true" ]; then
  echo "=== done: approved, PR ready for manual merge ${PR_URL} ==="
  emit_result "$(jq -cn --arg u "$PR_URL" --arg b "$VIBECODE_BRANCH" \
    '{status:"success", pr_url:$u, branch:$b, merged:false}')"
  exit 0
fi

if [ "$MERGED" != "true" ]; then
  reason="review not approved after ${REVIEW_MAX_ROUNDS} round(s); PR left open"
  [ -n "$JUDGE_REASON" ] && reason="${reason} (last review verdict: ${JUDGE_VERDICT} — ${JUDGE_REASON})"
  emit_result "$(jq -cn --arg u "$PR_URL" --arg b "$VIBECODE_BRANCH" --arg r "$reason" \
    '{status:"failed", pr_url:$u, branch:$b, merged:false, reason:$r}')"
  exit 1
fi

echo "=== done: merged ${PR_URL} ==="
emit_result "$(jq -cn --arg u "$PR_URL" --arg b "$VIBECODE_BRANCH" \
  '{status:"success", pr_url:$u, branch:$b, merged:true}')"
