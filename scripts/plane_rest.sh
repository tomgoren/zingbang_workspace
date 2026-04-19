#!/usr/bin/env bash

set -euo pipefail

if [[ -z "${PLANE_API_KEY:-}" || -z "${PLANE_WORKSPACE_SLUG:-}" || -z "${PLANE_BASE_URL:-}" ]]; then
  printf 'Missing required env vars: PLANE_API_KEY, PLANE_WORKSPACE_SLUG, PLANE_BASE_URL\n' >&2
  exit 1
fi

usage() {
  cat <<'EOF'
Usage:
  scripts/plane_rest.sh projects
  scripts/plane_rest.sh states <project_id>
  scripts/plane_rest.sh labels <project_id>
  scripts/plane_rest.sh project-items <project_id>
  scripts/plane_rest.sh ticket <project_identifier> <issue_number>
  scripts/plane_rest.sh search <query>

Notes:
  - Uses PLANE_API_KEY, PLANE_WORKSPACE_SLUG, and PLANE_BASE_URL from the environment.
  - Outputs raw JSON so it composes cleanly with jq.
EOF
}

api_get() {
  local endpoint="$1"
  shift || true

  curl -fsSL -G \
    -H "X-API-Key: $PLANE_API_KEY" \
    "$PLANE_BASE_URL/api/v1/workspaces/$PLANE_WORKSPACE_SLUG/$endpoint" \
    "$@"
}

cmd="${1:-}"

case "$cmd" in
  projects)
    api_get "projects/"
    ;;
  states)
    [[ $# -eq 2 ]] || { usage >&2; exit 1; }
    api_get "projects/$2/states/"
    ;;
  labels)
    [[ $# -eq 2 ]] || { usage >&2; exit 1; }
    api_get "projects/$2/labels/"
    ;;
  project-items)
    [[ $# -eq 2 ]] || { usage >&2; exit 1; }
    api_get "projects/$2/work-items/"
    ;;
  ticket)
    [[ $# -eq 3 ]] || { usage >&2; exit 1; }
    api_get "projects/$2/issues/$3/"
    ;;
  search)
    [[ $# -eq 2 ]] || { usage >&2; exit 1; }
    api_get "work-items/search/" --data-urlencode "query=$2"
    ;;
  ""|-h|--help|help)
    usage
    ;;
  *)
    printf 'Unknown command: %s\n\n' "$cmd" >&2
    usage >&2
    exit 1
    ;;
esac
