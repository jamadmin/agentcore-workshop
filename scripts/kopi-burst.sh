#!/usr/bin/env bash
# Sends n orders to the harness named kopi_agent at the same moment, each from a
# different person in its own session, and prints how long each one took.
#   kopi-burst.sh [n]     default 20, at most 26
# Run this, don't source it: sourcing would run it in your own shell and could close it.
(return 0 2>/dev/null) && { echo "This is a script, so run it rather than sourcing it: ${WORKSHOP:-.}/scripts/kopi-burst.sh" >&2; return 1; }
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"
n="${1:-20}"
[[ "$n" =~ ^[0-9]+$ && "$n" -ge 1 ]] || die "Usage: kopi-burst.sh [number of orders]"
agentcore_py burst kopi_agent "$n"
