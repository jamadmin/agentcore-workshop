#!/usr/bin/env bash
# Prints a gateway's ARN, found by name. Works for console- and CLI-built gateways.
#   gateway-arn.sh tally-gw
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"
[[ $# -eq 1 ]] || die "Usage: gateway-arn.sh <gateway name>"
agentcore_py gateway-arn "$1"
