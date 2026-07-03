#!/usr/bin/env bash
# Vibecode worker pipeline:
#   clone repo -> branch -> aider (DeepSeek) implements the feature ->
#   verify lint + tests -> push -> open PR -> emit VIBECODE_RESULT line.
#
# Required env: GITHUB_TOKEN, DEEPSEEK_API_KEY, VIBECODE_REPO (owner/name),
#               VIBECODE_BRANCH, VIBECODE_PROMPT, VIBECODE_PR_TITLE
# Optional env: VIBECODE_BASE_BRANCH (default main), AIDER_MODEL
set -uo pipefail

BASE_BRANCH="${VIBECODE_BASE_BRANCH:-main}"
AIDER_MODEL="${AIDER_MODEL:-deepseek/deepseek-v4-pro}"
REPO_DIR=/work/repo
VENV=/work/venv

emit_result() {
  # single-line JSON so the bot can grep it out of the pod logs
  echo "VIBECODE_RESULT:$1"
}

fail() {
  emit_result "$(jq -cn --arg r "$1" --arg b "${VIBECODE_BRANCH:-}" \
    '{status:"failed", reason:$r, branch:$b}')"
  exit 1
}

for var in GITHUB_TOKEN DEEPSEEK_API_KEY VIBECODE_REPO VIBECODE_BRANCH \
           VIBECODE_PROMPT VIBECODE_PR_TITLE; do
  [ -n "${!var:-}" ] || fail "missing required env var: $var"
done

echo "=== vibecode worker: cloning ${VIBECODE_REPO} ==="
git clone "https://x-access-token:${GITHUB_TOKEN}@github.com/${VIBECODE_REPO}.git" \
  "$REPO_DIR" || fail "git clone failed"
cd "$REPO_DIR" || fail "repo dir missing"

git config user.name "vibecode-bot"
git config user.email "vibecode-bot@users.noreply.github.com"
git checkout -b "$VIBECODE_BRANCH" "origin/${BASE_BRANCH}" || fail "branch creation failed"

echo "=== installing repository dependencies ==="
python -m venv "$VENV" || fail "venv creation failed"
"$VENV/bin/pip" install --no-cache-dir --quiet --upgrade pip || fail "pip upgrade failed"
"$VENV/bin/pip" install --no-cache-dir --quiet -r requirements-dev.txt \
  || fail "dependency installation failed"
"$VENV/bin/pip" install --no-cache-dir --quiet ruff==0.8.4 || fail "ruff installation failed"

TEST_CMD="$VENV/bin/python -m unittest discover tests"
printf '%s' "$VIBECODE_PROMPT" > /work/prompt.txt

run_aider() {
  aider \
    --model "$AIDER_MODEL" \
    --yes-always \
    --no-check-update \
    --no-show-model-warnings \
    --no-attribute-author \
    --no-attribute-committer \
    --auto-test \
    --test-cmd "$TEST_CMD" \
    --message-file "$1"
}

echo "=== running aider (${AIDER_MODEL}) ==="
run_aider /work/prompt.txt || fail "aider run failed"

echo "=== verifying: ruff ==="
"$VENV/bin/ruff" check --fix . && "$VENV/bin/ruff" format .
if ! git diff --quiet; then
  git add -A
  git commit -m "style: apply ruff autofixes" || fail "committing lint fixes failed"
fi
"$VENV/bin/ruff" check . || fail "ruff check still failing after autofix"
"$VENV/bin/ruff" format --check . || fail "ruff format still failing after autofix"

echo "=== verifying: test suite ==="
if ! $TEST_CMD; then
  echo "=== tests failing, giving aider one repair round ==="
  $TEST_CMD 2>&1 | tail -n 100 > /work/test-failures.txt || true
  {
    echo "The test suite (python -m unittest discover tests) is failing."
    echo "Fix the code and/or tests so the whole suite passes. Failure output:"
    echo
    cat /work/test-failures.txt
  } > /work/repair-prompt.txt
  run_aider /work/repair-prompt.txt || fail "aider repair run failed"
  $TEST_CMD || fail "test suite still failing after repair attempt"
fi

# A green suite only proves the *existing* tests still pass; it does not prove
# the new feature is exercised at all. Require the change to add or modify a
# test, giving the agent one round to add one if it forgot.
tests_changed() {
  [ -n "$(git diff --name-only "origin/${BASE_BRANCH}..HEAD" -- tests/)" ]
}
if ! tests_changed; then
  echo "=== no test added; asking aider to add one ==="
  {
    echo "Your change does not add or modify any test under tests/."
    echo "Add a test (python unittest style, discovered by"
    echo "'python -m unittest discover tests') that exercises the feature you"
    echo "just implemented and would FAIL without your change. Then ensure the"
    echo "whole suite still passes."
  } > /work/test-required-prompt.txt
  run_aider /work/test-required-prompt.txt || fail "aider test-adding run failed"
  "$VENV/bin/ruff" check --fix . && "$VENV/bin/ruff" format .
  if ! git diff --quiet; then
    git add -A
    git commit -m "test: add coverage for the new feature" || fail "committing test failed"
  fi
  $TEST_CMD || fail "test suite failing after adding tests"
  tests_changed || fail "the change ships no test (agent did not add one)"
fi

if [ "$(git rev-list --count "origin/${BASE_BRANCH}..HEAD")" -eq 0 ]; then
  fail "the coding agent made no commits"
fi

echo "=== pushing branch ${VIBECODE_BRANCH} ==="
git push origin "$VIBECODE_BRANCH" || fail "git push failed"

echo "=== creating pull request ==="
PR_BODY="Automated change created by the /vibecode Discord command.

Feature request:

$(printf '%s' "${VIBECODE_FEATURE:-see prompt}" | head -c 2000)

Implemented by aider + ${AIDER_MODEL}. Test suite and ruff verified in the worker before this PR was opened."

PR_RESPONSE=$(curl -sS -X POST \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/${VIBECODE_REPO}/pulls" \
  -d "$(jq -cn \
        --arg title "$VIBECODE_PR_TITLE" \
        --arg head "$VIBECODE_BRANCH" \
        --arg base "$BASE_BRANCH" \
        --arg body "$PR_BODY" \
        '{title:$title, head:$head, base:$base, body:$body}')") \
  || fail "GitHub PR API call failed"

PR_URL=$(echo "$PR_RESPONSE" | jq -r '.html_url // empty')
[ -n "$PR_URL" ] || fail "PR creation failed: $(echo "$PR_RESPONSE" | jq -r '.message // "unknown error"')"

echo "=== done: ${PR_URL} ==="
emit_result "$(jq -cn --arg u "$PR_URL" --arg b "$VIBECODE_BRANCH" \
  '{status:"success", pr_url:$u, branch:$b}')"
