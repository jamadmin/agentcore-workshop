#!/usr/bin/env bash
# Asks a harness each question in a file, one new session per question, and prints the answers.
#   intake-ask.sh intake_agent $WORKSHOP/intake/questions.txt
# Run this, don't source it: sourcing would run it in your own shell and could close it.
(return 0 2>/dev/null) && { echo "This is a script, so run it rather than sourcing it: ${WORKSHOP:-.}/scripts/intake-ask.sh" >&2; return 1; }
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"
[[ $# -eq 2 ]] || die "Usage: intake-ask.sh <harness name> <questions file>"
[[ -f "$2" ]] || die "No such file: $2"
agentcore_py ask "$1" "$2"
