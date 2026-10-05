#!/usr/bin/env bash
# Asks a harness each question in a file, one new session per question, and prints the answers.
#   intake-ask.sh intake_agent $WORKSHOP/intake/questions.txt
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"
[[ $# -eq 2 ]] || die "Usage: intake-ask.sh <harness name> <questions file>"
[[ -f "$2" ]] || die "No such file: $2"
agentcore_py ask "$1" "$2"
