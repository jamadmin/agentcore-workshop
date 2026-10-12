#!/usr/bin/env bash
# Prints a gateway's MCP endpoint (<gateway URL>/mcp), found by name. Works for console- and CLI-built gateways.
#   gateway-url.sh tally-gw
# Run this, don't source it: sourcing would run it in your own shell and could close it.
(return 0 2>/dev/null) && { echo "This is a script, so run it rather than sourcing it: ${WORKSHOP:-.}/scripts/gateway-url.sh" >&2; return 1; }
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"
[[ $# -eq 1 ]] || die "Usage: gateway-url.sh <gateway name>"
agentcore_py gateway-url "$1"
