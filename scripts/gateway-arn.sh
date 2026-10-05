#!/usr/bin/env bash
# Prints a gateway's ARN, found by name. Works for console- and CLI-built gateways.
#   gateway-arn.sh tally-gw
# Run this, don't source it: sourcing would run it in your own shell and could close it.
(return 0 2>/dev/null) && { echo "This is a script, so run it rather than sourcing it: ${WORKSHOP:-.}/scripts/gateway-arn.sh" >&2; return 1; }
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"
[[ $# -eq 1 ]] || die "Usage: gateway-arn.sh <gateway name>"
agentcore_py gateway-arn "$1"
