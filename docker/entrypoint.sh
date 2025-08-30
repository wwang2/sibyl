#!/usr/bin/env bash
set -euo pipefail
[[ -f ".env" ]] && export $(grep -v '^#' .env | xargs) || true
exec "$@"
