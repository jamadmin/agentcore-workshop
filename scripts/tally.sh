#!/usr/bin/env bash
# Lists the credits issued to a Tally customer, straight from the backend.
#   tally.sh credits kettle
#   tally.sh reset kettle      clear them (facilitators, before a dry run)
# Run this, don't source it: sourcing would run it in your own shell and could close it.
(return 0 2>/dev/null) && { echo "This is a script, so run it rather than sourcing it: ${WORKSHOP:-.}/scripts/tally.sh" >&2; return 1; }
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"

cmd="${1:-}"; customer="${2:-}"
[[ -n "$customer" ]] || die "Usage: tally.sh credits|reset <customer id>"
case "$cmd" in
  credits)
    invoke_backend tally "{\"tool\":\"list_credits\",\"customer_id\":\"$customer\"}" | python3 "$WORKSHOP/scripts/lib/show.py" credits ;;
  reset)
    invoke_backend tally "{\"tool\":\"reset_credits\",\"customer_id\":\"$customer\"}" >/dev/null
    echo "Credits for $customer cleared." ;;
  *)
    die "Usage: tally.sh credits|reset <customer id>" ;;
esac
