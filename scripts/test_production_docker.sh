#!/usr/bin/env bash
# Each invocation owns an isolated Compose project with ephemeral PostgreSQL data.
set -euo pipefail
translation_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
translation_compose="$translation_root/deploy/docker-compose.production-tests.yml"
# Empty interpolation env prevents workspace .env from influencing the test stack.
translation_env="$(mktemp /tmp/translation-tests-env.XXXXXX)"
translation_project="translation-integration-${translation_env##*.}"
translation_project="${translation_project,,}"
cleanup() {
  translation_result=$?
  trap - EXIT
  docker compose --env-file "$translation_env" -p "$translation_project" -f "$translation_compose" down --volumes --remove-orphans || true
  rm -f -- "$translation_env"
  exit "$translation_result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
docker compose --env-file "$translation_env" -p "$translation_project" -f "$translation_compose" up \
  --build --abort-on-container-exit --exit-code-from tests
