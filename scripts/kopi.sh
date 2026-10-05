#!/usr/bin/env bash
# Reads or clears today's run straight from the Kopi Run backend.
#   kopi.sh run      show the run
#   kopi.sh reset    empty it
# Run this, don't source it: sourcing would run it in your own shell and could close it.
(return 0 2>/dev/null) && { echo "This is a script, so run it rather than sourcing it: ${WORKSHOP:-.}/scripts/kopi.sh" >&2; return 1; }
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"

case "${1:-}" in
  run)
    invoke_backend kopi '{"tool":"get_run"}' | python3 "$WORKSHOP/scripts/lib/show.py" run ;;
  reset)
    invoke_backend kopi '{"tool":"reset_run"}' >/dev/null
    echo "Today's run is empty." ;;
  *)
    die "Usage: kopi.sh run|reset" ;;
esac
