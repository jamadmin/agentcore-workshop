#!/usr/bin/env bash
# Lists the credits issued to a Tally customer, straight from the backend.
#   tally.sh credits kettle
#   tally.sh reset kettle      clear them (facilitators, before a dry run)
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
