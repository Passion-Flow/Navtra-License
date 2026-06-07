#!/bin/sh
# Container entrypoint (init-scripts.md): wait deps -> migrate (advisory-lock) -> bootstrap.
# POSIX sh only (no bash 4+ syntax). Each step is idempotent.
set -e

forge healthcheck --wait-deps --timeout 60

# Only the api role runs migrations + bootstrap; edge/worker/scheduler skip them.
if [ "${APP_ROLE:-api}" = "api" ]; then
  forge migrate up
  forge bootstrap --silent
fi

exec "$@"
