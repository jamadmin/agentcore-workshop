#!/usr/bin/env bash
# Prints a gateway's MCP URL, found by name. Works for console- and CLI-built gateways.
#   gateway-url.sh tally-gw
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"
[[ $# -eq 1 ]] || die "Usage: gateway-url.sh <gateway name>"
agentcore_py gateway-url "$1"
