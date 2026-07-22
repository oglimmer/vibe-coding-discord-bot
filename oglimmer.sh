#!/usr/bin/env bash
#
# oglimmer.sh — project task runner.
#
# Dispatcher for repeatable dev/CI tasks. Designed to work on a fresh clone:
# it provisions an isolated virtualenv and installs dependencies on first run.
#
# Guarantees:
#   * Non-interactive — never reads stdin, never prompts. Safe for CI/hooks.
#   * Never blocks — stdin is closed for every child process.
#   * Fails loud — any error aborts with a non-zero exit code.
#
# Usage:
#   ./oglimmer.sh test          Lint + tests on the host venv
#   ./oglimmer.sh test --docker  Same suite in a clean-room Docker container
#   ./oglimmer.sh help          Show available commands
#
# The PostgreSQL driver is psycopg[binary], a self-contained wheel that bundles
# libpq — it installs from PyPI on a fresh clone with no system libraries, so
# both modes just `pip install`. The DB-touching tests are gated
# (POSTILLON_DB_TEST) or use an in-memory fake, so no PostgreSQL server is needed.
set -euo pipefail

# --- Resolve repo root regardless of caller's CWD --------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- Configuration ---------------------------------------------------------
VENV_DIR="${OGLIMMER_VENV:-$SCRIPT_DIR/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
RUFF_VERSION="0.8.4"   # keep in sync with .pre-commit-config.yaml / ci.yml

# Make every pip/tool invocation non-interactive and quiet-ish.
export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_NO_INPUT=1
export PYTHONDONTWRITEBYTECODE=1
export DEBIAN_FRONTEND=noninteractive

# --- Logging helpers -------------------------------------------------------
log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m warn:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

# Run a child command with stdin closed so nothing can ever block on input.
run() { "$@" </dev/null; }

# --- Environment provisioning ----------------------------------------------
# Creates the host venv on first run and installs all dependencies. The
# psycopg[binary] wheel needs no system libraries, so this works on a fresh
# clone. A stamp keyed on the requirements skips reinstalls when unchanged.
ensure_venv() {
  command -v "$PYTHON_BIN" >/dev/null 2>&1 \
    || die "$PYTHON_BIN not found on PATH. Install Python 3.12+ first."

  if [ ! -x "$VENV_DIR/bin/python" ]; then
    log "Creating virtualenv at $VENV_DIR"
    run "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi

  local py="$VENV_DIR/bin/python"
  local stamp="$VENV_DIR/.deps.stamp"
  local sig
  sig="$(cat requirements.txt requirements-dev.txt)"

  if [ ! -f "$stamp" ] || ! printf '%s' "$sig" | cmp -s - "$stamp"; then
    log "Installing dependencies"
    run "$py" -m pip install --upgrade pip
    run "$py" -m pip install -r requirements-dev.txt
    printf '%s' "$sig" > "$stamp"
  fi

  # Install ruff pinned to the CI version if missing/mismatched.
  if ! "$VENV_DIR/bin/ruff" --version 2>/dev/null | grep -q "$RUFF_VERSION"; then
    log "Installing ruff==$RUFF_VERSION"
    run "$py" -m pip install "ruff==$RUFF_VERSION"
  fi
}

# --- Full suite in a clean-room Docker container ---------------------------
# Runs the exact CI recipe inside a stock python image. Source is mounted
# read-only; all caches/bytecode are redirected to /tmp so the host tree and
# the host .venv are never touched. Needs only Docker — no host libs, no DB
# server (psycopg[binary] installs from PyPI, DB tests are gated/faked).
run_full_in_docker() {
  command -v docker >/dev/null 2>&1 \
    || die "Docker not found. '--docker' runs the suite in a container and needs Docker."
  run docker info >/dev/null 2>&1 \
    || die "Docker daemon not reachable. Start Docker Desktop / the daemon and retry."

  local image="${OGLIMMER_DOCKER_IMAGE:-python:3.12}"
  log "Full suite in Docker: $image"

  # Inner script runs as root; set -euo pipefail so any step aborts the
  # container with a non-zero status.
  run docker run --rm \
    -v "$SCRIPT_DIR:/app:ro" -w /app \
    -e PIP_DISABLE_PIP_VERSION_CHECK=1 -e PIP_NO_INPUT=1 \
    -e DEBIAN_FRONTEND=noninteractive \
    -e PYTHONPYCACHEPREFIX=/tmp/pyc -e RUFF_CACHE_DIR=/tmp/ruff \
    "$image" bash -euo pipefail -c '
      echo "==> pip install (deps incl. psycopg[binary])"
      python -m pip install --quiet --upgrade pip
      python -m pip install --quiet "ruff=='"$RUFF_VERSION"'" -r requirements-dev.txt
      echo "==> ruff lint";          ruff check .
      echo "==> ruff format check";  ruff format --check .
      echo "==> unittest suite";     python -m unittest discover tests -v
      echo "==> pytest e2e suite";   python -m pytest -p no:cacheprovider tests/test_e2e_1337.py -v
      echo "==> syntax check"
      find . -name "*.py" -not -path "./.venv/*" -not -path "./venv/*" -print0 \
        | xargs -0 python -m py_compile
    '
}

# --- Commands --------------------------------------------------------------
cmd_test() {
  local mode=host
  for arg in "$@"; do
    case "$arg" in
      --docker|--full) mode=docker ;;
      # Deprecated alias from the MariaDB era — kept so old muscle memory works.
      --with-postgres|--with-mariadb)
        warn "$arg is deprecated; use --docker"; mode=docker ;;
      -h|--help) echo "usage: oglimmer.sh test [--docker]"; return 0 ;;
      *) die "unknown option for 'test': $arg" ;;
    esac
  done

  if [ "$mode" = docker ]; then
    run_full_in_docker
    log "All checks passed (mode: docker)."
    return 0
  fi

  # --- host: host venv -----------------------------------------------------
  ensure_venv
  local py="$VENV_DIR/bin/python"
  local ruff="$VENV_DIR/bin/ruff"

  log "Ruff lint"
  run "$ruff" check .

  log "Ruff format check"
  run "$ruff" format --check .

  log "Unittest suite"
  run "$py" -m unittest discover tests -v

  log "Pytest e2e suite"
  run "$py" -m pytest tests/test_e2e_1337.py -v

  log "Syntax check"
  find . -name '*.py' -not -path './.venv/*' -not -path './venv/*' -print0 \
    | xargs -0 "$py" -m py_compile

  log "All checks passed (mode: host)."
}

cmd_help() {
  cat <<'EOF'
oglimmer.sh — project task runner

Commands:
  test [--docker]
          Provision venv (first run) then run lint + full test suite (mirrors CI):
            ruff check . / ruff format --check .
            python -m unittest discover tests
            python -m pytest tests/test_e2e_1337.py
            py_compile syntax sweep
          Default (host): runs on the host venv. psycopg[binary] installs from
          PyPI with no system libraries, so this works on a fresh clone.
          --docker (--full): runs the same suite inside a clean-room Docker
          container. Needs only Docker — no host libs, no DB server.
  help    Show this message

Env overrides:
  OGLIMMER_VENV          host venv location    (default: ./.venv)
  PYTHON_BIN             base python           (default: python3)
  OGLIMMER_DOCKER_IMAGE  docker-mode image     (default: python:3.12)
EOF
}

# --- Dispatch --------------------------------------------------------------
main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    test) cmd_test "$@" ;;
    help|-h|--help) cmd_help ;;
    *) warn "Unknown command: $cmd"; cmd_help; exit 2 ;;
  esac
}

main "$@"
