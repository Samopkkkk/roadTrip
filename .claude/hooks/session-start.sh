#!/bin/bash
# Install backend dependencies so tests and linters work in Claude Code on the web.
set -euo pipefail

# Only needed in the remote (web) environment — local checkouts manage their own venv.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}"

# Idempotent: pip skips already-satisfied requirements, and the container image
# is cached after the hook completes, so subsequent sessions start fast.
python3 -m pip install --quiet --disable-pip-version-check -r backend/requirements.txt

echo "session-start: backend dependencies installed."
